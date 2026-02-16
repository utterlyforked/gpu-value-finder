#!/usr/bin/env python3
"""
Generic pipeline interpreter — reads pipeline.yml and returns all currently runnable tasks.
Parallel-safe: uses sentinel files for completion tracking.
"""
import json
import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_complete(task_id):
    return Path(f'docs/.state/completed/{task_id}.done').exists()


def get_all_spec_files():
    """Return all engineering spec files, excluding the review doc itself."""
    specs_dir = Path('docs/05-specs')
    if not specs_dir.exists():
        return []
    return sorted(
        str(p) for p in specs_dir.glob('*.md')
        if not p.name.startswith('spec-review')
        and not p.name.startswith('SPEC-REVIEW')
    )


def get_latest_feature_docs():
    features_dir = Path('docs/02-features')
    refinement_dir = Path('docs/03-refinement')
    docs = []
    for feature_file in sorted(features_dir.glob('*.md')):
        refined_dir = refinement_dir / feature_file.stem
        if refined_dir.exists():
            updates = sorted(refined_dir.glob('updated-v1.*.md'))
            if updates:
                docs.append(str(updates[-1]))
                continue
        docs.append(str(feature_file))
    return docs


def get_latest_feature_doc(feature_id, feature_slug):
    """Return the most refined version of a single feature doc, falling back to the initial breakdown."""
    stem = f'{feature_id}-{feature_slug}'
    refined_dir = Path(f'docs/03-refinement/{stem}')
    if refined_dir.exists():
        updates = sorted(refined_dir.glob('updated-v1.*.md'))
        if updates:
            return str(updates[-1])
    return f'docs/02-features/{stem}.md'


def get_latest_questions_file(feature_id, feature_slug):
    """Return the highest-iteration tech-lead questions file for a feature, or None if none exist."""
    stem = f'{feature_id}-{feature_slug}'
    refined_dir = Path(f'docs/03-refinement/{stem}')
    if refined_dir.exists():
        questions = sorted(refined_dir.glob('questions-iter-*.md'))
        if questions:
            return str(questions[-1])
    return None


def resolve_value(value, **kwargs):
    """Resolve a single value — handles special tokens and {pattern} substitution."""
    if value == '{{latest_feature_docs}}':
        return get_latest_feature_docs()
    if value == '{{latest_feature_doc}}':
        return get_latest_feature_doc(kwargs['feature_id'], kwargs['feature_slug'])
    if value == '{{latest_questions_file}}':
        return get_latest_questions_file(kwargs['feature_id'], kwargs['feature_slug'])
    if value == '{{all_spec_files}}':
        return get_all_spec_files()
    if isinstance(value, str):
        return value.format(**kwargs)
    return value


def resolve_input(input_dict, **kwargs):
    """Resolve all values in an input dict, skipping optional files that don't exist yet."""
    optional_keys = {'appsec_doc', 'qa_doc', 'foundation_spec', 'tech_lead_review'}
    resolved = {}
    for key, value in input_dict.items():
        resolved_value = resolve_value(value, **kwargs)
        # Drop keys that resolved to None (e.g. {{latest_questions_file}} with no refinement)
        if resolved_value is None:
            continue
        if key in optional_keys and isinstance(resolved_value, str):
            if not Path(resolved_value).exists():
                continue
        resolved[key] = resolved_value
    return resolved


def parse_feature_registry():
    """Load or derive the feature registry from the PRD."""
    registry_path = Path('docs/.state/feature-registry.json')
    if registry_path.exists():
        with open(registry_path) as f:
            return json.load(f)

    prd_path = Path('docs/01-prd/prd-v1.0.md')
    if not prd_path.exists():
        return {}

    with open(prd_path) as f:
        content = f.read()

    features = [m.strip() for m in re.findall(r'###\s+Feature\s+\d+:\s+(.+)', content)]
    registry = {}
    for i, feature in enumerate(features, 1):
        feature_id = f'FEAT-{i:02d}'
        slug = feature.lower().replace(' ', '-').replace(':', '').replace(',', '')
        registry[feature_id] = {'id': feature_id, 'name': feature, 'slug': slug}

    if registry:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_path, 'w') as f:
            json.dump(registry, f, indent=2)

    return registry


def build_task(task_id, agent, output_path, task_input):
    return {'id': task_id, 'agent': agent, 'output_path': output_path, 'input': task_input}


# ---------------------------------------------------------------------------
# Stage processors — return [] (pass), [tasks] (work to do), or None (gate)
# ---------------------------------------------------------------------------

def process_single(stage):
    task_id = stage.get('task_id', stage['id'])
    output = stage['output']
    if is_complete(task_id) or Path(output).exists():
        return []
    task_input = resolve_input(stage.get('input', {}))
    return [build_task(task_id, stage['agent'], output, task_input)]


def process_gate(stage):
    if Path(stage['sentinel']).exists():
        return []
    print(f"⏸  Gate: {stage['message']}", file=sys.stderr)
    return None


def process_per_feature(stage):
    registry = parse_feature_registry()
    if not registry:
        return []
    tasks = []
    for feature_id, feature in registry.items():
        kwargs = {'feature_id': feature_id, 'feature_slug': feature['slug'], 'feature_name': feature['name']}
        task_id = stage['task_id'].format(**kwargs)
        output = stage['output'].format(**kwargs)
        if is_complete(task_id) or Path(output).exists():
            continue
        task_input = resolve_input(stage.get('input', {}), **kwargs)
        task_input['feature_id'] = feature_id
        task_input['feature'] = feature['slug']
        tasks.append(build_task(task_id, stage['agent'], output, task_input))
    return tasks


def process_parallel_group(stage):
    tasks = []
    for subtask in stage['tasks']:
        task_id = subtask['task_id']
        output = subtask['output']
        if is_complete(task_id) or Path(output).exists():
            continue
        task_input = resolve_input(subtask.get('input', {}))
        tasks.append(build_task(task_id, subtask['agent'], output, task_input))
    return tasks


def process_refinement_loop(stage):
    """Tech-lead / product-spec iteration loop, one chain per feature, all features in parallel."""
    features_dir = Path('docs/02-features')
    if not features_dir.exists():
        return []

    feature_files = list(features_dir.glob('*.md'))
    if not feature_files:
        return []

    # All feature breakdowns must be complete before refinement starts
    registry = parse_feature_registry()
    for feature_id, feature in registry.items():
        output = f'docs/02-features/{feature_id}-{feature["slug"]}.md'
        if not is_complete(f'breakdown-{feature_id}') and not Path(output).exists():
            return []

    max_iter = stage.get('max_iterations', 5)
    ready_signal = stage.get('ready_signal', 'READY FOR IMPLEMENTATION')
    reviewer = stage['reviewer']
    responder = stage['responder']
    refinement_dir = Path('docs/03-refinement')
    tasks = []

    for feature_file in sorted(feature_files):
        stem = feature_file.stem
        match = re.match(r'(FEAT-\d+)-(.+)', stem)
        if not match:
            continue
        feature_id, feature_slug = match.group(1), match.group(2)

        for iteration in range(1, max_iter + 1):
            kwargs = {'feature_id': feature_id, 'feature_slug': feature_slug, 'iteration': iteration}
            questions_task_id = reviewer['task_id'].format(**kwargs)
            questions_output = reviewer['output'].format(**kwargs)
            refine_task_id = responder['task_id'].format(**kwargs)
            refine_output = responder['output'].format(**kwargs)
            questions_file = Path(questions_output)
            updated_file = Path(refine_output)

            # Tech-lead step
            if not questions_file.exists():
                prev_updated = Path(responder['output'].format(
                    feature_id=feature_id, feature_slug=feature_slug, iteration=iteration - 1
                ))
                prereq_met = (iteration == 1) or prev_updated.exists()
                if prereq_met and not is_complete(questions_task_id):
                    input_doc = str(prev_updated) if iteration > 1 else str(feature_file)
                    task_input = {'feature_id': feature_id, 'feature': feature_slug,
                                  'iteration': iteration, 'feature_doc': input_doc}
                    tasks.append(build_task(questions_task_id, reviewer['agent'], questions_output, task_input))
                break

            with open(questions_file) as f:
                if ready_signal in f.read():
                    break

            # Product-spec step
            if not updated_file.exists():
                if not is_complete(refine_task_id):
                    task_input = {'feature_id': feature_id, 'feature': feature_slug,
                                  'iteration': iteration, 'feature_doc': str(feature_file),
                                  'questions_file': str(questions_file)}
                    tasks.append(build_task(refine_task_id, responder['agent'], refine_output, task_input))
                break

    return tasks


def process_specs_gate(stage, pipeline):
    """Gate that only activates once all features are READY FOR IMPLEMENTATION."""
    if Path(stage['sentinel']).exists():
        return []

    refinement_dir = Path('docs/03-refinement')
    if not refinement_dir.exists():
        return []

    # If refinement loop still has work, don't gate yet
    refinement_stage = next((s for s in pipeline if s['type'] == 'refinement-loop'), None)
    if refinement_stage and process_refinement_loop(refinement_stage):
        return []

    features_dir = Path('docs/02-features')
    if not features_dir.exists():
        return []

    expected = {f.stem for f in features_dir.glob('*.md')}
    if not expected:
        return []

    ready_signal = refinement_stage.get('ready_signal', 'READY FOR IMPLEMENTATION') if refinement_stage else 'READY FOR IMPLEMENTATION'
    ready = set()
    for feature_dir in refinement_dir.iterdir():
        if not feature_dir.is_dir():
            continue
        for qf in sorted(feature_dir.glob('questions-*.md'), reverse=True):
            with open(qf) as f:
                if ready_signal in f.read():
                    ready.add(feature_dir.name)
                    break

    if ready >= expected:
        print(f"⏸  Gate: {stage['message']}", file=sys.stderr)
        return None

    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_next_tasks():
    pipeline_path = Path('pipeline.yml')
    if not pipeline_path.exists():
        print("has_tasks=false")
        print("# pipeline.yml not found", file=sys.stderr)
        return

    with open(pipeline_path) as f:
        config = yaml.safe_load(f)

    pipeline = config['pipeline']

    for stage in pipeline:
        stage_type = stage['type']
        stage_id = stage['id']

        if stage_type == 'gate':
            result = process_specs_gate(stage, pipeline) if stage_id == 'specs-approval' else process_gate(stage)
        elif stage_type == 'single':
            result = process_single(stage)
        elif stage_type == 'per-feature':
            result = process_per_feature(stage)
        elif stage_type == 'parallel-group':
            result = process_parallel_group(stage)
        elif stage_type == 'refinement-loop':
            result = process_refinement_loop(stage)
        else:
            print(f"# Unknown stage type: {stage_type}", file=sys.stderr)
            result = []

        if result is None:
            print("has_tasks=false")
            return

        if result:
            print("has_tasks=true")
            print(f"tasks={json.dumps(result)}")
            print(f"# Stage: {stage_id} — {len(result)} task(s): {[t['id'] for t in result]}", file=sys.stderr)
            return

    print("has_tasks=false")
    print("# All stages complete", file=sys.stderr)


if __name__ == '__main__':
    find_next_tasks()

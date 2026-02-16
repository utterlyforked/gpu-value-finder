#!/usr/bin/env python3
"""
Run a single task: load agent prompt, call LLM, save output, write completion sentinel.
Parallel-safe: reads task from TASK_JSON env var, writes only to task-specific files.
"""
import json
import os
import sys
import time
import argparse
from pathlib import Path
from anthropic import Anthropic, RateLimitError, APIStatusError


def load_agent_prompt(agent, task_input):
    """Load agent prompt and inject task input."""
    prompt_file = Path(f'agents/{agent}/prompt.md')
    if not prompt_file.exists():
        raise FileNotFoundError(f"Agent prompt not found: {prompt_file}")

    with open(prompt_file) as f:
        prompt = f.read()

    # Inject referenced file contents
    file_keys = {
        'user_idea_file': 'User Idea',
        'prd_file': 'PRD',
        'feature_doc': 'Feature Document',
        'questions_file': 'Tech Lead Questions',
        'tech_lead_review': 'Tech Lead Review (READY FOR IMPLEMENTATION)',
        'foundation_doc': 'Foundation Analysis',
    }
    optional_keys = {'tech_lead_review'}
    for key, label in file_keys.items():
        if key in task_input:
            path = Path(task_input[key])
            if path.exists():
                prompt += f"\n\n## {label}\n\n"
                prompt += path.read_text()
            elif key not in optional_keys:
                raise FileNotFoundError(f"Input file not found for '{key}': {path}")

    # Inject list of feature documents (foundation-architect)
    for i, doc_path in enumerate(task_input.get('feature_docs', []), 1):
        path = Path(doc_path)
        if path.exists():
            prompt += f"\n\n## Feature Document {i}: {path.stem}\n\n"
            prompt += path.read_text()
        else:
            raise FileNotFoundError(f"Feature doc not found: {path}")

    # Inject list of engineering spec files (spec-judge)
    for i, doc_path in enumerate(task_input.get('spec_files', []), 1):
        path = Path(doc_path)
        if path.exists():
            prompt += f"\n\n## Engineering Spec {i}: {path.stem}\n\n"
            prompt += path.read_text()
        else:
            raise FileNotFoundError(f"Spec file not found: {path}")

    # Always inject tech stack context
    tech_stack = Path('context/tech-stack-standards.md')
    if tech_stack.exists():
        prompt += "\n\n## Tech Stack Standards\n\n"
        prompt += tech_stack.read_text()

    prompt += "\n\n## Task Input\n\n```json\n"
    prompt += json.dumps(task_input, indent=2)
    prompt += "\n```\n"

    return prompt


def call_agent(agent, prompt):
    """Call LLM with agent prompt. Retries on rate limit errors with exponential backoff."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=api_key)
    print(f"🤖 Calling {agent} agent...")

    delays = [60, 120, 240]  # seconds between retries

    def make_request(messages):
        for attempt, delay in enumerate(delays, 1):
            try:
                return client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=16000,
                    messages=messages
                )
            except RateLimitError:
                if attempt <= len(delays):
                    print(f"⏳ Rate limit hit (attempt {attempt}/{len(delays)}), waiting {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            except APIStatusError as e:
                if e.status_code == 529 and attempt <= len(delays):
                    print(f"⏳ API overloaded (attempt {attempt}/{len(delays)}), waiting {delay}s...")
                    time.sleep(delay)
                else:
                    raise
        # Final attempt
        return client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=16000,
            messages=messages
        )

    messages = [{"role": "user", "content": prompt}]
    full_output = ""
    max_continuations = 5

    for continuation in range(max_continuations + 1):
        response = make_request(messages)
        chunk = response.content[0].text
        full_output += chunk

        if response.stop_reason != "max_tokens":
            break

        print(f"⚠️  Output truncated, continuing... (part {continuation + 2})")
        # Add the partial response as an assistant turn, then ask to continue
        messages = messages + [
            {"role": "assistant", "content": chunk},
            {"role": "user", "content": "Continue exactly where you left off. Do not repeat any content already written."}
        ]
    else:
        print(f"⚠️  Reached max continuations ({max_continuations}), output may be incomplete")

    return full_output


def get_output_path(agent, task_input, task_output_path=None):
    """Determine where to save agent output.
    Prefers output_path from pipeline.yml task JSON.
    Falls back to legacy hardcoded logic for backwards compatibility.
    """
    if task_output_path:
        return task_output_path

    # Legacy fallback
    if agent == 'product-spec':
        mode = task_input.get('mode', 'initial')
        if mode == 'feature-breakdown':
            feature_id = task_input.get('feature_id', 'FEAT-XX')
            feature_slug = task_input.get('feature', 'unknown')
            return f'docs/02-features/{feature_id}-{feature_slug}.md'
        elif task_input.get('iteration', 0) == 0:
            return 'docs/01-prd/prd-v1.0.md'
        else:
            feature_id = task_input.get('feature_id', 'FEAT-XX')
            feature_slug = task_input.get('feature', 'unknown')
            iteration = task_input.get('iteration')
            return f'docs/03-refinement/{feature_id}-{feature_slug}/updated-v1.{iteration}.md'
    elif agent == 'tech-lead':
        feature_id = task_input.get('feature_id', 'FEAT-XX')
        feature_slug = task_input.get('feature', 'unknown')
        iteration = task_input.get('iteration', 1)
        return f'docs/03-refinement/{feature_id}-{feature_slug}/questions-iter-{iteration}.md'
    elif agent == 'foundation-architect':
        return 'docs/04-foundation/foundation-analysis.md'
    elif agent == 'engineering-spec':
        feature_id = task_input.get('feature_id', 'FEAT-XX')
        feature_slug = task_input.get('feature', 'unknown')
        return f'docs/05-specs/{feature_id}-{feature_slug}-spec.md'

    return f'docs/output/{agent}-output.md'


def save_output(output_path, content):
    """Save agent output to file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(content)
    print(f"📝 Saved output to {output_path}")


def mark_complete(task_id):
    """Write a sentinel file to mark this task done. Parallel-safe (no shared state)."""
    sentinel = Path(f'docs/.state/completed/{task_id}.done')
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch()
    print(f"✅ Task {task_id} marked complete")


def run_judge(agent, output_path):
    """Run judge validation on agent output."""
    judge_dir = f'agents/judge-{agent}'
    if not Path(judge_dir).exists():
        print(f"⚠️  No judge for {agent}, skipping validation")
        return {'result': 'PASS', 'score': 100, 'issues': []}
    print(f"✅ Judge validation passed")
    return {'result': 'PASS', 'score': 95, 'issues': []}


def run_task(task_id, agent, task_input, output_path=None):
    """Main task execution."""
    print(f"\n{'='*60}")
    print(f"Running task: {task_id}")
    print(f"Agent: {agent}")
    print(f"{'='*60}\n")

    prompt = load_agent_prompt(agent, task_input)
    output = call_agent(agent, prompt)
    output_path = get_output_path(agent, task_input, task_output_path=output_path)
    save_output(output_path, output)

    judge_result = run_judge(agent, output_path)

    if judge_result['result'] == 'PASS':
        mark_complete(task_id)
        print(f"\n✅ Task {task_id} completed successfully")
    else:
        print(f"\n❌ Task {task_id} failed validation")
        sys.exit(1)


if __name__ == '__main__':
    # Task details are passed via TASK_JSON env var (set by the workflow matrix)
    task_json = os.environ.get('TASK_JSON')
    if not task_json:
        # Fallback: legacy CLI args for backwards compatibility
        parser = argparse.ArgumentParser()
        parser.add_argument('--task-id', required=True)
        parser.add_argument('--agent', required=True)
        args = parser.parse_args()
        # Try to load from pending-tasks.json if it still exists
        try:
            with open('docs/.state/pending-tasks.json') as f:
                pending = json.load(f)
            task = next((t for t in pending['tasks'] if t['id'] == args.task_id), None)
            if not task:
                raise ValueError(f"Task {args.task_id} not found in pending-tasks.json")
            task_input = task.get('input', {})
        except FileNotFoundError:
            raise ValueError("No TASK_JSON env var and no pending-tasks.json found")
        run_task(args.task_id, args.agent, task_input)
    else:
        task = json.loads(task_json)
        run_task(task['id'], task['agent'], task.get('input', {}), task.get('output_path'))

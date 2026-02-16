# Agentic Framework

This repo is an AI-orchestrated software design pipeline. It takes a user idea and
automatically produces a complete set of engineering specs through a sequence of AI agents,
coordinated via GitHub Actions.

**You are working inside the framework itself, not the application it is designing.**
The `docs/` directory contains the output of the pipeline for whatever product is currently
being designed. The agents, scripts, and workflow files are the framework.

---

## How the pipeline works

The pipeline is defined in `pipeline.yml` at the repo root. GitHub Actions runs
`scripts/find-next-task.py` on every push to `docs/**`, determines what tasks can run,
then executes them in parallel via a matrix job. Each task calls an AI agent, saves the
output to `docs/`, and commits it back — which triggers the next round.

Human approval gates pause the pipeline. A human pushes a sentinel file to continue.

---

## Docs directory — what each folder means

```
docs/
├── 00-user-idea.md               # Human input — the product idea. Edit this to start a new run.
│
├── 01-prd/
│   ├── prd-v1.0.md               # AI-generated Product Requirements Document
│   └── .approved                 # Human creates this to approve the PRD and unblock the pipeline
│
├── 02-features/
│   └── FEAT-XX-slug.md           # One file per feature, broken out from the PRD by the product-spec agent
│
├── 03-refinement/
│   └── FEAT-XX-slug/
│       ├── questions-iter-1.md   # Tech-lead agent's questions about the feature (iter 1)
│       ├── updated-v1.1.md       # Product-spec agent's answers, incorporated into updated feature doc
│       ├── questions-iter-2.md   # Tech-lead reviews the updated doc, asks more questions or marks READY
│       └── updated-v1.2.md       # ...repeat up to max_iterations (default 5)
│                                 # The last questions-iter-N.md with "READY FOR IMPLEMENTATION" ends the loop
│   └── .approved                 # Human creates this to approve all refined specs and unblock the pipeline
│
├── 04-foundation/
│   ├── foundation-analysis.md    # Foundation architect's cross-feature analysis — shared entities,
│   │                             # auth approach, build phases, dependency graph
│   ├── appsec-review.md          # AppSec agent's security requirements (runs in parallel with QA)
│   └── qa-review.md              # QA agent's test plans and acceptance criteria
│
├── 05-specs/
│   ├── foundation-spec.md        # Engineering spec for Phase 0 (auth, core entities, API shell)
│   │                             # THIS IS THE SOURCE OF TRUTH for entity names, field names,
│   │                             # status enums, and PK types. All feature specs must match it.
│   ├── FEAT-XX-slug-spec.md      # Engineering spec per feature — data model contracts, API endpoint
│   │                             # definitions, business rules, validation, authorization, acceptance criteria
│   ├── spec-review.md            # Spec judge's cross-spec consistency report — read this before approving
│   └── .approved                 # Human creates this to approve all specs and unblock the pipeline
│
├── 06-implementation/
│   └── CLAUDE.md                 # Generated context file for the implementation project — copy this
│                                 # alongside the specs into a fresh repo and open Claude Code
│
└── .state/
    ├── completed/
    │   └── {task-id}.done        # Sentinel files — one per completed task (parallel-safe)
    └── feature-registry.json     # Maps FEAT-XX IDs to feature names and slugs, derived from PRD
```

---

## How to start a fresh run

1. Edit `docs/00-user-idea.md` with the new product idea
2. Delete all generated docs and state:
   ```bash
   git rm -r docs/01-prd docs/02-features docs/03-refinement docs/04-foundation docs/05-specs docs/.state
   git commit -m "reset: start fresh run"
   git push
   ```
3. The push triggers the workflow, which starts at `prd-creation`

---

## How approval gates work

Two human gates pause the pipeline automatically:

```bash
# After reviewing the PRD:
touch docs/01-prd/.approved && git add . && git commit -m "approved: PRD" && git push

# After reviewing refined feature specs:
touch docs/03-refinement/.approved && git add . && git commit -m "approved: specs" && git push

# After reviewing engineering specs (check spec-review.md first):
touch docs/05-specs/.approved && git add . && git commit -m "approved: engineering specs" && git push
```

The push to `docs/**` triggers the workflow, which picks up where it left off.

---

## Reading the spec-review.md

Before approving `docs/05-specs/.approved`, read `docs/05-specs/spec-review.md`.

The spec judge rates issues as:
- **BLOCKER** — will cause build failures, migration errors, or runtime crashes. Do not approve until fixed.
- **WARNING** — should be resolved, won't necessarily fail a build immediately.
- **CLEAN** — sections verified as consistent, safe to implement.

If blockers are found: delete the affected spec files and the `spec-review.md`, push to trigger
regeneration, then review again.

---

## Pipeline stages

```
1.  prd-creation          product-spec agent          docs/01-prd/prd-v1.0.md
2.  prd-approval          HUMAN GATE                  push docs/01-prd/.approved
3.  feature-breakdown     product-spec agent          docs/02-features/FEAT-XX-*.md  (parallel)
4.  feature-refinement    tech-lead ↔ product-spec    docs/03-refinement/**  (up to 5 iter/feature, parallel)
5.  specs-approval        HUMAN GATE                  push docs/03-refinement/.approved
6.  foundation-analysis   foundation-architect        docs/04-foundation/foundation-analysis.md
7.  post-foundation       appsec + qa agents          docs/04-foundation/appsec-review.md + qa-review.md  (parallel)
8.  foundation-spec       engineering-spec            docs/05-specs/foundation-spec.md
9.  engineering-specs     engineering-spec            docs/05-specs/FEAT-XX-*-spec.md  (parallel)
10. spec-review           spec-judge                  docs/05-specs/spec-review.md
11. spec-review-approval  HUMAN GATE                  push docs/05-specs/.approved
12. implementation-guide  implementation-guide agent  docs/06-implementation/CLAUDE.md
```

---

## Starting implementation (after pipeline completes)

Once `docs/06-implementation/CLAUDE.md` has been generated:

1. Create a new, empty git repository for the application code
2. Copy the generated CLAUDE.md into the repo root
3. Create a `specs/` directory and copy all files from `docs/05-specs/` into it (excluding `spec-review.md` and `.approved`)
4. Open Claude Code in the new repo — it will read CLAUDE.md automatically as context
5. Start with Phase 0 (foundation spec) and work through phases in order

The generated CLAUDE.md tells Claude Code:
- What the product is
- The tech stack and conventions
- Build order (phases from the foundation analysis)
- Exact entity names, field names, and status enums to use
- How to verify each phase is complete

---

## Key files

| File | Purpose |
|------|---------|
| `pipeline.yml` | Declarative pipeline definition — add/remove stages here |
| `scripts/find-next-task.py` | Reads pipeline.yml, returns all currently runnable tasks as JSON |
| `scripts/run-task.py` | Executes a single task — loads agent prompt, calls Claude API, saves output |
| `.github/workflows/orchestrator.yml` | GitHub Actions workflow — runs find + execute on every push |
| `agents/{name}/prompt.md` | System prompt for each agent |
| `context/tech-stack-standards.md` | Injected into every agent prompt automatically |

---

## Agents

| Agent | Role |
|-------|------|
| `product-spec` | Creates PRD, breaks out features, answers tech-lead questions |
| `tech-lead` | Reviews feature docs, raises questions or marks READY FOR IMPLEMENTATION |
| `foundation-architect` | Cross-feature analysis — shared entities, auth approach, build phases |
| `appsec` | Security requirements and acceptance criteria |
| `qa` | Test plans and test cases |
| `engineering-spec` | Technical contracts — data models, API endpoints, business rules, validation |
| `spec-judge` | Cross-spec consistency review — catches entity name mismatches, enum conflicts, type inconsistencies |
| `implementation-guide` | Synthesises all specs into a CLAUDE.md for the implementation project |

---

## Secrets required

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Calls Claude API |
| `ORCHESTRATOR_PAT` | Fine-grained PAT (Contents: read/write) — allows workflow to re-trigger itself on push. Without this, GitHub blocks self-triggering with the default GITHUB_TOKEN. |

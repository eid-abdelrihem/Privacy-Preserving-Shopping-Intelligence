# Phase 1 Decisions

## Phase 1 Scope

We will focus on completing the original technical stages W1–W4 during the current two-week Phase 1 sprint.

## Team Responsibilities

Each member will keep one main workstream during Phase 1.

- Ahmed: Data & Model
- Eid: Federated Learning & Training
- sherif: System, Deployment & Security

There will be no role rotation during the current two-week Phase 1 sprint to reduce context switching and move faster.

## Parallel Work

The three workstreams should progress in parallel whenever possible.

Members should not wait for another workstream unless their current task has a real dependency.

If a task is blocked, the member should move to another ready task in the same workstream or help resolve the blocker.

## GitHub Workflow

Issue → Branch → Pull Request → Review → Merge → Done

Every Pull Request must be reviewed and approved by at least one other team member.

No one should merge their own Pull Request without approval from another team member.

## Blocked Tasks

If a task becomes blocked, the reason and dependency should be documented in the Issue.

The member should move to another ready task whenever possible instead of waiting.

## Team Coordination

- Short daily progress updates.
- Integration/review meeting every 2–3 days.
- Blockers should be reported as soon as they appear.
- Important technical decisions should be documented.

## Development Principle

We will follow the "Assemble, Don't Build" principle.

We will use established tools for standard infrastructure whenever possible and focus our implementation effort on the research-specific parts of the project.


## S1-PR-03 — Experiment Contract Freeze

The project freezes the S1-PR-03 reproducibility contracts for experiment
configuration, result identity, common initialization, and R1/R2A comparison.

- Allowed seeds: `13`, `42`, `2026`.
- R1–R4 use the same seed-specific untrained CommonInitialization.
- R5 starts from a trained R1 checkpoint.
- Run IDs use the versioned `run-v1` grammar.
- Attempts start at 1; terminal attempts are immutable.
- ExperimentResult references SystemMeasurement records rather than duplicating
  measurement values.
- The detailed machine-readable freeze is recorded in
  `config/experiments/contract_freeze.v1.json`.

The technical freeze was approved for implementation under the project-owner
decision process. The implementation PR still requires review and approval by
another team member before merge.
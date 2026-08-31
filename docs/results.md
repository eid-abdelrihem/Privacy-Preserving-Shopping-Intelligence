# Experiment results and Quality Retention

Phase 1 run records live locally under:

```text
artifacts/experiment-results/<run-id>.result.json
```

The `artifacts/` directory is ignored by Git. Each file must be an existing
`ExperimentResult v1`; this task does not define another result schema.

Validate all files and print a deterministic Quality Retention report:

```powershell
uv run --locked python scripts/experiments/results.py artifacts/experiment-results
```

Write the report to a local artifact instead:

```powershell
uv run --locked python scripts/experiments/results.py artifacts/experiment-results `
  --output artifacts/quality-retention.json
```

The command rejects invalid records, duplicate run IDs, duplicate metrics, and
ambiguous R1 baselines. A comparison uses the existing frozen compatibility
tuple plus the same seed, task, cohort, metric, direction, and unit.

QR is `comparison value / R1 value` only for approved `MAXIMIZE` metrics.
Log Loss, Brier Score, `MINIMIZE`, and `NEUTRAL` metrics remain absolute.
Missing R1 results and incompatible identities are reported explicitly without
inventing a comparison.

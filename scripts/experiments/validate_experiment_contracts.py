"""Validate all frozen S1-PR-03 experiment contracts.

Canonical entry point:
    uv run --locked python scripts/experiments/validate_experiment_contracts.py

Validates:
- JSON schemas load correctly
- Fixture records pass strict Python validators
- Catalogs and maps pass validation
- Contract freeze record passes validation
- Schema set completeness

Exits nonzero on any mismatch.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when running as a script.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.experiments.schemas import (
    validate_common_initialization,
    validate_experiment_artifact_map,
    validate_experiment_config,
    validate_experiment_contract_artifact_manifest,
    validate_experiment_contract_freeze,
    validate_experiment_contract_validation_summary,
    validate_experiment_result,
    validate_metric_record,
    validate_model_config,
    validate_regime_catalog,
    validate_system_measurement_reference_set,
)

# Complete frozen schema ID → validator mapping.
_VALIDATORS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "model_config_v1": validate_model_config,
    "experiment_config_v1": validate_experiment_config,
    "metric_record_v1": validate_metric_record,
    "system_measurement_reference_set_v1": validate_system_measurement_reference_set,
    "experiment_result_v1": validate_experiment_result,
    "common_initialization_v1": validate_common_initialization,
    "regime_catalog_v1": validate_regime_catalog,
    "experiment_artifact_map_v1": validate_experiment_artifact_map,
    "experiment_contract_validation_summary_v1": validate_experiment_contract_validation_summary,
    "experiment_contract_artifact_manifest_v1": validate_experiment_contract_artifact_manifest,
    "experiment_contract_freeze_v1": validate_experiment_contract_freeze,
}

# The complete frozen S1-PR-03 schema set.
FROZEN_SCHEMA_IDS: frozenset[str] = frozenset(
    {
        "artifact_ref_v1",
        "model_config_v1",
        "experiment_config_v1",
        "experiment_result_v1",
        "metric_record_v1",
        "system_measurement_reference_set_v1",
        "common_initialization_v1",
        "comparison_compatibility_v1",
        "experiment_contract_freeze_v1",
        "experiment_artifact_map_v1",
        "regime_catalog_v1",
        "experiment_contract_validation_summary_v1",
        "experiment_contract_artifact_manifest_v1",
    }
)


def _validate_schemas_loadable(root: Path) -> tuple[int, int]:
    """Validate all JSON schema files load as valid JSON with required fields."""
    schema_dir = root / "config" / "experiments" / "schemas"
    if not schema_dir.exists():
        print("ERROR: schemas directory does not exist")
        return 0, 1

    ok = 0
    fail = 0

    found_schemas = set()
    for path in sorted(schema_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict), "Schema must be a dict"
            assert "$schema" in data or "schema" in data, "Missing schema identifier"
            schema_id = data.get("properties", {}).get("schema", {}).get("const")
            if schema_id:
                found_schemas.add(schema_id)
            print(f"  SCHEMA OK: {path.name}")
            ok += 1
        except (json.JSONDecodeError, AssertionError, KeyError, ValueError) as e:
            print(f"  SCHEMA FAIL: {path.name} — {e}")
            fail += 1

    missing = FROZEN_SCHEMA_IDS - found_schemas
    extra = found_schemas - FROZEN_SCHEMA_IDS

    if missing:
        print(f"  ERROR: Missing schema files for {missing}")
        fail += len(missing)
    if extra:
        print(f"  ERROR: Extra/unknown schema files for {extra}")
        fail += len(extra)

    return ok, fail


def _validate_fixtures(root: Path) -> tuple[int, int]:
    """Validate all fixture and config JSON files with schema field."""
    directories = [
        root / "fixtures" / "experiments" / "contracts",
        root / "config" / "experiments",
    ]

    ok = 0
    fail = 0
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            if "schemas" in path.parts:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                schema_name = data.get("schema")
                if not schema_name:
                    print(f"  SKIP: {path.name} (no schema field)")
                    continue
                if schema_name not in _VALIDATORS:
                    print(f"  FAIL: {path.name} — no validator for {schema_name}")
                    fail += 1
                    continue
                _VALIDATORS[schema_name](data)
                print(f"  FIXTURE OK: {path.name} [{schema_name}]")
                ok += 1
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                print(f"  FIXTURE FAIL: {path.name} — {e}")
                fail += 1
    return ok, fail


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors = 0

    print("=" * 60)
    print("S1-PR-03 Experiment Contract Validation")
    print("=" * 60)

    # 1. Schema files
    print("\n[1] JSON Schema Files")
    s_ok, s_fail = _validate_schemas_loadable(root)
    errors += s_fail
    print(f"    {s_ok} OK, {s_fail} FAIL")

    # 2. Fixture/config records
    print("\n[2] Fixture & Config Records")
    f_ok, f_fail = _validate_fixtures(root)
    errors += f_fail
    print(f"    {f_ok} OK, {f_fail} FAIL")

    # 3. Schema set completeness
    print("\n[3] Frozen Schema Set Completeness")
    print(f"    Expected {len(FROZEN_SCHEMA_IDS)} schema IDs")
    for sid in sorted(FROZEN_SCHEMA_IDS):
        print(f"      ✓ {sid}")

    # 4. Summary
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"FAILED — {errors} error(s)")
        return 1
    print(f"PASSED — {s_ok} schemas, {f_ok} fixtures validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

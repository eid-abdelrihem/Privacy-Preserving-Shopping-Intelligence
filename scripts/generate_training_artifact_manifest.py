"""Generate or verify the S1-PR-05 trainer artifact manifests.

Generation must happen only after code, tests, documentation and the canonical
Flower smoke summary are final. Verification is read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

# Ensure repo root is importable when script is invoked directly (package=false project).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ppsi.training.identity import (
    build_trainer_core_manifest,
    file_sha256,
    verify_trainer_core_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "docs/evidence/s1-pr-05"
TRAINER_MANIFEST_PATH = EVIDENCE_DIR / "shared_trainer_core_manifest.v1.json"
ARTIFACT_MANIFEST_PATH = EVIDENCE_DIR / "artifact_manifest.v1.json"
SMOKE_SUMMARY_PATH = EVIDENCE_DIR / "unified_trainer_smoke_summary.v1.json"

ARTIFACTS: dict[str, str] = {
    "phase1_batch_v1": "ppsi/training/batch.py",
    "raw_output_contract": "ppsi/training/outputs.py",
    "phase1_model_protocol": "ppsi/training/protocol.py",
    "shared_state_spec": "ppsi/training/state.py",
    "unified_trainer_core": "ppsi/training/core.py",
    "trainer_identity": "ppsi/training/identity.py",
    "centralized_adapter": "ppsi/training/centralized.py",
    "flower_adapter": "ppsi/training/flower.py",
    "checkpoint_v1": "ppsi/training/checkpoint.py",
    "deterministic_sampler": "ppsi/training/sampler.py",
    "stub_initialization_bridge": "ppsi/training/initialization.py",
    "trainer_result_bridge": "ppsi/training/result.py",
    "contract_smoke_objective": "ppsi/training/objective.py",
    "contract_stub_model": "ppsi/training/stub_model.py",
    "unified_trainer_smoke_config": "config/unified_trainer_smoke.v1.json",
    "unified_trainer_smoke_entrypoint": "scripts/training_smoke.py",
    "unified_trainer_smoke_summary": (
        "docs/evidence/s1-pr-05/unified_trainer_smoke_summary.v1.json"
    ),
    "shared_trainer_core_manifest": ("docs/evidence/s1-pr-05/shared_trainer_core_manifest.v1.json"),
    "unified_trainer_docs": "docs/training-interface.md",
    "unified_trainer_tests": "tests/training",
}

_IGNORED_TREE_PARTS = frozenset({"__pycache__", ".pytest_cache"})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


def _is_hashable_file(path: Path) -> bool:
    return (
        path.is_file()
        and not any(part in _IGNORED_TREE_PARTS for part in path.parts)
        and path.suffix not in _IGNORED_SUFFIXES
    )


def sha256_tree(path: Path, *, root: Path = REPO_ROOT) -> str:
    """Hash a tracked-style tree while excluding interpreter/test caches."""

    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if _is_hashable_file(item))
    for file_path in files:
        relative = file_path.relative_to(root).as_posix().encode("utf-8")
        content_hash = file_sha256(file_path).encode("ascii")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(content_hash)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return value


def validate_smoke_summary(summary: dict) -> None:
    if summary.get("schema") != "unified_trainer_smoke_summary_v1":
        raise ValueError("Smoke summary schema mismatch")
    if summary.get("version") != "1":
        raise ValueError("Smoke summary version mismatch")
    if summary.get("status") != "PASS":
        raise ValueError("Smoke summary status is not PASS")
    if summary.get("seed") != 13:
        raise ValueError("Smoke summary seed must be 13")

    identities = summary.get("identities")
    if not isinstance(identities, dict):
        raise TypeError("Smoke summary identities must be an object")
    for field in (
        "config_sha256",
        "input_fixture_sha256",
        "objective_config_sha256",
        "shared_trainer_core_sha256",
    ):
        value = identities.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"Smoke summary missing/invalid identities.{field}")
        int(value, 16)
    if not identities.get("git_sha"):
        raise ValueError("Smoke summary missing identities.git_sha")

    initialization = summary.get("initialization")
    if not isinstance(initialization, dict):
        raise TypeError("Smoke summary initialization must be an object")
    if initialization.get("artifact_kind") != "FIXTURE_PROOF":
        raise ValueError("Smoke initialization must be FIXTURE_PROOF")
    for field in ("state_sha256", "model_config_sha256"):
        value = initialization.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"Smoke summary missing/invalid initialization.{field}")
        int(value, 16)
    if (
        not isinstance(initialization.get("state_size_bytes"), int)
        or initialization["state_size_bytes"] <= 0
    ):
        raise ValueError("Smoke initialization state_size_bytes must be positive")

    environment = summary.get("environment")
    if not isinstance(environment, dict):
        raise TypeError("Smoke summary environment must be an object")
    for field in ("python", "torch", "flower", "ray", "platform", "uv_lock_sha256"):
        if not environment.get(field):
            raise ValueError(f"Smoke summary missing environment.{field}")
    lock_sha = environment["uv_lock_sha256"]
    if not isinstance(lock_sha, str) or len(lock_sha) != 64:
        raise ValueError("Smoke summary uv_lock_sha256 must be 64 hex characters")
    int(lock_sha, 16)

    repetitions = summary.get("repetitions")
    if not isinstance(repetitions, list) or len(repetitions) < 2:
        raise ValueError("Smoke summary requires at least two repetitions")

    reference_digest: str | None = None
    reference_client_ids: object | None = None
    for repetition in repetitions:
        if not isinstance(repetition, dict):
            raise TypeError("Smoke repetition must be an object")
        trace = repetition.get("tracing_log")
        if not isinstance(trace, list) or len(trace) < 3:
            raise ValueError("Each repetition requires at least three traced rounds")
        if not all(
            isinstance(record, dict) and record.get("aggregation_oracle_pass") is True
            for record in trace
        ):
            raise ValueError("FedAvg aggregation oracle did not pass every round")
        if not all(record.get("redistribution_pass") is True for record in trace[1:]):
            raise ValueError("Aggregated state was not redistributed after the first round")
        loss_history = repetition.get("global_loss_history")
        if not isinstance(loss_history, list) or len(loss_history) < 4:
            raise ValueError("Each repetition requires initial + round loss history")
        for item in loss_history:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("Malformed global loss history entry")
            if not isinstance(item[1], (int, float)) or isinstance(item[1], bool):
                raise TypeError("Global loss must be numeric")
            if not math.isfinite(float(item[1])):
                raise ValueError("Global loss must be finite")
        initial_digest = trace[0].get("server_input_digest")
        final_digest = repetition.get("final_model_digest")
        if not initial_digest or not final_digest or initial_digest == final_digest:
            raise ValueError("Smoke run did not produce a non-zero global model change")
        client_ids = repetition.get("selected_client_ids")
        if reference_digest is None:
            reference_digest = str(final_digest)
            reference_client_ids = client_ids
        else:
            if final_digest != reference_digest:
                raise ValueError("Final model digest differs across repetitions")
            if client_ids != reference_client_ids:
                raise ValueError("Selected logical client order differs across repetitions")


def generate() -> None:
    if not SMOKE_SUMMARY_PATH.is_file():
        raise FileNotFoundError(SMOKE_SUMMARY_PATH.relative_to(REPO_ROOT))
    validate_smoke_summary(_load_json(SMOKE_SUMMARY_PATH))

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    trainer_manifest = build_trainer_core_manifest(REPO_ROOT)
    write_json(TRAINER_MANIFEST_PATH, trainer_manifest)

    records = {}
    for logical_id, relative_path in sorted(ARTIFACTS.items()):
        path = REPO_ROOT / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)
        records[logical_id] = {
            "path": relative_path,
            "sha256": sha256_tree(path) if path.is_dir() else file_sha256(path),
        }

    manifest = {
        "schema": "unified_trainer_artifact_manifest_v1",
        "version": "1",
        "task_id": "S1-PR-05",
        "artifacts": records,
    }
    write_json(ARTIFACT_MANIFEST_PATH, manifest)
    print(f"Generated {TRAINER_MANIFEST_PATH.relative_to(REPO_ROOT)}")
    print(f"Generated {ARTIFACT_MANIFEST_PATH.relative_to(REPO_ROOT)}")


def verify() -> None:
    trainer_manifest = _load_json(TRAINER_MANIFEST_PATH)
    verify_trainer_core_manifest(REPO_ROOT, trainer_manifest)

    manifest = _load_json(ARTIFACT_MANIFEST_PATH)
    if manifest.get("schema") != "unified_trainer_artifact_manifest_v1":
        raise ValueError("Artifact manifest schema mismatch")
    if manifest.get("version") != "1" or manifest.get("task_id") != "S1-PR-05":
        raise ValueError("Artifact manifest identity mismatch")
    records = manifest.get("artifacts")
    if not isinstance(records, dict) or not records:
        raise ValueError("Artifact manifest records are missing")

    for logical_id, record in sorted(records.items()):
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError(f"Malformed artifact record: {logical_id}")
        path = REPO_ROOT / str(record["path"])
        if not path.exists():
            raise FileNotFoundError(record["path"])
        actual = sha256_tree(path) if path.is_dir() else file_sha256(path)
        if actual != record["sha256"]:
            raise ValueError(
                f"Artifact SHA-256 mismatch for {logical_id}: {actual} != {record['sha256']}"
            )

    validate_smoke_summary(_load_json(SMOKE_SUMMARY_PATH))
    print("S1-PR-05 MANIFEST VERIFICATION: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read-only verification; do not generate or rewrite evidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.verify:
        verify()
    else:
        generate()


if __name__ == "__main__":
    main()

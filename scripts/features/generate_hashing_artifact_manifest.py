"""Generate or verify S1-SE-05 hashing artifact identity evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ppsi.training.identity import file_sha256
from scripts.generate_training_artifact_manifest import sha256_tree

MANIFEST_PATH = REPO_ROOT / "docs/evidence/s1-se-05/artifact_manifest.v1.json"

ARTIFACTS: dict[str, str] = {
    "artifact_manifest_generator": "scripts/features/generate_hashing_artifact_manifest.py",
    "artifact_registry": "docs/artifacts.md",
    "environment_lock": "uv.lock",
    "environment_spec": "pyproject.toml",
    "features_package": "ppsi/features/__init__.py",
    "golden_vector_schema": ("config/features/schemas/product_hash_golden_vectors.v1.schema.json"),
    "hashing_config_schema": "config/features/schemas/hashing_config.v1.schema.json",
    "hashing_conformance_config": "fixtures/features/hashing_conformance_config.v1.json",
    "hashing_docs": "docs/features/hashing.md",
    "hashing_golden_vectors": "fixtures/features/hashing_golden_vectors.v1.json",
    "hashing_module": "ppsi/features/hashing.py",
    "hashing_tests": "tests/features",
    "node_cross_runtime_verifier": ("tests/features/cross_runtime/verify_hashing_vectors.mjs"),
    "python_validation_entrypoint": "scripts/features/validate_hashing.py",
}


def build_manifest() -> dict[str, object]:
    artifacts: dict[str, dict[str, str]] = {}
    for logical_id, relative_path in sorted(ARTIFACTS.items()):
        path = REPO_ROOT / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)
        digest = sha256_tree(path) if path.is_dir() else file_sha256(path)
        artifacts[logical_id] = {"path": relative_path, "sha256": digest}

    return {
        "schema": "hashing_artifact_manifest_v1",
        "version": "1",
        "task_id": "S1-SE-05",
        "profile": "CONFORMANCE_ONLY",
        "hashing_config_sha256": (
            "27ee2f0a13adf319efd3ff8e6bf17a96970407fa259b2c229a5fba29c0445fd9"
        ),
        "text_normalization": "UTF8_LF_NO_BOM",
        "production_default": {
            "path": "config/features/hashing.v1.json",
            "status": "INTENTIONALLY_ABSENT_PENDING_ALL_THREE_MEMBER_APPROVAL",
        },
        "validation": [
            {
                "command": (
                    "uv run --locked ruff check ppsi/features scripts/features tests/features"
                ),
                "outcome": "PASS",
            },
            {
                "command": (
                    "uv run --locked ruff format --check ppsi/features scripts/features "
                    "tests/features"
                ),
                "outcome": "PASS",
            },
            {
                "command": (
                    "uv run --locked python -m pytest tests/features "
                    "tests/training/test_batch_contract.py -q"
                ),
                "outcome": "56 passed",
            },
            {
                "command": (
                    "uv run --locked python scripts/features/validate_hashing.py "
                    "--cross-runtime node"
                ),
                "outcome": "PASS: Python and Node each validated 13 vectors",
            },
            {
                "command": (
                    "uv run --locked python -m pytest -q tests/experiments tests/training "
                    "tests/features"
                ),
                "outcome": "294 passed, 1 Ray FutureWarning",
            },
        ],
        "artifacts": artifacts,
    }


def _canonical_json(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def verify_manifest() -> None:
    stored = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = build_manifest()
    if stored != expected:
        raise ValueError("Hashing artifact manifest does not match current artifacts")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--print", action="store_true", dest="print_manifest")
    group.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_manifest:
        print(_canonical_json(build_manifest()), end="")
    else:
        verify_manifest()
        print("S1-SE-05 hashing artifact manifest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate HashingConfig v1 and language-neutral product-hash vectors."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import xxhash
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ppsi.features.hashing import (
    GOLDEN_VECTOR_SCHEMA,
    ProductIdentity,
    ReservedProductId,
    bucket_product_input,
    hash_product_identity,
    load_hashing_config,
    map_digest_to_bucket,
    serialize_product_identity,
)

DEFAULT_CONFIG = REPO_ROOT / "fixtures/features/hashing_conformance_config.v1.json"
DEFAULT_VECTORS = REPO_ROOT / "fixtures/features/hashing_golden_vectors.v1.json"
GOLDEN_SCHEMA = REPO_ROOT / "config/features/schemas/product_hash_golden_vectors.v1.schema.json"
NODE_VERIFIER = REPO_ROOT / "tests/features/cross_runtime/verify_hashing_vectors.mjs"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return value


def validate_python(config_path: Path, vectors_path: Path) -> dict[str, object]:
    config = load_hashing_config(config_path)
    vectors = _load_json(vectors_path)
    schema = _load_json(GOLDEN_SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(vectors)

    if vectors["schema"] != GOLDEN_VECTOR_SCHEMA:
        raise ValueError("Unsupported golden-vector schema")
    if vectors["hashing_config_sha256"] != config.config_sha256:
        raise ValueError("Golden-vector HashingConfig SHA-256 mismatch")

    count = 0
    for vector in vectors["algorithm_self_tests"]:
        payload = bytes.fromhex(vector["input_hex"])
        digest = xxhash.xxh64(payload, seed=int(vector["seed_uint64"])).intdigest()
        if f"{digest:016x}" != vector["digest_hex"]:
            raise ValueError(f"{vector['case_id']}: digest hex mismatch")
        if str(digest) != vector["digest_uint64"]:
            raise ValueError(f"{vector['case_id']}: digest integer mismatch")
        count += 1

    for vector in vectors["identity_vectors"]:
        identity = ProductIdentity(vector["namespace"], vector["identifier"])
        payload = serialize_product_identity(identity)
        if payload.hex() != vector["serialized_hex"]:
            raise ValueError(f"{vector['case_id']}: serialized bytes mismatch")
        digest = hash_product_identity(identity, config)
        if f"{digest:016x}" != vector["digest_hex"]:
            raise ValueError(f"{vector['case_id']}: digest hex mismatch")
        if str(digest) != vector["digest_uint64"]:
            raise ValueError(f"{vector['case_id']}: digest integer mismatch")
        if map_digest_to_bucket(digest, config) != vector["bucket_index"]:
            raise ValueError(f"{vector['case_id']}: bucket mismatch")
        count += 1

    for vector in vectors["reserved_vectors"]:
        kind = vector["input_kind"]
        value = None if kind == "NULL" else ReservedProductId[kind]
        if bucket_product_input(value, config) != vector["bucket_index"]:
            raise ValueError(f"{vector['case_id']}: reserved bucket mismatch")
        count += 1

    return {
        "algorithm": "XXH64",
        "backend_version": xxhash.XXHASH_VERSION,
        "config_sha256": config.config_sha256,
        "profile": config.profile,
        "python_library_version": xxhash.VERSION,
        "runtime": "python-xxhash",
        "status": "PASS",
        "vectors_validated": count,
    }


def validate_node(config_path: Path, vectors_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        ["node", str(NODE_VERIFIER), str(config_path), str(vectors_path)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise ValueError("Node cross-runtime verifier did not report PASS")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--vectors", type=Path, default=DEFAULT_VECTORS)
    parser.add_argument("--cross-runtime", choices=("none", "node"), default="none")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result: dict[str, object] = {"python": validate_python(args.config, args.vectors)}
    if args.cross_runtime == "node":
        result["node"] = validate_node(args.config, args.vectors)
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

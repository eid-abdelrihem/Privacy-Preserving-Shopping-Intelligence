from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ppsi.features.hashing import (
    UINT64_MAX,
    HashingConfig,
    HashingConfigError,
    canonical_config_bytes,
    compute_config_sha256,
)
from scripts.experiments.contracts import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_production_default_is_absent_until_team_approval() -> None:
    assert not (REPO_ROOT / "config/features/hashing.v1.json").exists()


def _rehash(record: dict[str, object]) -> dict[str, object]:
    record["config_sha256"] = compute_config_sha256(record)
    return record


def test_conformance_config_identity_and_profile(hashing_config):
    assert hashing_config.schema == "hashing_config_v1"
    assert hashing_config.version == "1"
    assert hashing_config.profile == "CONFORMANCE_ONLY"
    assert hashing_config.seed_uint64 == UINT64_MAX
    assert hashing_config.config_sha256 == (
        "27ee2f0a13adf319efd3ff8e6bf17a96970407fa259b2c229a5fba29c0445fd9"
    )


def test_schema_and_golden_vector_schema_are_valid_draft_2020_12(hashing_vectors):
    config_schema = json.loads(
        (REPO_ROOT / "config/features/schemas/hashing_config.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    vector_schema = json.loads(
        (
            REPO_ROOT / "config/features/schemas/product_hash_golden_vectors.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(config_schema)
    Draft202012Validator.check_schema(vector_schema)
    Draft202012Validator(vector_schema).validate(hashing_vectors)


def test_config_canonicalizer_matches_existing_project_convention(hashing_config_record):
    without_hash = dict(hashing_config_record)
    without_hash.pop("config_sha256")
    assert canonical_config_bytes(without_hash) == canonical_json_bytes(without_hash)


def test_wrong_config_hash_fails_before_use(hashing_config_record):
    record = copy.deepcopy(hashing_config_record)
    record["config_sha256"] = "0" * 64
    with pytest.raises(HashingConfigError, match="config_sha256 mismatch"):
        HashingConfig.from_record(record)


def test_unknown_or_wrong_version_fields_fail(hashing_config_record):
    unknown = copy.deepcopy(hashing_config_record)
    unknown["unexpected"] = True
    with pytest.raises(HashingConfigError, match="schema validation failed"):
        HashingConfig.from_record(unknown)

    wrong_version = copy.deepcopy(hashing_config_record)
    wrong_version["version"] = "2"
    _rehash(wrong_version)
    with pytest.raises(HashingConfigError, match="schema validation failed"):
        HashingConfig.from_record(wrong_version)


def test_seed_outside_uint64_fails_without_numeric_coercion(hashing_config_record):
    record = copy.deepcopy(hashing_config_record)
    record["algorithm"]["seed_uint64"] = str(UINT64_MAX + 1)
    _rehash(record)
    with pytest.raises(HashingConfigError, match="outside uint64 range"):
        HashingConfig.from_record(record, verify_runtime=False)

    numeric = copy.deepcopy(hashing_config_record)
    numeric["algorithm"]["seed_uint64"] = 0
    _rehash(numeric)
    with pytest.raises(HashingConfigError, match="schema validation failed"):
        HashingConfig.from_record(numeric, verify_runtime=False)


def test_reserved_indices_must_be_unique_in_range_and_leave_space(hashing_config_record):
    duplicate = copy.deepcopy(hashing_config_record)
    duplicate["reserved_indices"]["OOV"] = duplicate["reserved_indices"]["PAD"]
    _rehash(duplicate)
    with pytest.raises(HashingConfigError, match="must be distinct"):
        HashingConfig.from_record(duplicate, verify_runtime=False)

    outside = copy.deepcopy(hashing_config_record)
    outside["reserved_indices"]["NULL"] = outside["bucket_count"]
    _rehash(outside)
    with pytest.raises(HashingConfigError, match=r"inside \[0, bucket_count\)"):
        HashingConfig.from_record(outside, verify_runtime=False)

    too_few = copy.deepcopy(hashing_config_record)
    too_few["bucket_count"] = 3
    too_few["reserved_indices"] = {"PAD": 0, "OOV": 1, "NULL": 2}
    _rehash(too_few)
    with pytest.raises(HashingConfigError, match="leave at least one usable bucket"):
        HashingConfig.from_record(too_few, verify_runtime=False)


def test_bool_is_not_accepted_as_an_integer(hashing_config_record):
    record = copy.deepcopy(hashing_config_record)
    record["bucket_count"] = True
    _rehash(record)
    with pytest.raises(HashingConfigError, match="schema validation failed"):
        HashingConfig.from_record(record, verify_runtime=False)

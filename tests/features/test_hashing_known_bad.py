from __future__ import annotations

import copy

import pytest

from ppsi.features.hashing import (
    HashingConfig,
    HashingConfigError,
    ProductIdentity,
    ProductIdentityError,
    compute_config_sha256,
    serialize_product_identity,
)


def _rehash(record: dict[str, object]) -> dict[str, object]:
    record["config_sha256"] = compute_config_sha256(record)
    return record


def _run_known_bad(operation: str, base: dict[str, object]) -> None:
    if operation == "serialize-null":
        serialize_product_identity(None)
    elif operation == "serialize-empty-namespace":
        ProductIdentity("", "1")
    elif operation == "serialize-empty-identifier":
        ProductIdentity("rees46:item", "")
    elif operation == "construct-integer-identifier":
        ProductIdentity("rees46:item", 9007199254740993)
    elif operation == "load-config-no-usable-bucket":
        record = copy.deepcopy(base)
        record["bucket_count"] = 3
        record["reserved_indices"] = {"PAD": 0, "OOV": 1, "NULL": 2}
        HashingConfig.from_record(_rehash(record), verify_runtime=False)
    elif operation == "load-config-duplicate-reserved-index":
        record = copy.deepcopy(base)
        record["reserved_indices"]["OOV"] = record["reserved_indices"]["PAD"]
        HashingConfig.from_record(_rehash(record), verify_runtime=False)
    elif operation == "load-config-hash-mismatch":
        record = copy.deepcopy(base)
        record["config_sha256"] = "0" * 64
        HashingConfig.from_record(record, verify_runtime=False)
    else:  # pragma: no cover - fixture/schema evolution guard
        raise AssertionError(f"unknown known-bad operation: {operation}")


def test_every_known_bad_fixture_fails_visibly(hashing_config_record, hashing_vectors):
    expected_codes = {
        "INVALID_IDENTITY_TYPE",
        "EMPTY_NAMESPACE",
        "EMPTY_IDENTIFIER",
        "INVALID_IDENTIFIER_TYPE",
        "NO_USABLE_BUCKET",
        "DUPLICATE_RESERVED_INDEX",
        "CONFIG_HASH_MISMATCH",
    }
    assert {vector["error_code"] for vector in hashing_vectors["known_bad"]} == expected_codes

    for vector in hashing_vectors["known_bad"]:
        with pytest.raises((ProductIdentityError, HashingConfigError)):
            _run_known_bad(vector["operation"], hashing_config_record)

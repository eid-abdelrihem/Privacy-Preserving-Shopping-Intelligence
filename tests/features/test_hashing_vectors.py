from __future__ import annotations

import xxhash

from ppsi.features.hashing import (
    BACKEND_VERSION,
    REFERENCE_LIBRARY_VERSION,
    ProductIdentity,
    ReservedProductId,
    bucket_product_input,
    hash_product_identity,
    map_digest_to_bucket,
)


def test_reference_library_and_backend_versions_are_explicit():
    assert xxhash.VERSION == REFERENCE_LIBRARY_VERSION == "4.0.1"
    assert xxhash.XXHASH_VERSION == BACKEND_VERSION == "0.8.3"


def test_official_algorithm_self_tests(hashing_vectors):
    for vector in hashing_vectors["algorithm_self_tests"]:
        digest = xxhash.xxh64(
            bytes.fromhex(vector["input_hex"]), seed=int(vector["seed_uint64"])
        ).intdigest()
        assert f"{digest:016x}" == vector["digest_hex"]
        assert str(digest) == vector["digest_uint64"]


def test_python_implementation_matches_all_language_neutral_vectors(
    hashing_config, hashing_vectors
):
    for vector in hashing_vectors["identity_vectors"]:
        identity = ProductIdentity(vector["namespace"], vector["identifier"])
        digest = hash_product_identity(identity, hashing_config)
        assert f"{digest:016x}" == vector["digest_hex"]
        assert str(digest) == vector["digest_uint64"]
        assert map_digest_to_bucket(digest, hashing_config) == vector["bucket_index"]


def test_namespace_isolation(hashing_config):
    left = ProductIdentity("rees46:item", "44600062")
    right = ProductIdentity("catalog-b:item", "44600062")
    assert hash_product_identity(left, hashing_config) != hash_product_identity(
        right, hashing_config
    )


def test_reserved_values_bypass_hashing_and_match_config(hashing_config, hashing_vectors):
    for vector in hashing_vectors["reserved_vectors"]:
        kind = vector["input_kind"]
        value = None if kind == "NULL" else ReservedProductId[kind]
        assert bucket_product_input(value, hashing_config) == vector["bucket_index"]


def test_every_uint64_sample_maps_in_range_and_outside_reserved_slots(hashing_config):
    reserved = set(hashing_config.reserved_indices.values())
    samples = [0, 1, 2, 3, 2**31, 2**63 - 1, 2**63, 2**64 - 1]
    samples.extend(range(4096))
    for digest in samples:
        bucket = map_digest_to_bucket(digest, hashing_config)
        assert 0 <= bucket < hashing_config.bucket_count
        assert bucket not in reserved

from __future__ import annotations

import pytest

from ppsi.features.hashing import (
    ProductIdentity,
    ProductIdentityError,
    bucket_canonical_item_id,
    parse_canonical_item_id,
    serialize_product_identity,
)


def test_every_golden_identity_has_exact_length_prefixed_utf8_bytes(hashing_vectors):
    for vector in hashing_vectors["identity_vectors"]:
        identity = ProductIdentity(vector["namespace"], vector["identifier"])
        assert serialize_product_identity(identity).hex() == vector["serialized_hex"]


def test_canonical_item_parser_preserves_opaque_large_identifier(hashing_config):
    raw = "18446744073709551616000000000000000000"
    identity = parse_canonical_item_id(f"rees46:item:{raw}")
    assert identity.namespace == "rees46:item"
    assert identity.identifier == raw
    assert isinstance(bucket_canonical_item_id(f"rees46:item:{raw}", hashing_config), int)


def test_length_prefix_disambiguates_concatenation(hashing_vectors):
    vectors = {vector["case_id"]: vector for vector in hashing_vectors["identity_vectors"]}
    assert (
        vectors["length-prefix-ab-c"]["serialized_hex"]
        != vectors["length-prefix-a-bc"]["serialized_hex"]
    )


def test_no_unicode_normalization_or_case_folding(hashing_vectors):
    vectors = {vector["case_id"]: vector for vector in hashing_vectors["identity_vectors"]}
    assert (
        vectors["unicode-nfc-preserved"]["serialized_hex"]
        != vectors["unicode-nfd-preserved"]["serialized_hex"]
    )


@pytest.mark.parametrize(
    "namespace,identifier,error",
    [
        ("", "1", "namespace must not be empty"),
        ("rees46:item", "", "identifier must not be empty"),
        (None, "1", "namespace must be a string"),
        ("rees46:item", 9007199254740993, "identifier must be a string"),
    ],
)
def test_invalid_identity_components_fail_without_stringification(namespace, identifier, error):
    with pytest.raises(ProductIdentityError, match=error):
        ProductIdentity(namespace, identifier)


@pytest.mark.parametrize(
    "value",
    [None, 123, "rees46:category:1", "rees46:item:", ":item:1", "rees46:item"],
)
def test_invalid_canonical_item_id_fails(value):
    with pytest.raises(ProductIdentityError, match="canonical item_id"):
        parse_canonical_item_id(value)


def test_serializer_rejects_none_instead_of_hashing_text_none():
    with pytest.raises(ProductIdentityError, match="must be ProductIdentity"):
        serialize_product_identity(None)

"""Stable feature-representation contracts."""

from ppsi.features.hashing import (
    HashingConfig,
    HashingConfigError,
    ProductHashResidual,
    ProductIdentity,
    ProductIdentityError,
    ReservedProductId,
    bucket_canonical_item_id,
    bucket_product_input,
    bucketize_canonical_item_ids,
    bucketize_product_inputs,
    hash_product_identity,
    load_hashing_config,
    map_digest_to_bucket,
    parse_canonical_item_id,
    serialize_product_identity,
)

__all__ = [
    "HashingConfig",
    "HashingConfigError",
    "ProductHashResidual",
    "ProductIdentity",
    "ProductIdentityError",
    "ReservedProductId",
    "bucket_canonical_item_id",
    "bucket_product_input",
    "bucketize_canonical_item_ids",
    "bucketize_product_inputs",
    "hash_product_identity",
    "load_hashing_config",
    "map_digest_to_bucket",
    "parse_canonical_item_id",
    "serialize_product_identity",
]

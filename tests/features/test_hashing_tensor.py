from __future__ import annotations

import pytest
import torch

from ppsi.features.hashing import (
    ProductHashResidual,
    ProductIdentity,
    ProductIdentityError,
    ReservedProductId,
    bucketize_canonical_item_ids,
    bucketize_product_inputs,
)


def test_bucketization_is_shape_preserving_int64(hashing_config):
    values = [
        ProductIdentity("rees46:item", "1"),
        ReservedProductId.PAD,
        None,
        ProductIdentity("rees46:item", "2"),
        ReservedProductId.OOV,
        ProductIdentity("other:item", "1"),
    ]
    result = bucketize_product_inputs(values, shape=(2, 3), config=hashing_config)
    assert result.dtype == torch.int64
    assert tuple(result.shape) == (2, 3)
    assert result[0, 1].item() == hashing_config.pad_index
    assert result[0, 2].item() == hashing_config.null_index
    assert result[1, 1].item() == hashing_config.oov_index


def test_canonical_string_bucketization_does_not_accept_numeric_values(hashing_config):
    values = ["rees46:item:1", 9007199254740993]
    with pytest.raises(ProductIdentityError, match="canonical item_id must be a string"):
        bucketize_canonical_item_ids(values, shape=(1, 2), config=hashing_config)


def test_shape_count_and_shape_type_mismatch_fail(hashing_config):
    values = [ProductIdentity("rees46:item", "1")]
    with pytest.raises(ValueError, match="requires 2 inputs"):
        bucketize_product_inputs(values, shape=(1, 2), config=hashing_config)
    with pytest.raises(TypeError, match=r"shape\[1\]"):
        bucketize_product_inputs(values, shape=(1, True), config=hashing_config)


def test_product_hash_residual_preserves_shape_and_zeros_pad(hashing_config):
    buckets = bucketize_product_inputs(
        [
            ProductIdentity("rees46:item", "1"),
            ReservedProductId.PAD,
            ReservedProductId.OOV,
            None,
            ProductIdentity("rees46:item", "2"),
            ProductIdentity("rees46:item", "3"),
        ],
        shape=(2, 3),
        config=hashing_config,
    )
    module = ProductHashResidual(hashing_config)
    output = module(buckets)
    assert tuple(output.shape) == (2, 3, hashing_config.residual_embedding_dim)
    assert torch.equal(output[0, 1], torch.zeros(hashing_config.residual_embedding_dim))
    assert module.config_sha256 == hashing_config.config_sha256
    assert set(module.state_dict()) == {"embedding.weight"}


def test_product_hash_residual_rejects_wrong_dtype_and_range(hashing_config):
    module = ProductHashResidual(hashing_config)
    with pytest.raises(TypeError, match="torch.int64"):
        module(torch.tensor([1], dtype=torch.int32))
    with pytest.raises(ValueError, match="outside"):
        module(torch.tensor([hashing_config.bucket_count], dtype=torch.int64))

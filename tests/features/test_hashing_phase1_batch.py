from __future__ import annotations

from dataclasses import replace

import torch

from ppsi.features.hashing import ProductIdentity, ReservedProductId, bucketize_product_inputs
from ppsi.training.batch import CategoricalChannelSpec, validate_canonical_phase1_batch
from ppsi.training.fixtures import default_batch_spec, make_phase1_batch


def test_hashed_products_integrate_without_replacing_category_or_brand(hashing_config):
    base = make_phase1_batch()
    base_spec = default_batch_spec()
    batch_size, history_width = base.history_mask.shape
    _, candidate_width = base.candidate_mask.shape

    history_inputs = []
    for row in range(batch_size):
        for column in range(history_width):
            history_inputs.append(
                ProductIdentity("rees46:item", f"h-{row}-{column}")
                if base.history_mask[row, column]
                else ReservedProductId.PAD
            )
    history_buckets = bucketize_product_inputs(
        history_inputs,
        shape=(batch_size, history_width),
        config=hashing_config,
    )

    candidate_inputs = []
    for row in range(batch_size):
        for column in range(candidate_width):
            candidate_inputs.append(
                ProductIdentity("rees46:item", f"c-{row}-{column}")
                if base.candidate_mask[row, column]
                else ReservedProductId.PAD
            )
    candidate_buckets = bucketize_product_inputs(
        candidate_inputs,
        shape=(batch_size, candidate_width),
        config=hashing_config,
    )

    history_category = base.history_categorical_ids["category_id"].clone()
    history_brand = history_category.clone()
    history_channels = {
        "product_hash_bucket_id": history_buckets,
        "category_id": history_category,
        "brand_id": history_brand,
        "event_type_id": base.history_categorical_ids["event_type_id"],
    }

    candidate_category = base.candidate_categorical_ids["candidate_category_id"].clone()
    candidate_brand = candidate_category.clone()
    candidate_channels = {
        "candidate_category_id": candidate_category,
        "candidate_brand_id": candidate_brand,
    }

    spec = replace(
        base_spec,
        history_categorical=(
            CategoricalChannelSpec(
                "product_hash_bucket_id",
                pad_id=hashing_config.pad_index,
                vocab_size=hashing_config.bucket_count,
            ),
            CategoricalChannelSpec("category_id", pad_id=0, vocab_size=16),
            CategoricalChannelSpec("brand_id", pad_id=0, vocab_size=16),
            CategoricalChannelSpec("event_type_id", pad_id=0, vocab_size=8),
        ),
        candidate_categorical=(
            CategoricalChannelSpec("candidate_category_id", pad_id=0, vocab_size=16),
            CategoricalChannelSpec("candidate_brand_id", pad_id=0, vocab_size=16),
        ),
        candidate_id_pad_id=hashing_config.pad_index,
        candidate_id_vocab_size=hashing_config.bucket_count,
    )
    batch = replace(
        base,
        history_categorical_ids=history_channels,
        candidate_ids=candidate_buckets,
        candidate_categorical_ids=candidate_channels,
    )

    validate_canonical_phase1_batch(batch, spec)
    assert torch.equal(batch.history_categorical_ids["category_id"], history_category)
    assert torch.equal(batch.history_categorical_ids["brand_id"], history_brand)
    assert torch.equal(batch.candidate_categorical_ids["candidate_category_id"], candidate_category)
    assert torch.equal(batch.candidate_categorical_ids["candidate_brand_id"], candidate_brand)

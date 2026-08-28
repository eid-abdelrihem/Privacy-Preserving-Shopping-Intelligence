from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import torch

from ppsi.features.hashing import bucketize_canonical_item_ids

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_EVENT_CONTRACT = REPO_ROOT / "fixtures/canonical_event_v1.json"
REAL_SMOKE_FIXTURE = REPO_ROOT / "fixtures/smoke_sample.parquet"


def test_canonical_event_item_id_grammar_matches_hash_adapter() -> None:
    contract = json.loads(CANONICAL_EVENT_CONTRACT.read_text(encoding="utf-8"))

    assert contract["schema_version"] == "CanonicalEvent/v1"
    assert contract["id_namespaces"]["item_id"] == "rees46:item:<raw id>"


def test_real_canonical_item_ids_flow_into_phase1_hash_buckets(hashing_config) -> None:
    item_ids = (
        pl.read_parquet(REAL_SMOKE_FIXTURE, columns=["item_id"])
        .head(64)
        .get_column("item_id")
        .to_list()
    )

    buckets = bucketize_canonical_item_ids(
        item_ids,
        shape=(len(item_ids),),
        config=hashing_config,
    )

    assert buckets.dtype == torch.int64
    assert tuple(buckets.shape) == (len(item_ids),)
    assert (
        buckets.tolist()
        == bucketize_canonical_item_ids(
            item_ids,
            shape=(len(item_ids),),
            config=hashing_config,
        ).tolist()
    )
    assert set(buckets.tolist()).isdisjoint(hashing_config.reserved_indices.values())

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ppsi.features.hashing import load_hashing_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "fixtures/features/hashing_conformance_config.v1.json"
VECTORS_PATH = REPO_ROOT / "fixtures/features/hashing_golden_vectors.v1.json"


@pytest.fixture
def hashing_config():
    return load_hashing_config(CONFIG_PATH)


@pytest.fixture
def hashing_config_record() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def hashing_vectors() -> dict[str, object]:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))

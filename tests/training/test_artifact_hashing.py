from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from ppsi.training.identity import file_sha256
from scripts.generate_training_artifact_manifest import (
    ARTIFACTS,
    _load_json,
    sha256_tree,
    validate_artifact_records,
)


def test_text_hash_normalizes_lf_crlf_and_bom(tmp_path: Path):
    left = tmp_path / "left.py"
    right = tmp_path / "right.py"
    bom = tmp_path / "bom.py"
    left.write_bytes(b"x = 1\ny = 2\n")
    right.write_bytes(b"x = 1\r\ny = 2\r\n")
    bom.write_bytes(b"\xef\xbb\xbfx = 1\r\ny = 2\r\n")
    assert file_sha256(left) == file_sha256(right) == file_sha256(bom)


def test_binary_hash_preserves_exact_bytes(tmp_path: Path):
    left = tmp_path / "left.bin"
    right = tmp_path / "right.bin"
    left.write_bytes(b"x\r\ny")
    right.write_bytes(b"x\ny")
    assert file_sha256(left) != file_sha256(right)


def test_tree_hash_ignores_interpreter_and_pytest_caches(tmp_path: Path):
    tracked = tmp_path / "tests/training/test_example.py"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("assert 1 + 1 == 2\n", encoding="utf-8")
    baseline = sha256_tree(tmp_path / "tests", root=tmp_path)

    cache = tmp_path / "tests/training/__pycache__/test_example.cpython-311.pyc"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"machine-specific bytecode")
    pytest_cache = tmp_path / "tests/.pytest_cache/v/cache/nodeids"
    pytest_cache.parent.mkdir(parents=True)
    pytest_cache.write_text("[]", encoding="utf-8")

    assert sha256_tree(tmp_path / "tests", root=tmp_path) == baseline


def _artifact_records() -> dict[str, dict[str, str]]:
    return {
        logical_id: {"path": path, "sha256": "0" * 64}
        for logical_id, path in ARTIFACTS.items()
    }


def test_artifact_records_require_exact_ids_and_paths():
    records = _artifact_records()
    validate_artifact_records(records)

    missing = deepcopy(records)
    missing.pop("phase1_batch_v1")
    with pytest.raises(ValueError, match="logical ID set mismatch"):
        validate_artifact_records(missing)

    replaced = deepcopy(records)
    replaced["replacement"] = replaced.pop("phase1_batch_v1")
    with pytest.raises(ValueError, match="logical ID set mismatch"):
        validate_artifact_records(replaced)

    wrong_path = deepcopy(records)
    wrong_path["phase1_batch_v1"]["path"] = "ppsi/training/outputs.py"
    with pytest.raises(ValueError, match="duplicate canonical paths"):
        validate_artifact_records(wrong_path)

    unique_wrong_path = deepcopy(records)
    unique_wrong_path["phase1_batch_v1"]["path"] = "ppsi/training/not-the-contract.py"
    with pytest.raises(ValueError, match="Artifact path mismatch"):
        validate_artifact_records(unique_wrong_path)


def test_json_loader_rejects_duplicate_logical_ids(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(
        '{"schema":"v1","artifacts":{"same":{"path":"a","sha256":"0"},'
        '"same":{"path":"b","sha256":"1"}}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key 'same'"):
        _load_json(path)

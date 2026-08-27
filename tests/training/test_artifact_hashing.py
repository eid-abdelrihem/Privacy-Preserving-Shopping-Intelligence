from __future__ import annotations

from pathlib import Path

from ppsi.training.identity import file_sha256
from scripts.generate_training_artifact_manifest import sha256_tree


def test_text_hash_normalizes_lf_crlf_and_bom(tmp_path: Path):
    left = tmp_path / "left.py"
    right = tmp_path / "right.py"
    bom = tmp_path / "bom.py"
    left.write_bytes(b"x = 1\ny = 2\n")
    right.write_bytes(b"x = 1\r\ny = 2\r\n")
    bom.write_bytes(b"\xef\xbb\xbfx = 1\r\ny = 2\r\n")
    assert file_sha256(left) == file_sha256(right) == file_sha256(bom)


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

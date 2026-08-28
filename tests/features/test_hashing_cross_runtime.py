from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_VERIFIER = REPO_ROOT / "tests/features/cross_runtime/verify_hashing_vectors.mjs"
CONFIG = REPO_ROOT / "fixtures/features/hashing_conformance_config.v1.json"
VECTORS = REPO_ROOT / "fixtures/features/hashing_golden_vectors.v1.json"


def test_independent_node_bigint_runtime_matches_golden_vectors():
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the S1-SE-05 cross-runtime contract"
    completed = subprocess.run(
        [node, str(NODE_VERIFIER), str(CONFIG), str(VECTORS)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["runtime"] == "node-bigint-reference"
    assert result["config_sha256"] == (
        "27ee2f0a13adf319efd3ff8e6bf17a96970407fa259b2c229a5fba29c0445fd9"
    )

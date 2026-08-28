from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/features/validate_hashing.py"
CONFIG = REPO_ROOT / "fixtures/features/hashing_conformance_config.v1.json"
VECTORS = REPO_ROOT / "fixtures/features/hashing_golden_vectors.v1.json"


def test_results_are_identical_across_processes_and_pythonhashseed():
    outputs = []
    for seed in ("0", "1", "42", "random"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--config",
                str(CONFIG),
                "--vectors",
                str(VECTORS),
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1

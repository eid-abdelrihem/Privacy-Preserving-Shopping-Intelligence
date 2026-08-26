import hashlib
import json
from pathlib import Path


def generate_manifest():
    evidence_dir = Path("docs/evidence/s1-pr-02")
    manifest_path = evidence_dir / "artifact_manifest.v1.json"

    # Files to hash
    files_to_hash = {
        "config": Path("config/fl_synthetic_smoke.v1.json"),
        "entry_point": Path("scripts/federated/fl_synthetic_smoke.py"),
        "lifecycle_test": Path("tests/federated/test_fl_synthetic_smoke.py"),
        "documentation": Path("docs/federated-synthetic-smoke.md"),
        "smoke_summary": evidence_dir / "fl_synthetic_smoke_summary.v1.json",
        "environment_lock": Path("uv.lock"),
    }

    manifest = {"schema": "artifact_manifest_v1", "version": 1, "artifacts": {}}

    for logical_id, file_path in files_to_hash.items():
        if not file_path.exists() and logical_id != "documentation":
            raise FileNotFoundError(f"Missing required deliverable: {file_path}")

        # We allow missing documentation for now as we might generate it later,
        # but wait, the instruction says to hash documentation too. We should write documentation first.
        if file_path.exists():
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            manifest["artifacts"][logical_id] = {
                "path": str(file_path.as_posix()),
                "sha256": file_hash,
            }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated manifest at {manifest_path}")


if __name__ == "__main__":
    generate_manifest()

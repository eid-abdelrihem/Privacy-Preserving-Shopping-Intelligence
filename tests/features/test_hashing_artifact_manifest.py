from __future__ import annotations

from scripts.features.generate_hashing_artifact_manifest import verify_manifest


def test_hashing_artifact_manifest_matches_current_files():
    verify_manifest()

"""Tests for regime catalog and artifact map validation via internal validators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.experiments.contracts import ContractValidationError
from scripts.experiments.schemas import (
    validate_experiment_artifact_map,
    validate_regime_catalog,
)

_ROOT = Path(__file__).parent.parent.parent


class TestRegimeCatalog:
    def test_regime_catalog_validates(self) -> None:
        data_path = _ROOT / "config" / "experiments" / "regime_catalog.v1.json"
        assert data_path.exists(), f"Missing {data_path}"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        result = validate_regime_catalog(data)
        expected_regimes = {"R1", "R2A", "R2B", "R3", "R4", "R5"}
        assert set(result["regimes"].keys()) == expected_regimes

    def test_regime_catalog_rejects_unknown_fields(self) -> None:
        data = {
            "schema": "regime_catalog_v1",
            "version": "1",
            "regimes": {},
            "extra": "bad",
        }
        with pytest.raises(ContractValidationError, match="unknown fields"):
            validate_regime_catalog(data)

    def test_regime_catalog_rejects_wrong_schema(self) -> None:
        data = {
            "schema": "wrong_v1",
            "version": "1",
            "regimes": {},
        }
        with pytest.raises(ContractValidationError, match="schema"):
            validate_regime_catalog(data)


class TestArtifactMap:
    def test_artifact_map_validates(self) -> None:
        data_path = _ROOT / "config" / "experiments" / "experiment_artifact_map.v1.json"
        assert data_path.exists(), f"Missing {data_path}"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        result = validate_experiment_artifact_map(data)
        assert isinstance(result["artifacts"], dict)

    def test_artifact_map_rejects_unknown_fields(self) -> None:
        data = {
            "schema": "experiment_artifact_map_v1",
            "version": "1",
            "artifacts": {},
            "extra": "bad",
        }
        with pytest.raises(ContractValidationError, match="unknown fields"):
            validate_experiment_artifact_map(data)

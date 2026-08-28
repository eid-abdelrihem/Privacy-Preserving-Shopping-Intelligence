import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts/validate_repository_security.py"
SPEC = importlib.util.spec_from_file_location("repository_security_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def test_runtime_assembled_known_bad_fixture_is_rejected() -> None:
    provider_prefix = "".join(map(chr, (103, 104, 112, 95)))
    known_bad = f"ACCESS_TOKEN={provider_prefix}{'A' * 36}"

    findings = VALIDATOR.find_secret_markers(known_bad, Path("runtime-known-bad.txt"))

    assert findings == ["runtime-known-bad.txt: possible github_token"]


def test_non_authenticating_placeholders_are_allowed() -> None:
    safe_example = "API_KEY=\nACCESS_TOKEN=<set-locally>\nPASSWORD=<not-a-secret>\n"

    assert VALIDATOR.find_secret_markers(safe_example, Path("safe-example.env")) == []


def test_repository_settings_policy_matrix_is_consistent() -> None:
    assert VALIDATOR.validate_policy_matrix(ROOT / VALIDATOR.POLICY_MATRIX_PATH) == []


def test_repository_security_baseline_passes() -> None:
    assert VALIDATOR.validate_repository(ROOT) == []

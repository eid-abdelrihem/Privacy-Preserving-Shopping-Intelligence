"""Validate the repository-review and secret-handling baseline for S1-SE-01."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_MATRIX_PATH = Path(
    "docs/evidence/s1-se-01/repository-settings-policy-matrix.v1.json"
)
ARTIFACT_MANIFEST_PATH = Path("docs/evidence/s1-se-01/artifact_manifest.v1.json")

REQUIRED_PATHS = (
    Path(".github/CODEOWNERS"),
    Path(".github/SECURITY.md"),
    Path(".github/pull_request_template.md"),
    Path("docs/security/secret-handling.md"),
    POLICY_MATRIX_PATH,
    ARTIFACT_MANIFEST_PATH,
    Path("scripts/validate_repository_security.py"),
    Path("tests/security/test_repository_security.py"),
)

EXPECTED_OWNERS = {
    "@eid-abdelrihem",
    "@AhmedAbdelhamed01",
    "@ahmedd-sherif",
}

EXPECTED_IGNORED_PATHS = (
    ".env",
    ".env.local",
    ".env.production",
    ".secrets/example.txt",
    "credentials.json",
    "credentials.development.json",
    "service-account-project.json",
    "private.pem",
    "private.key",
    "private.p12",
    ".netrc",
    ".pypirc",
)

EXPECTED_TRACKABLE_PATHS = (".env.example",)

EXPECTED_CONTROL_TARGETS: dict[str, Any] = {
    "branch.require_pull_request": True,
    "branch.required_approving_reviews": 1,
    "branch.dismiss_stale_reviews": True,
    "branch.require_code_owner_review": True,
    "branch.require_last_push_approval": True,
    "branch.require_conversation_resolution": True,
    "branch.enforce_for_admins": True,
    "branch.allow_force_pushes": False,
    "branch.allow_deletions": False,
    "branch.required_status_checks": "deferred_until_s1_se_02_real_check",
    "security.secret_scanning": "enabled",
    "security.push_protection": "enabled",
    "security.dependency_alerts": "enabled",
    "security.dependabot_security_updates": "enabled",
    "security.private_vulnerability_reporting": "enabled",
    "security.codeql_default_setup": "enabled_python_default_suite",
    "actions.default_workflow_permissions": "read",
    "workflow.non_author_merge": True,
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-{5}BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-{5}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("provider_secret_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
)


def find_secret_markers(text: str, path: Path | str = "<memory>") -> list[str]:
    """Return redacted findings without ever echoing a matched credential value."""

    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"{path}: possible {label}")
    return findings


def _git_paths(root: Path) -> tuple[list[Path], list[str]]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return [], [f"git ls-files failed: {stderr or 'unknown error'}"]

    paths = {
        Path(os.fsdecode(raw_path))
        for raw_path in completed.stdout.split(b"\0")
        if raw_path
    }
    return sorted(paths, key=lambda path: path.as_posix()), []


def _is_ignored(root: Path, relative_path: str) -> tuple[bool, str | None]:
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative_path],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if completed.returncode in (0, 1):
        return completed.returncode == 0, None

    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    return False, f"git check-ignore failed for {relative_path}: {stderr or 'unknown error'}"


def validate_ignore_rules(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative_path in EXPECTED_IGNORED_PATHS:
        ignored, error = _is_ignored(root, relative_path)
        if error:
            errors.append(error)
        elif not ignored:
            errors.append(f"expected secret path is trackable: {relative_path}")

    for relative_path in EXPECTED_TRACKABLE_PATHS:
        ignored, error = _is_ignored(root, relative_path)
        if error:
            errors.append(error)
        elif ignored:
            errors.append(f"safe example path must remain trackable: {relative_path}")
    return errors


def validate_codeowners(root: Path = ROOT) -> list[str]:
    path = root / ".github/CODEOWNERS"
    if not path.is_file():
        return ["missing .github/CODEOWNERS"]

    entries = [
        line.split()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    global_entries = [entry for entry in entries if entry and entry[0] == "*"]
    if len(global_entries) != 1:
        return ["CODEOWNERS must contain exactly one global '*' rule"]

    owners = set(global_entries[0][1:])
    if owners != EXPECTED_OWNERS:
        return ["global CODEOWNERS rule must name all three project members"]
    return []


def validate_pull_request_template(root: Path = ROOT) -> list[str]:
    path = root / ".github/pull_request_template.md"
    if not path.is_file():
        return ["missing .github/pull_request_template.md"]

    content = path.read_text(encoding="utf-8")
    required_markers = (
        "## Summary",
        "## Linked Issue and dependencies",
        "Closes #",
        "## Validation",
        "## Artifacts and reproducibility",
        "## Security and privacy",
        "## Review and merge",
        "A non-author will merge this PR",
    )
    return [
        f"pull request template is missing marker: {marker}"
        for marker in required_markers
        if marker not in content
    ]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"missing JSON artifact: {path}"]
    except json.JSONDecodeError as error:
        return None, [f"invalid JSON in {path}: {error}"]

    if not isinstance(payload, dict):
        return None, [f"JSON artifact must be an object: {path}"]
    return payload, []


def validate_policy_matrix(path: Path | None = None) -> list[str]:
    matrix_path = path or ROOT / POLICY_MATRIX_PATH
    payload, errors = _load_json(matrix_path)
    if payload is None:
        return errors

    if payload.get("schema") != "repository_settings_policy_matrix_v1":
        errors.append("policy matrix schema must be repository_settings_policy_matrix_v1")
    if payload.get("version") != 1:
        errors.append("policy matrix version must be 1")
    if payload.get("task_id") != "S1-SE-01":
        errors.append("policy matrix task_id must be S1-SE-01")

    redaction = payload.get("redaction")
    if not isinstance(redaction, dict) or redaction.get("secret_material_included") is not False:
        errors.append("policy matrix must explicitly exclude secret material")

    controls = payload.get("controls")
    if not isinstance(controls, list):
        return errors + ["policy matrix controls must be an array"]

    indexed: dict[str, dict[str, Any]] = {}
    for control in controls:
        if not isinstance(control, dict) or not isinstance(control.get("id"), str):
            errors.append("every policy control must be an object with a string id")
            continue
        control_id = control["id"]
        if control_id in indexed:
            errors.append(f"duplicate policy control: {control_id}")
        indexed[control_id] = control

    for control_id, expected_target in EXPECTED_CONTROL_TARGETS.items():
        control = indexed.get(control_id)
        if control is None:
            errors.append(f"missing policy control: {control_id}")
            continue
        if control.get("target") != expected_target:
            errors.append(f"unexpected target for policy control: {control_id}")
        status = control.get("status")
        if status == "pending_owner_action" and control.get("owner_action_required") is not True:
            errors.append(f"pending owner control lacks owner_action_required: {control_id}")
        if status == "verified" and control.get("observed") != control.get("target"):
            errors.append(f"verified control does not match its target: {control_id}")

    pending_ids = {
        control_id
        for control_id, control in indexed.items()
        if control.get("status") == "pending_owner_action"
    }
    owner_actions = payload.get("owner_actions")
    if not isinstance(owner_actions, dict):
        errors.append("policy matrix owner_actions must be an object")
    else:
        action_ids = set(owner_actions.get("control_ids", []))
        if action_ids != pending_ids:
            errors.append("owner_actions control_ids must match pending_owner_action controls")
        if pending_ids and owner_actions.get("status") != "pending":
            errors.append("owner_actions status must be pending while owner controls remain")

    local_commands = payload.get("validation", {}).get("local_commands", [])
    required_commands = {
        "uv run --locked python scripts/validate_repository_security.py",
        "uv run --locked pytest -q tests/security/test_repository_security.py",
        (
            "uv run --locked ruff check scripts/validate_repository_security.py "
            "tests/security/test_repository_security.py"
        ),
    }
    if not required_commands.issubset(set(local_commands)):
        errors.append("policy matrix is missing one or more canonical local validation commands")

    serialized = json.dumps(payload, sort_keys=True)
    errors.extend(find_secret_markers(serialized, matrix_path))
    return errors


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_artifact_manifest(path: Path | None = None) -> list[str]:
    manifest_path = path or ROOT / ARTIFACT_MANIFEST_PATH
    payload, errors = _load_json(manifest_path)
    if payload is None:
        return errors

    if payload.get("schema") != "repository_security_artifact_manifest_v1":
        errors.append("artifact manifest has an unexpected schema")
    if payload.get("version") != 1 or payload.get("task_id") != "S1-SE-01":
        errors.append("artifact manifest must identify S1-SE-01 version 1")
    if payload.get("hash_algorithm") != "SHA-256":
        errors.append("artifact manifest hash_algorithm must be SHA-256")
    if payload.get("hash_scope") != "UTF-8 text normalized to LF with no BOM":
        errors.append("artifact manifest must use the cross-platform canonical text hash scope")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return errors + ["artifact manifest artifacts must be an object"]

    for logical_id, record in artifacts.items():
        if not isinstance(record, dict):
            errors.append(f"artifact manifest record must be an object: {logical_id}")
            continue
        relative_path = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            errors.append(f"artifact manifest record is incomplete: {logical_id}")
            continue
        artifact_path = ROOT / relative_path
        if not artifact_path.is_file():
            errors.append(f"manifest artifact is missing: {relative_path}")
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            errors.append(f"manifest SHA-256 has invalid format: {relative_path}")
            continue
        if _canonical_text_sha256(artifact_path) != expected_hash:
            errors.append(f"manifest SHA-256 mismatch: {relative_path}")
    return errors


def scan_repository(root: Path = ROOT) -> list[str]:
    paths, errors = _git_paths(root)
    for relative_path in paths:
        absolute_path = root / relative_path
        if not absolute_path.is_file() or absolute_path.stat().st_size > 2 * 1024 * 1024:
            continue
        content = absolute_path.read_bytes()
        if b"\0" in content:
            continue
        text = content.decode("utf-8", errors="replace")
        errors.extend(find_secret_markers(text, relative_path.as_posix()))
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    errors = [
        f"missing required repository-security artifact: {relative_path.as_posix()}"
        for relative_path in REQUIRED_PATHS
        if not (root / relative_path).is_file()
    ]
    errors.extend(validate_codeowners(root))
    errors.extend(validate_pull_request_template(root))
    errors.extend(validate_ignore_rules(root))
    errors.extend(validate_policy_matrix(root / POLICY_MATRIX_PATH))
    errors.extend(validate_artifact_manifest(root / ARTIFACT_MANIFEST_PATH))
    errors.extend(scan_repository(root))
    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("REPOSITORY SECURITY VALIDATION: FAIL")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1

    print("REPOSITORY SECURITY VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

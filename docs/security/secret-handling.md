# Secret-Handling Baseline

## Purpose and scope

This policy applies to source code, notebooks, tests, documentation, GitHub Actions, experiment
evidence, datasets, model artifacts, deployment configuration, and local developer files in this
public repository. It defines the Phase 1 baseline; it does not claim production isolation,
Differential Privacy, Secure Aggregation, or protection that has not been implemented and measured.

## Never commit sensitive material

Do not commit:

- API credentials, access tokens, passwords, private keys, certificates containing private key
  material, session cookies, connection strings, or signed URLs;
- local `.env` variants, credential-manager exports, cloud CLI profiles, package-registry
  credentials, or service-account files;
- raw customer or user histories, direct identifiers, private client adapters, or data whose
  redistribution terms have not been verified;
- secret-scanning alert details or repository-setting evidence that contains authorization
  headers, tokens, email addresses, or private numeric identifiers.

The root `.gitignore` is a preventive guard, not a security boundary. A file being ignored does not
make it safe to store indefinitely or share. Existing tracked content is not made safe by adding an
ignore rule later.

## Local development

1. Store secrets in the operating-system credential manager or an approved local secret store.
2. If a tool requires environment variables, load them from a local ignored file or the current
   process environment. Never add the value to shell history, notebooks, screenshots, logs, or test
   output.
3. A committed `.env.example` may contain variable names and empty or unmistakable placeholder
   values only. It must never contain a provider-shaped or functional credential.
4. Grant the narrowest scope, shortest lifetime, and smallest resource access that supports the
   task. Use separate development credentials where a credential is unavoidable.
5. Before pushing, inspect the staged diff and run the repository security validator.

## GitHub Actions

- Store required CI values in GitHub Actions secrets or environments, never in workflow YAML.
- Set workflow and job permissions explicitly to the minimum required; the repository-level default
  should be read-only.
- Do not expose secrets to pull requests from forks or run untrusted pull-request code in a context
  that can access repository secrets.
- Do not print environment dumps, authorization headers, secret contexts, or command traces that
  expand sensitive values.
- Pin third-party Actions immutably and review their permissions. Issue `S1-SE-02` owns the initial
  CI workflow and the exact required check name.

## Tests, examples, and evidence

Tests must use synthetic, non-authenticating values. A known-bad scanner fixture must be assembled
at runtime from harmless fragments so no complete provider-shaped token is persisted in Git.
Repository-settings evidence must be filtered to the fields needed for review and must state when a
setting could not be read with the current role. Never infer that a hidden setting is enabled.

## If a secret is exposed

1. Stop using the credential and report the exposure privately under `.github/SECURITY.md`.
2. Rotate or revoke it at the provider immediately; deleting the Git commit is not revocation.
3. Identify the repository, branches, tags, forks, logs, caches, artifacts, and CI output that may
   contain it.
4. Review provider access logs and contain unauthorized access.
5. Remove the value from the current tree and, when required, coordinate history rewriting with the
   repository owner. Do not rewrite shared history unilaterally.
6. Record only redacted incident evidence and the rotation/revocation outcome.
7. Add a narrowly targeted preventive check or ignore rule without committing the leaked value as
   a fixture.

## Required local validation

From the repository root, run:

```powershell
uv run --locked python scripts/validate_repository_security.py
uv run --locked pytest -q tests/security/test_repository_security.py
uv run --locked ruff check scripts/validate_repository_security.py tests/security/test_repository_security.py
```

The expected result is exit code `0` and `REPOSITORY SECURITY VALIDATION: PASS`. These checks do not
replace GitHub secret scanning, push protection, peer review, or credential rotation.

## Owner-controlled settings

Branch protection, secret scanning, push protection, dependency alerts, CodeQL default setup,
private vulnerability reporting, and default Actions permissions require repository-owner/admin
access. Their filtered observed state and pending owner actions are recorded in
`docs/evidence/s1-se-01/repository-settings-policy-matrix.v1.json`. No contributor should request or
share the owner's token to perform those actions.

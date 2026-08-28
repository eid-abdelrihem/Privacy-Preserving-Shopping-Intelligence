# Security Policy

## Supported versions

This research repository has no stable release yet. Security fixes are applied to the current
`main` branch. Historical commits and experimental branches are not supported versions.

## Reporting a vulnerability

Do not publish vulnerability details, credentials, raw user histories, or exploit material in a
public Issue, Discussion, Pull Request, or commit.

Use the repository's **Security** tab and **Report a vulnerability** to submit a private report.
Private vulnerability reporting is an owner-controlled setting and is tracked in
[`docs/evidence/s1-se-01/repository-settings-policy-matrix.v1.json`](../docs/evidence/s1-se-01/repository-settings-policy-matrix.v1.json).

If that button is temporarily unavailable, contact a maintainer through an existing private team
channel and ask for a secure reporting route without including vulnerability details. An external
reporter without a private channel may open a minimal public Issue titled `Security contact
request`; include no technical details, credentials, personal data, or exploit steps.

Include the following only in the resulting private channel:

- affected commit, path, or component;
- impact and realistic attack prerequisites;
- minimal reproduction steps with synthetic data;
- suggested remediation, if known;
- whether any credential or personal data may have been exposed.

The maintainers will acknowledge the report, validate it, coordinate remediation, and disclose it
only after a fix or an explicit risk decision. Never test against data, accounts, or infrastructure
that you do not own or have permission to use.

## Secret exposure

Treat a committed secret as compromised even if the commit is later deleted. Stop using it, notify
a maintainer privately, rotate or revoke it at the provider, review relevant access logs, and then
remove it from reachable history if necessary. Follow
[`docs/security/secret-handling.md`](../docs/security/secret-handling.md) for the project baseline.

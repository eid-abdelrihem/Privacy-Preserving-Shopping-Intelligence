# Repository Protection

The main branch should use these GitHub settings:

- require a pull request;
- require one approval;
- require approval of the most recent reviewable push;
- require resolved conversations;
- apply the rule to administrators with no bypass;
- block force pushes and branch deletion.

Do not require a status check until #22 creates a real CI check and it succeeds at least once. Then
require only that stable check.

Enable secret scanning, push protection, dependency alerts, private vulnerability reporting, and
read-only default GitHub Actions permissions. CodeQL and automated dependency-update PRs can wait
until the initial CI pipeline is stable.

These platform settings are the enforcement. The files in .github only provide the team-facing
workflow and review guidance.

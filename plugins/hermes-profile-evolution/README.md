# hermes-profile-evolution

Claude Code command, skill, and supported file-edit hook for submitting non-authoritative, target-addressed Hermes profile-evolution proposals.

The plugin contains no Hermes credential, route registry, mutation policy, target ledger, or target-disposition logic. It calls only the canonical `hermes profile-request` interface with a closed version-1 envelope on standard input. A compatible health response is required before proposal submission.

The hook blocks recognizable Claude Code file-tool edits after the Team Mimir ownership classifier reports profile-owned, mixed, unknown, or prohibited custody. It intentionally does not claim shell-command interception.

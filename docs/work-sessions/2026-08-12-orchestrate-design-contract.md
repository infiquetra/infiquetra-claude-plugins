# Orchestrate design — binding contract v0.1

Governs the design effort for a new `orchestrate` plugin (Claude Code plugin plus a Codex
sibling) that turns Jeff's pasted orchestration charter into reusable, enforced mechanism.

Phase: **evidence gathering and requirements.** Not implementation.

This document exists because the prior charter failed as prose. Every rule below is
countable or checkable; nothing here relies on an agent finding it persuasive.

## Mutation scope

- **write:** `docs/**` in `infiquetra-claude-plugins`; the session scratchpad
- **read-only:** every other path, every other repository, all three transcript corpora
- **forbidden this phase:** `plugins/**`, `tests/**`, `.claude-plugin/**`, and every
  repository other than `infiquetra-claude-plugins`

## Artifact budget

- 1 pain-point ledger
- 1 requirements document, with diagrams
- 0 issues, 0 branches, 0 pull requests, 0 commits, 0 plugin scaffolds

Anything past this list needs Jeff's approval, asked for each time.

## Work in progress

One phase active at a time; a phase closes before the next opens.
Mining sessions take exactly one shard each, return their ledger, and close.

## Stop conditions — halt and ask

- a finding implies changing an existing plugin
- the design needs a new repository, service, or daemon
- scope reaches past "orchestrate plugin plus its Codex sibling"
- any commit, push, issue, or pull request
- any install, marketplace refresh, or configuration change
- any permission escalation for a delegated session

## Authority

**May:** read anything; launch and close agent sessions in Herdr workspace `w2C`;
write documents under `docs/`; run read-only analysis.

**May not:** commit, push, open issues, modify any plugin, install anything, change
herdr/agent/cmux configuration, or touch any repository other than this one.

## Progress is reported as

Findings confirmed or killed. Decisions closed.

**Not** as: documents written, sessions launched, or agents run.

## Evidence base

- 2,318,065,699 raw bytes across 598 sessions, last 8 days
- three corpora: `~/.claude/projects`, `~/.claude-company/projects`, `~/.codex/sessions`
- distilled to 34,578,874 bytes across 552 sessions after dropping tool calls, tool
  results, reasoning traces, and `codex-auto-review` bot sessions
- split into 8 project-clustered shards

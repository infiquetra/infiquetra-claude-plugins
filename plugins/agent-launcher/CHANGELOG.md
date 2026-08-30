# Changelog

## [1.1.0] - 2026-08-30

### Fixed

- **A hanging session create is a named stop, not a blocked launch (#890).** `launch` runs the
  wrapper under an explicit deadline (`LAUNCH_CREATE_SECONDS`, 120 seconds — larger than every
  other deadline because it may reach another machine and cold-start a vendor CLI) and stops with
  a named message when the create times out or exits nonzero, instead of blocking without bound.
- **A pane this launch did not create is inspected before it is prompted (#897).** A session
  whose tab already existed may hold text somebody staged in its input box, and a prompt typed
  behind it can submit that text. The guard reads the box with styling intact, distinguishes a
  client's own placeholder from staged text, and treats staged text as a stop — recorded in the
  receipt and the unit note, never cleared. The guard keys on tab ownership, not the wrapper's
  `reused` bit, which names the workspace and would inspect the ordinary create path.
- **A declared permission is honoured and confirmed, never silently downgraded (#896).** A
  permission value outside the vendor's map stops with a named message instead of falling back to
  the auto flags, and preflight confirms the declared posture against the launch argv, recording
  `permission_resolved` in the receipt distinctly from the requested value.
- **A stale transcript can no longer certify a launch's account (#889).** `launch` captures the
  create instant and passes it as a recency floor, so a statusline-silent session is confirmed
  only from a transcript written at or after that instant (one second of mtime slack absorbs
  filesystem granularity). The receipt records `account_evidence` — statusline, transcript, or
  none — beside the requested account.
- **A failing owned close is surfaced instead of swallowed (#888).** `close_run_session` returns
  the Herdr result and records a failing close (returncode and error text) on the unit note;
  `close_owned_session`, the CLI-facing variant, exits nonzero on the same failure. Unowned
  sessions still close nothing and report nothing.
- **A missing receipt path stops with a cause and a recovery, not a traceback (#887).**
  `close --receipt-json` on an argument that is neither an existing file nor inline JSON raises a
  `SystemExit` naming the path and the remedy. Inline JSON — object or array — keeps its existing
  behaviour, including the `receipt must be a JSON object` stop.
- **The skill stops overselling `--dry-run` (#880).** The guidance now names what dry-run confirms
  (resolved working directory, Herdr workspace, flag ordering, exact command) and what it does not
  validate (model, reasoning effort, account), and documents the real preflight — a bounded live
  launch with a read-back — under an ordering rule with secret-safety safeguards.

## [1.0.0] - 2026-08-25

### Added

- **Portable single-session launch contract (#777).** New plugin owns create-via-`agents`,
  verify-via-Herdr, prompt delivery, and owned cleanup. An ordinary session can launch one
  verified agent without starting an Orchestrate run. Orchestrate consumes the same module
  (`skills/agent-launcher/scripts/launcher.py`) and no longer keeps a private copy of the
  launcher seam. Explicit dependency on the canonical `herdr` skill for every interaction
  after the session exists; this plugin does not duplicate it. The Agent Plugins port is
  tracked at infiquetra-agent-plugins#22 and does not gate this release.

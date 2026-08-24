# Muse skills install CLI contract exploration

- **Date:** 2026-08-24
- **Issue:** #786 (exploration; parent issue #787 "defects-claude-plugins unattended run", unit U14, lane C1)
- **Status:** Complete exploration findings. Documentation-only; no production code changes required.
- **System under test:** Muse CLI `0.2.1 (0.2.1-R1215.1)` at `~/.local/bin/muse` on macOS.

---

## 1. Executive summary

During unifi plugin staging in session `2cc86ea6-7168-4a88-bc8f-460f60524ff6` (worktree `orch-s9-resync-unifi-201`, 2026-08-22), a two-target comparison harness (`stage.sh`) crashed with `KeyError: 'installed'` when attempting to parse the JSON output of `muse skills install ... --json`.

This exploration executed read-only and scratch-target interrogation of the installed Muse command-line interface (`muse`) to establish the actual JSON output contract for `muse skills install`.

### Key findings

1. **Success emits `"installed"`, failure emits `"error"`.** On successful installation (exit code `0`), Muse emits a top-level JSON object with the `"installed"`, `"lockfile_path"`, and `"diagnostics"` keys. On failure (exit code `1`), Muse emits a top-level JSON object with the `"error"` key containing `"code"`, `"message"`, and `"details"` — with **no `"installed"` key**.
2. **Root cause of the historical crash.** The session-authored staging harness unconditionally dereferenced `data["installed"]` without checking the process exit code and with the human-readable error message discarded by `2>/dev/null`. When one of the two staged installations failed, Muse returned `{"error": ...}` on standard output, and the unguarded dereference raised `KeyError: 'installed'`. The harness source and the failing invocation are quoted from the session transcript in Section 5; what that evidence does **not** establish is *which* error Muse returned, because the harness discarded standard error and its captured JSON files were not preserved in the transcript.
3. **Repository code status.** A complete grep audit across `plugins/` (non-test) confirmed that no in-repo code or documentation currently invokes `muse skills install` or makes unverified assumptions about its JSON structure.
4. **Follow-up disposition.** No correction is needed in existing repository code or plugin surfaces. This document serves as the authoritative reference for any future cross-vendor staging harness or porting workflow.

---

## 2. System under test & environment

- **CLI binary:** `/Users/jefcox/.local/bin/muse`
- **CLI version command:** `muse --version`
- **Captured output:**
  ```text
  Muse Code 0.2.1 (0.2.1-R1215.1)
  ```

---

## 3. Verbatim CLI captures

### 3.1. `muse skills --help`

**Command run:**
```bash
muse skills --help
```

**Verbatim output (exit code 0):**
```text
usage: muse skills list [--source all|user|project|built-in|plugin] [--enabled-only] [--workspace <path>] [--trust-workspace] [--json]

usage: muse skills inspect <skill-id-or-path> [--source all|user|project|built-in|plugin] [--workspace <path>] [--trust-workspace] [--json]

usage: muse skills enable <skill-id-or-path> --scope user|project|built-in|plugin [--workspace <path>] [--trust-workspace] [--json]

usage: muse skills user-only <skill-id-or-path> --scope user|project|built-in|plugin [--workspace <path>] [--trust-workspace] [--json]

usage: muse skills disable <skill-id-or-path> --scope user|project|built-in|plugin [--workspace <path>] [--trust-workspace] [--json]

usage: muse skills validate <path> [--json]

usage: muse skills install <path> [--scope user] [--name NAME] [--force] [--json]

usage: muse skills import --from claude|codex [--scope user] [--dry-run] [--force] [--json]

usage: muse skills update <skill-id> [--json]

usage: muse skills uninstall <skill-id> [--keep-files] [--json]
```

---

### 3.2. Real skills install — success run

**Test setup:**
A scratch skill directory `/tmp/scratch-muse-test-skill` containing `SKILL.md` was created:
```markdown
---
name: scratch-test-probe
description: Scratch probe for testing muse skills install contract
---
# Scratch Test Probe
This is a temporary scratch probe for testing the muse CLI contract.
```

**Command run:**
```bash
muse skills install /tmp/scratch-muse-test-skill --json
```

> **Reproduction caution.** This command is not a dry run. With no `--scope`, and with `--scope user`
> alike, Muse installs into the operator's real user skill scope and rewrites the shared
> `skills/.muse/lock.json`. Anyone re-running this capture should run the Section 3.5 uninstall
> afterwards. Section 3.5 was run for this exploration and `muse skills list` afterwards showed no
> `scratch-test-probe` entry.

**Verbatim output (exit code 0):**
```json
{
  "installed": {
    "id": "scratch-test-probe",
    "path": "$CONFIG_DIR/skills/scratch-test-probe",
    "version": null,
    "revision": null,
    "provenance": {
      "source": {
        "type": "local"
      },
      "content_sha256": "sha256:5651578c46a597d58cba36e34334765147f8b95c5629ddec02201a2af98052dd",
      "files": [
        {
          "relative_path": "SKILL.md",
          "sha256": "sha256:efd4527cd3d68c03b7e1cde134dd487f55b5a5daa5901cf6182244165038dbfa",
          "bytes": 191
        }
      ]
    }
  },
  "lockfile_path": "$CONFIG_DIR/skills/.muse/lock.json",
  "diagnostics": []
}
```

---

### 3.3. Induced failure run 1 — duplicate / already installed

**Command run:**
```bash
muse skills install /tmp/scratch-muse-test-skill --json
```

**Verbatim output (exit code 1):**
```json
{
  "error": {
    "code": "skill-already-installed",
    "message": "skill already installed: scratch-test-probe",
    "details": {}
  }
}
```
*(Standard error carried the plain-text line `skill already installed: scratch-test-probe`; standard output carried the JSON above and nothing else.)*

---

### 3.4. Induced failure run 2 — non-existent target path

**Command run:**
```bash
muse skills install /tmp/nonexistent-skill-dir-xyz --json
```

**Verbatim output (exit code 1):**
```json
{
  "error": {
    "code": "invalid-skill-package",
    "message": "No such file or directory (os error 2)",
    "details": {}
  }
}
```
*(Standard error carried the plain-text line `No such file or directory (os error 2)`; standard output carried the JSON above and nothing else.)*

---

### 3.5. Scratch probe cleanup

**Command run:**
```bash
muse skills uninstall scratch-test-probe --json
rm -rf /tmp/scratch-muse-test-skill
```

**Verbatim output (exit code 0):**
```json
{
  "uninstalled": {
    "id": "scratch-test-probe",
    "removed_files": [
      "SKILL.md"
    ],
    "kept_files": []
  },
  "lockfile_path": "$CONFIG_DIR/skills/.muse/lock.json"
}
```

---

## 4. Verified JSON contract specification

### 4.0. Stream, exit-code, and repeat-install behaviour

These properties hold across every run captured in Section 3 and govern how the shapes below may be
consumed:

- **Standard output carries only JSON when `--json` is passed** — on success and on failure alike.
  It is safe to hand the whole of standard output to a JSON parser without stripping a prefix.
- **The human-readable message goes to standard error**, never to standard output. Discarding it
  with `2>/dev/null` costs a harness nothing *provided it reads the JSON*, because `error.code` and
  `error.message` carry the same information in machine-readable form. The original harness did
  both — discarded standard error and skipped the error branch — which is why the failure surfaced
  as a bare `KeyError` with no diagnosis.
- **The exit code is the primary success signal:** `0` for the success shape, `1` for every failure
  observed here. Branch on the exit code first and treat the JSON as the detail, not the verdict.
- **Installing is not idempotent.** Re-installing an already-installed skill id fails with exit `1`
  and `error.code == "skill-already-installed"` rather than succeeding as a no-op. This is the
  collision that broke the original two-install comparison harness. Passing `--force` re-installs
  over the existing skill and returns the ordinary success shape with exit `0`; uninstalling first
  works equally well.

### 4.1. Success shape (`exit code == 0`)

```json
{
  "installed": {
    "id": "<string>",
    "path": "<string>",
    "version": "<string | null>",
    "revision": "<string | null>",
    "provenance": {
      "source": {
        "type": "<string>"
      },
      "content_sha256": "<string>",
      "files": [
        {
          "relative_path": "<string>",
          "sha256": "<string>",
          "bytes": "<integer>"
        }
      ]
    }
  },
  "lockfile_path": "<string>",
  "diagnostics": []
}
```

> **`path` and `lockfile_path` are not filesystem paths.** Muse emits the literal, unexpanded token
> `$CONFIG_DIR` at the front of both — for example `$CONFIG_DIR/skills/<id>` — and does not resolve
> it. The same token appears in `muse skills inspect --json` output, so this is a Muse-wide output
> convention rather than an install-only quirk. A consumer that passes the value straight to
> `Path(...)` gets a directory that does not exist. On this machine `$CONFIG_DIR` resolves to
> `~/.config/muse`, confirmed by locating an installed probe at
> `/Users/jefcox/.config/muse/skills/<id>`; resolve the token yourself, or derive the location from
> `muse skills inspect` rather than from the raw string.
>
> **`diagnostics` was empty in every observed run.** It is typed `[]` above because that is what was
> captured, not because a populated entry has been ruled out. Treat it as a list of unknown element
> shape and do not assume it stays empty.

### 4.2. Failure shape (`exit code != 0`)

```json
{
  "error": {
    "code": "<string>",
    "message": "<string>",
    "details": {}
  }
}
```

> **Sampling caveat.** Two failures were induced here — `skill-already-installed` and
> `invalid-skill-package`. `details` was an empty object in both, and `muse skills --help` does not
> enumerate the error codes, so the code set is open and `details` may well be populated for codes
> not exercised. Branch on `error.code` with an explicit fallback for unrecognised codes, and read
> `details` defensively rather than assuming it is empty.

### 4.3. Consumer guidance for Python / shell harnesses

Any script calling `muse skills install <path> --json` should follow this pattern:

```python
import json
import subprocess
from pathlib import Path

proc = subprocess.run(
    ["muse", "skills", "install", str(target_path), "--json"],
    capture_output=True,
    text=True,
)

try:
    data = json.loads(proc.stdout)
except json.JSONDecodeError:
    raise RuntimeError(f"Muse emitted non-JSON output (exit {proc.returncode}): {proc.stdout} / {proc.stderr}")

if proc.returncode != 0 or "error" in data:
    err = data.get("error", {})
    err_code = err.get("code", "unknown-error")
    err_msg = err.get("message", proc.stderr.strip() or "Installation failed")
    raise RuntimeError(f"Muse skill installation failed ({err_code}): {err_msg}")

installed_info = data["installed"]
skill_id = installed_info["id"]
content_digest = installed_info["provenance"]["content_sha256"]

# NOTE: installed_info["path"] is NOT a usable filesystem path -- Muse returns the literal
# unexpanded token "$CONFIG_DIR/skills/<id>". Resolve it before touching the filesystem.
reported_path = installed_info["path"]
```

---

## 5. Root cause of the historical crash — transcript evidence

The claim in Section 1 rests on the session transcript at
`~/.claude/projects/-Users-jefcox-workspace-infiquetra-orch-s9-resync-unifi-201/2cc86ea6-7168-4a88-bc8f-460f60524ff6.jsonl`,
lines 575-576 (2026-08-22T22:17:32Z). Line 575 is the Bash invocation; line 576 is its failure.

The failing invocation redirected standard error away and captured standard output to a file:

```bash
timeout 150 "$SP/stage.sh" muse2 muse skills install ".../pkg2/portable-unifi-alt/skills/unifi-protect" --scope user --json 2>/dev/null > "$SP/muse2_unifi-protect.json"
timeout 150 "$SP/stage.sh" muse  muse skills install ".../pkg/unifi/skills/unifi-protect"            --scope user --json 2>/dev/null > "$SP/muse1_unifi-protect.json"
```

The two load-bearing lines of the harness that read those files were:

```python
obj,_=d.raw_decode(raw[raw.index("{"):])
vals.append(obj["installed"]["provenance"]["content_sha256"])
```

The traceback in line 576 names `File "<stdin>", line 11`, which is the second of those two lines.

What this establishes:

- The harness checked **no exit code** before dereferencing `obj["installed"]`, so a failure shape
  reached the dereference unguarded. This is the immediate cause.
- The captured file did contain a parseable JSON object: `raw.index("{")` and `raw_decode` both
  succeeded, and only the subscript raised. A missing or non-JSON file would have raised
  `ValueError`, not `KeyError`. So Muse emitted a well-formed object **without** an `installed`
  key — which, per Section 4.2, is the failure shape.
- The `2>/dev/null` redirect discarded the plain-text message that would have named the failure,
  which is why the original session could not say what went wrong.

What this does **not** establish: which `error.code` Muse returned. The raw JSON files were not
preserved in the transcript window. Given that the harness installed the same skill id twice in a
row, `skill-already-installed` (Section 4.0) is the leading candidate, but it is a candidate and not
a finding.

This resolves the three hypotheses the leaf issue left open: the harness's own assumption was wrong
(hypothesis c), and it was wrong *because* Muse's contract genuinely differs on failure
(hypothesis a). The two are the same defect seen from either end, not competing explanations.

---

## 6. Repository audit and touchpoint analysis

A comprehensive search of the codebase was conducted to determine if any production code or documentation relied on unverified Muse JSON assumptions.

### 6.1. Candidate surface evaluation

1. **`plugins/orchestrate/skills/orchestrate/SKILL.md` (and `commands/orchestrate.md`):**
   - The vendor table names Muse with exactly two flags, `--model` and `--reasoning-effort`
     (`SKILL.md` line 143). The approval flags `--approval-mode never` and `--yolo` are **not** in
     that table; they live in the permission-mode map at
     `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` line 169.
   - Neither surface invokes or documents `muse skills install`.
2. **`plugins/saga/scripts/engine_session_runner.py`:**
   - Mentions `"muse"` in `_KNOWN_TOOLS` (`line 28`).
   - Does not invoke `muse skills install`.
3. **`plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`:**
   - Maps model names and collapses reasoning effort (`low`, `medium`, `high`, `xhigh`) for the `"muse"` runtime.
   - Does not invoke `muse skills install`.

### 6.2. Codebase sweep for `installed`

Grep query: `grep -rn "installed" plugins/ | grep -v test`

Results:
- References in `team-execution`, `agy`, `unifi`, and `mission-control` refer to Claude's `~/.claude/plugins/installed_plugins.json` discovery rung.
- References in `orchestrate` refer to human-readable strings and changelogs indicating whether a tool or capability is installed.
- No in-repo file invokes `muse skills install` or expects an `installed` field from a subprocess JSON stream.

---

## 7. Follow-up and disposition

- **Follow-up issue required?** No. No repository surfaces are broken or encoding incorrect assumptions.
- **Disposition:** Recorded as **"no correction needed"** in the repository.
- **Future ownership:** Cross-vendor staging tooling and agent porting workflows own adhering to the contract defined in Section 4.

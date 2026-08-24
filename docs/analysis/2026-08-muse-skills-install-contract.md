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
2. **Root cause of the historical crash.** The session-authored staging harness unconditionally dereferenced `data["installed"]` without checking the process exit code or inspecting `data.get("error")`. When one of the two staged installations encountered an error (such as a conflict or validation error), Muse returned `{"error": ...}`, triggering the `KeyError: 'installed'`.
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
*(Trailing plain text on stderr/stdout: `skill already installed: scratch-test-probe`)*

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
*(Trailing plain text on stderr/stdout: `No such file or directory (os error 2)`)*

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
installed_path = installed_info["path"]
```

---

## 5. Repository audit and touchpoint analysis

A comprehensive search of the codebase was conducted to determine if any production code or documentation relied on unverified Muse JSON assumptions.

### 5.1. Candidate surface evaluation

1. **`plugins/orchestrate/skills/orchestrate/SKILL.md` (and `commands/orchestrate.md`):**
   - Mentions Muse in the vendor table (`--model`, `--reasoning-effort`, `--approval-mode never`, `--yolo`).
   - Does not invoke or document `muse skills install`.
2. **`plugins/saga/scripts/engine_session_runner.py`:**
   - Mentions `"muse"` in `_KNOWN_TOOLS` (`line 28`).
   - Does not invoke `muse skills install`.
3. **`plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`:**
   - Maps model names and collapses reasoning effort (`low`, `medium`, `high`, `xhigh`) for the `"muse"` runtime.
   - Does not invoke `muse skills install`.

### 5.2. Codebase sweep for `installed`

Grep query: `grep -rn "installed" plugins/ | grep -v test`

Results:
- References in `team-execution`, `agy`, `unifi`, and `mission-control` refer to Claude's `~/.claude/plugins/installed_plugins.json` discovery rung.
- References in `orchestrate` refer to human-readable strings and changelogs indicating whether a tool or capability is installed.
- No in-repo file invokes `muse skills install` or expects an `installed` field from a subprocess JSON stream.

---

## 6. Follow-up and disposition

- **Follow-up issue required?** No. No repository surfaces are broken or encoding incorrect assumptions.
- **Disposition:** Recorded as **"no correction needed"** in the repository.
- **Future ownership:** Cross-vendor staging tooling and agent porting workflows own adhering to the contract defined in Section 4.

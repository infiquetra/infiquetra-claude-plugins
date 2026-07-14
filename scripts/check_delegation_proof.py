#!/usr/bin/env python3
"""Delegation-integrity CI gate for bridge-carrying plugins (issue #457).

Two behavioral guards on top of the structural marketplace-drift check, both driven by the
declarative manifest ``marketplace/bridge_plugins.json`` (add a plugin there to bring it under
the gate; no code change needed):

``--mode version-gate`` (per-PR)
    Fails the build when a bridge-carrying plugin's ``marketplace.json`` version field changes in
    the diff *without* an accompanying, schema-valid delegation-proof artifact under the proofs
    directory whose ``version`` matches the new marketplace version and that verifies against its
    claimed run. This is the automated enforcement of CLAUDE.md step 6 for bridge plugins: a
    version bump must be backed by proof the bridge was actually exercised and produced real,
    attributable output.

``--mode fleet-sweep`` (continuous / broad)
    Sweeps every recorded delegation-proof artifact (and any standalone bridge transcript) and
    fails on any member of the failure taxonomy:

    * **silent no-op** — a claimed bridge run whose transcript contains zero external-tool calls
      (the bridge was "invoked" but produced no attributable work);
    * **unrecorded fallback** — a claimed bridge run whose transcript shows Claude did the work
      itself (Claude file-edit tools, no genuine bridge command) — the exact failure that made
      #278/#279 report green while making zero ``agy`` calls (LEARNINGS.md
      ``#agy-delegate-silent-claude-fallback``);
    * **untokened orphan write** — a write attributed to no traceable actor;
    * **broken proof chain** — a proof artifact that does not verify against its claimed run
      (schema/field/version invalid, discriminator miss, or transcript hash mismatch).

Why the *name* of the spawn path is never trusted
--------------------------------------------------
LEARNINGS.md:293 established that a spawned teammate can inherit Claude's full toolset and simply
do the work itself while the run is labeled genuine delegation. The only reliable discriminator
was grepping the transcript for an actual ``agy --model`` Bash call. This gate operationalizes
that: the per-plugin ``discriminator`` regex in the manifest, matched against real recorded
tool-call commands, is the trust signal — never the label on the spawn.

Design for testability
-----------------------
Pure functions (``detect_bridge_version_bumps``, ``verify_proof``, ``classify_transcript``,
``sweep``) operate on in-memory data and are unit-tested directly. The CLI wires git and the
filesystem around them. ``--dry-run`` reports findings but always exits 0, so the two modes are
independently invocable as a smoke check (``--mode version-gate --dry-run`` /
``--mode fleet-sweep --dry-run``) without a real diff or seeded artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess  # nosec B404 - git plumbing for the PR base ref, fixed argv, no shell
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "marketplace" / "bridge_plugins.json"
DEFAULT_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
DEFAULT_PROOFS_DIR = REPO_ROOT / "docs" / "delegation-proofs"
DEFAULT_BASE_REF = "origin/main"

PROOF_SCHEMA = "delegation-proof.v1"
MANIFEST_SCHEMA = "bridge-plugins.v1"

# Tool names that mean *Claude itself* edited files — the fingerprint of an unrecorded fallback
# where the "delegated" teammate was really Claude doing the work (LEARNINGS.md:293).
CLAUDE_FILE_TOOLS = frozenset({"Edit", "MultiEdit", "NotebookEdit", "Write"})

REQUIRED_PROOF_FIELDS = (
    "schema",
    "plugin",
    "version",
    "run_id",
    "bridge_command",
    "external_tool_calls",
    "actor",
)


class ManifestError(Exception):
    """The bridge-plugins manifest is missing or malformed. Fail loud, never silent-pass."""


# --------------------------------------------------------------------------- manifest


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and structurally validate the bridge-plugins manifest.

    Raises ManifestError on a missing file, invalid JSON, or a malformed bridge entry so a
    corrupted manifest fails the gate loudly instead of silently letting bumps through.
    """

    if not path.exists():
        raise ManifestError(f"bridge-plugins manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"bridge-plugins manifest is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"bridge-plugins manifest must be a JSON object: {path}")
    if data.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError(f"bridge-plugins manifest schema must be {MANIFEST_SCHEMA!r}: {path}")
    bridges = data.get("bridges")
    if not isinstance(bridges, dict) or not bridges:
        raise ManifestError(f"bridge-plugins manifest 'bridges' must be a non-empty object: {path}")
    for name, spec in bridges.items():
        if not isinstance(spec, dict) or "discriminator" not in spec:
            raise ManifestError(
                f"bridge '{name}' must be an object carrying a 'discriminator' regex: {path}"
            )
        try:
            re.compile(str(spec["discriminator"]))
        except re.error as exc:
            raise ManifestError(
                f"bridge '{name}' discriminator is not a valid regex ({path}): {exc}"
            ) from exc
    return data


def bridge_names(manifest: dict[str, Any]) -> set[str]:
    return set(manifest["bridges"].keys())


def discriminator_for(manifest: dict[str, Any], plugin: str) -> re.Pattern[str]:
    return re.compile(str(manifest["bridges"][plugin]["discriminator"]))


# --------------------------------------------------------------------- version gate


@dataclass(frozen=True)
class VersionBump:
    plugin: str
    old_version: str | None
    new_version: str


def _marketplace_versions(marketplace: dict[str, Any]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for entry in marketplace.get("plugins", []):
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            version = entry.get("version")
            if isinstance(version, str):
                versions[entry["name"]] = version
    return versions


def detect_bridge_version_bumps(
    base_marketplace: dict[str, Any],
    head_marketplace: dict[str, Any],
    bridges: set[str],
) -> list[VersionBump]:
    """Return every bridge plugin whose marketplace version changed between base and head."""

    base = _marketplace_versions(base_marketplace)
    head = _marketplace_versions(head_marketplace)
    bumps: list[VersionBump] = []
    for plugin in sorted(bridges):
        new = head.get(plugin)
        if new is None:
            continue  # plugin not present in head marketplace; nothing to gate
        old = base.get(plugin)
        if old != new:
            bumps.append(VersionBump(plugin=plugin, old_version=old, new_version=new))
    return bumps


# ------------------------------------------------------------------- proof artifacts


@dataclass(frozen=True)
class Proof:
    path: Path
    data: dict[str, Any]

    @property
    def plugin(self) -> str:
        return str(self.data.get("plugin", ""))

    @property
    def version(self) -> str:
        return str(self.data.get("version", ""))


def load_proofs(proofs_dir: Path) -> list[Proof]:
    """Load every ``*.json`` proof artifact under the proofs directory (recursively)."""

    if not proofs_dir.is_dir():
        return []
    proofs: list[Proof] = []
    for path in sorted(proofs_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            proofs.append(Proof(path=path, data={"__parse_error__": True}))
            continue
        if isinstance(data, dict):
            proofs.append(Proof(path=path, data=data))
    return proofs


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_proof(proof: Proof, discriminator: re.Pattern[str], *, base_dir: Path) -> list[str]:
    """Return the list of reasons this proof does not verify (empty list == verified).

    A verifying proof: has the right schema, all required fields, a ``bridge_command`` that
    matches the plugin's discriminator (proving a genuine bridge invocation, not a spawn-path
    label), a non-empty ``external_tool_calls`` list (proving real work, not a silent no-op), a
    non-empty ``actor`` token (proving the write is attributable, not orphaned), and — when the
    attested transcript file exists — a ``transcript_sha256`` that matches it (an intact chain).
    """

    data = proof.data
    reasons: list[str] = []

    if data.get("__parse_error__"):
        return ["proof artifact is not valid JSON"]
    if data.get("schema") != PROOF_SCHEMA:
        reasons.append(f"schema must be {PROOF_SCHEMA!r} (got {data.get('schema')!r})")
    for key in REQUIRED_PROOF_FIELDS:
        if key not in data:
            reasons.append(f"missing required field '{key}'")

    bridge_command = data.get("bridge_command")
    if isinstance(bridge_command, str):
        if not discriminator.search(bridge_command):
            reasons.append(
                "bridge_command does not match the plugin discriminator "
                "(spawn-path label is not proof of a genuine bridge run)"
            )
    elif "bridge_command" in data:
        reasons.append("bridge_command must be a string")

    calls = data.get("external_tool_calls")
    if isinstance(calls, list):
        if not calls:
            reasons.append("external_tool_calls is empty (silent no-op: no attributable work)")
    elif "external_tool_calls" in data:
        reasons.append("external_tool_calls must be a list")

    actor = data.get("actor")
    if "actor" in data and (not isinstance(actor, str) or not actor.strip()):
        reasons.append("actor is empty (untokened orphan write: no traceable actor)")

    # Chain link: recompute the transcript hash when the file is reachable.
    transcript = data.get("transcript")
    recorded_hash = data.get("transcript_sha256")
    if isinstance(transcript, str) and transcript:
        transcript_path = (base_dir / transcript).resolve()
        if not transcript_path.exists():
            transcript_path = (proof.path.parent / transcript).resolve()
        if transcript_path.exists() and isinstance(recorded_hash, str):
            actual = _sha256_file(transcript_path)
            if actual != recorded_hash:
                reasons.append(
                    "broken proof chain: transcript_sha256 does not match the attested "
                    f"transcript ({transcript})"
                )
    return reasons


def find_valid_proof(
    proofs: list[Proof],
    *,
    plugin: str,
    version: str,
    discriminator: re.Pattern[str],
    base_dir: Path,
) -> Proof | None:
    """First proof for this plugin+version that fully verifies, or None."""

    for proof in proofs:
        if (
            proof.plugin == plugin
            and proof.version == version
            and not verify_proof(proof, discriminator, base_dir=base_dir)
        ):
            return proof
    return None


# ----------------------------------------------------------------- transcript sweep


@dataclass(frozen=True)
class Finding:
    category: (
        str  # silent_no_op | unrecorded_fallback | untokened_orphan_write | broken_proof_chain
    )
    source: str
    detail: str

    def render(self) -> str:
        return f"[{self.category}] {self.source}: {self.detail}"


@dataclass
class TranscriptSignals:
    bridge_command_seen: bool = False
    claude_file_tool_seen: bool = False
    external_tool_calls: int = 0
    orphan_writes: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def _event_tool_name(event: dict[str, Any]) -> str | None:
    for key in ("tool_name", "name"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name")
                    if isinstance(name, str):
                        return name
    return None


def _event_command(event: dict[str, Any]) -> str | None:
    for key in ("command", "cmd"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    for container_key in ("arguments", "input"):
        container = event.get(container_key)
        if isinstance(container, dict):
            value = container.get("command")
            if isinstance(value, str):
                return value
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                tool_input = item.get("input")
                if isinstance(tool_input, dict):
                    value = tool_input.get("command")
                    if isinstance(value, str):
                        return value
    return None


def scan_transcript_signals(text: str, discriminator: re.Pattern[str]) -> TranscriptSignals:
    """Parse a JSONL transcript into the signals the failure taxonomy is derived from.

    Each non-blank line is a JSON event. A command matching the discriminator counts as a genuine
    external-tool call; a Claude file-edit tool marks a possible fallback; a ``write`` event with
    no ``actor``/attribution token is an untokened orphan write.
    """

    signals = TranscriptSignals()
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            signals.evidence.append(f"line {lineno}: invalid json")
            continue
        if not isinstance(event, dict):
            continue

        tool_name = _event_tool_name(event)
        command = _event_command(event)
        if command and discriminator.search(command):
            signals.bridge_command_seen = True
            signals.external_tool_calls += 1
            signals.evidence.append(f"line {lineno}: bridge command via {tool_name or 'unknown'}")
        if tool_name in CLAUDE_FILE_TOOLS:
            signals.claude_file_tool_seen = True
            signals.evidence.append(f"line {lineno}: Claude file tool {tool_name}")

        # Explicit write events must carry a traceable actor. A write with an absent/empty actor
        # is an untokened orphan write regardless of what else the transcript shows.
        if event.get("type") == "write" or event.get("event") == "write":
            actor = event.get("actor")
            paths = event.get("paths") or event.get("path") or "<unknown>"
            if not isinstance(actor, str) or not actor.strip():
                signals.orphan_writes.append(f"line {lineno}: write to {paths}")
    return signals


def classify_transcript(text: str, discriminator: re.Pattern[str], *, source: str) -> list[Finding]:
    """Classify one claimed bridge transcript against the failure taxonomy.

    A transcript reaching this function is *claimed* to be a bridge-delegated run (it lives under
    the sweep's proof/transcript surface). Findings:

    * untokened orphan writes are always reported;
    * if a genuine bridge command was seen, the run is real (only orphan writes can still fail it);
    * otherwise it is an unrecorded fallback (Claude file tools present) or a silent no-op (no
      external work at all).
    """

    signals = scan_transcript_signals(text, discriminator)
    findings: list[Finding] = []

    for orphan in signals.orphan_writes:
        findings.append(Finding("untokened_orphan_write", source, orphan))

    if signals.bridge_command_seen:
        return findings  # genuine bridge run; orphan-write findings (if any) still stand

    if signals.claude_file_tool_seen:
        findings.append(
            Finding(
                "unrecorded_fallback",
                source,
                "claimed bridge run but the transcript shows Claude file-edit tools and no "
                "genuine bridge command (the delegated teammate was really Claude)",
            )
        )
    else:
        findings.append(
            Finding(
                "silent_no_op",
                source,
                "claimed bridge run with zero external-tool calls matching the discriminator "
                "(bridge invoked but produced no attributable work)",
            )
        )
    return findings


def _resolve_transcript(proof: Proof, base_dir: Path) -> Path | None:
    transcript = proof.data.get("transcript")
    if not isinstance(transcript, str) or not transcript:
        return None
    candidate = (base_dir / transcript).resolve()
    if candidate.exists():
        return candidate
    candidate = (proof.path.parent / transcript).resolve()
    return candidate if candidate.exists() else None


def sweep(
    manifest: dict[str, Any],
    proofs: list[Proof],
    *,
    base_dir: Path,
    standalone_transcripts: list[Path] | None = None,
) -> list[Finding]:
    """Run the fleet delegation-integrity sweep over all proofs and standalone transcripts."""

    findings: list[Finding] = []
    bridges = bridge_names(manifest)

    for proof in proofs:
        plugin = proof.plugin
        if plugin not in bridges:
            findings.append(
                Finding(
                    "broken_proof_chain",
                    str(proof.path),
                    f"proof declares plugin {plugin!r} which is not a registered bridge",
                )
            )
            continue
        discriminator = discriminator_for(manifest, plugin)
        reasons = verify_proof(proof, discriminator, base_dir=base_dir)
        for reason in reasons:
            findings.append(Finding("broken_proof_chain", str(proof.path), reason))

        transcript_path = _resolve_transcript(proof, base_dir)
        if transcript_path is not None:
            findings.extend(
                classify_transcript(
                    transcript_path.read_text(encoding="utf-8"),
                    discriminator,
                    source=str(transcript_path),
                )
            )

    for transcript_path in standalone_transcripts or []:
        # A standalone transcript is not tied to one plugin; check it against every registered
        # bridge discriminator and only flag it when NO bridge's discriminator matches.
        text = transcript_path.read_text(encoding="utf-8")
        matched = False
        merged: list[Finding] = []
        for plugin in sorted(bridges):
            discriminator = discriminator_for(manifest, plugin)
            plugin_findings = classify_transcript(text, discriminator, source=str(transcript_path))
            if not any(
                f.category in {"silent_no_op", "unrecorded_fallback"} for f in plugin_findings
            ):
                matched = True
            merged = plugin_findings  # keep the last plugin's view for orphan/no-op detail
        if matched:
            findings.extend(f for f in merged if f.category == "untokened_orphan_write")
        else:
            findings.extend(merged)
    return findings


# ------------------------------------------------------------------------- git glue


def _git_show_json(ref: str, path: str) -> dict[str, Any]:
    """Return the JSON content of ``path`` at ``ref`` (empty dict if absent at that ref)."""

    result = subprocess.run(  # nosec B603 B607 - fixed argv, no shell, trusted git plumbing
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# ------------------------------------------------------------------------------- CLI


def _load_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError(f"expected a JSON object in {path}")
    return data


def run_version_gate(args: argparse.Namespace) -> tuple[int, list[str]]:
    manifest = load_manifest(args.manifest)
    bridges = bridge_names(manifest)

    head_marketplace = _load_json_file(args.marketplace)
    if args.base_marketplace is not None:
        base_marketplace = _load_json_file(args.base_marketplace)
    else:
        rel = str(args.marketplace.resolve().relative_to(REPO_ROOT))
        base_marketplace = _git_show_json(args.base_ref, rel)

    bumps = detect_bridge_version_bumps(base_marketplace, head_marketplace, bridges)
    proofs = load_proofs(args.proofs_dir)

    lines: list[str] = []
    failed = False
    for bump in bumps:
        discriminator = discriminator_for(manifest, bump.plugin)
        proof = find_valid_proof(
            proofs,
            plugin=bump.plugin,
            version=bump.new_version,
            discriminator=discriminator,
            base_dir=args.proofs_dir,
        )
        if proof is None:
            failed = True
            lines.append(
                f"VIOLATION: {bump.plugin} marketplace version "
                f"{bump.old_version} -> {bump.new_version} has no valid delegation-proof "
                f"artifact (schema {PROOF_SCHEMA}, version {bump.new_version}) under "
                f"{args.proofs_dir}."
            )
        else:
            lines.append(f"OK: {bump.plugin} {bump.new_version} backed by proof {proof.path.name}")
    if not bumps:
        lines.append("version-gate: no bridge-plugin marketplace version changes in this diff.")
    return (1 if failed else 0), lines


def run_fleet_sweep(args: argparse.Namespace) -> tuple[int, list[str]]:
    manifest = load_manifest(args.manifest)
    proofs = load_proofs(args.proofs_dir)
    standalone: list[Path] = []
    if args.transcripts_dir is not None and args.transcripts_dir.is_dir():
        standalone = sorted(args.transcripts_dir.rglob("*.jsonl"))

    findings = sweep(manifest, proofs, base_dir=args.proofs_dir, standalone_transcripts=standalone)
    lines = [f.render() for f in findings]
    if not findings:
        swept = len(proofs) + len(standalone)
        lines.append(f"fleet-sweep: {swept} artifact(s) swept, no delegation-integrity findings.")
    return (1 if findings else 0), lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("version-gate", "fleet-sweep"),
        help="Which guard to run.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--marketplace", type=Path, default=DEFAULT_MARKETPLACE)
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help="Git ref for the PR base marketplace.json (version-gate).",
    )
    parser.add_argument(
        "--base-marketplace",
        type=Path,
        default=None,
        help="Override the base marketplace.json with a file instead of `git show` (testing).",
    )
    parser.add_argument("--proofs-dir", type=Path, default=DEFAULT_PROOFS_DIR)
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=None,
        help="Additional directory of standalone bridge `.jsonl` transcripts (fleet-sweep).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report findings but always exit 0 (smoke check that a mode is invocable).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "version-gate":
            code, lines = run_version_gate(args)
        else:
            code, lines = run_fleet_sweep(args)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    stream = sys.stderr if code else sys.stdout
    for line in lines:
        print(line, file=stream)
    if code and not args.dry_run:
        print(
            f"\ndelegation-integrity ({args.mode}): FAILED — see findings above.",
            file=sys.stderr,
        )
    if args.dry_run:
        print(f"delegation-integrity ({args.mode}): --dry-run, not failing the build.")
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())

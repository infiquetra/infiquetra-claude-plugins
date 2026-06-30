"""Static prompt-contract tests for packaged agy surfaces."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "agy"
WRAPPER_PATH = "plugins/agy/scripts/agy_delegate.py"


def _read(relative_path: str) -> str:
    return (PLUGIN_ROOT / relative_path).read_text(encoding="utf-8")


def _frontmatter(relative_path: str) -> dict[str, str]:
    lines = _read(relative_path).splitlines()
    assert lines[0] == "---"

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return data
        if ": " in line:
            key, value = line.split(": ", 1)
            data[key] = value.strip()

    raise AssertionError(f"{relative_path} has no closing frontmatter marker")


def _assert_all_present(text: str, required: tuple[str, ...]) -> None:
    missing = [needle for needle in required if needle not in text]
    assert missing == []


def test_bridge_agents_are_bash_only_and_single_wrapper_run() -> None:
    required = (
        "tools: Bash",
        WRAPPER_PATH,
        "exactly once per delegated turn",
        "Direct Read/Edit/Write solving",
        "contract breach",
        "Do not invoke raw `agy`",
        "Do not use background, detached",
        "Do not commit, push, force-push, rewrite history",
        "change remote state",
        "locally as a fallback",
    )

    for agent in ("agy-coder", "agy-reviewer"):
        relative_path = f"agents/{agent}.md"
        text = _read(relative_path)

        assert _frontmatter(relative_path)["tools"] == "Bash"
        _assert_all_present(text, required)


def test_coder_prompt_requires_strong_packet_and_write_gate() -> None:
    text = _read("agents/agy-coder.md")

    _assert_all_present(
        text,
        (
            "expert software engineer",
            "read-broad/write-narrow",
            "exact write-set",
            "PLAN_GAP:",
            "TEST_CONFLICT:",
            "PATH_MISSING:",
            "Verification commands",
            "run report",
            "Default to `mode=patch-only`",
            "Use `mode=auto-if-clean` only",
            "explicit repo-relative write-set",
            "required verification commands",
            "`apply_policy=apply-if-clean`",
        ),
    )


def test_reviewer_prompt_defaults_and_lenses_are_single_agent_contract() -> None:
    text = _read("agents/agy-reviewer.md")

    _assert_all_present(
        text,
        (
            "Default to `role=reviewer`, `mode=no-write`, and `review_lens=adversarial`",
            "`adversarial`",
            "`quality`",
            "`scope-gap`",
            "`security-ops`",
            "do not create additional reviewer agents",
        ),
    )


def test_delegate_command_documents_wrapper_syntax_not_raw_agy() -> None:
    text = _read("commands/delegate.md")

    _assert_all_present(
        text,
        (
            "role=<coder|reviewer>",
            "mode=<no-write|patch-only|auto-if-clean>",
            "evidence=<minimal|summary|full>",
            "write-set=<repo-relative-path>",
            "verification=<command>",
            "review_lens=<adversarial|quality|scope-gap|security-ops>",
            "--write-set",
            "--verification-command",
            "--verification-required",
            WRAPPER_PATH,
            "Do not invoke raw `agy` directly",
        ),
    )
    assert "```bash\nagy " not in text


def test_skill_and_reference_share_evidence_and_write_gate_contract() -> None:
    skill = _read("skills/agy-delegate/SKILL.md")
    reference = _read("skills/agy-delegate/references/delegation-contract.md")

    for text in (skill, reference):
        _assert_all_present(
            text,
            (
                "The wrapper is the only supported execution path",
                "Direct Read/Edit/Write",
                "solving",
                "contract breach",
                "mode=patch-only",
                "mode=auto-if-clean",
                "explicit repo-relative write-set",
                "apply_policy=apply-if-clean",
                "required verification commands",
                "role=reviewer",
                "mode=no-write",
                "review_lens=adversarial",
                "adversarial",
                "quality",
                "scope-gap",
                "security-ops",
                "evidence",
                WRAPPER_PATH,
            ),
        )


def test_prompts_do_not_advertise_local_solving_affordances() -> None:
    surfaces = {
        "agents/agy-coder.md": _read("agents/agy-coder.md"),
        "agents/agy-reviewer.md": _read("agents/agy-reviewer.md"),
        "commands/delegate.md": _read("commands/delegate.md"),
        "skills/agy-delegate/SKILL.md": _read("skills/agy-delegate/SKILL.md"),
        "skills/agy-delegate/references/delegation-contract.md": _read(
            "skills/agy-delegate/references/delegation-contract.md"
        ),
    }
    banned_fragments = (
        "use Read",
        "use Edit",
        "use Write",
        "use MultiEdit",
        "solve locally",
        "local fallback is allowed",
        "may call raw `agy`",
        "invoke raw `agy` directly when",
        "run `agy` directly",
        "nohup python3 plugins/agy/scripts/agy_delegate.py",
        "&\n",
    )

    for path, text in surfaces.items():
        lowered = text.lower()
        for fragment in banned_fragments:
            assert fragment.lower() not in lowered, f"{path} advertises {fragment!r}"

"""Guard tests for the #287 U4 sandbox spawn-site inventory.

Ensures the inventory doc (plugins/saga/references/sandbox-spawn-sites.md) stays in sync with the
four in-scope verify/review-class SKILL.md files, and that each of those skills actually wires
`saga:readonly-verifier` at its spawn site.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent

INVENTORY_PATH = ROOT / "plugins/saga/references/sandbox-spawn-sites.md"

IN_SCOPE_SKILLS = {
    "brainstorm": ROOT / "plugins/saga/skills/brainstorm/SKILL.md",
    "code-review": ROOT / "plugins/saga/skills/code-review/SKILL.md",
    "qa": ROOT / "plugins/saga/skills/qa/SKILL.md",
    "investigate": ROOT / "plugins/saga/skills/investigate/SKILL.md",
    "resume": ROOT / "plugins/saga/skills/resume/SKILL.md",
}


def test_spawn_site_inventory_lists_all_verify_skills() -> None:
    assert INVENTORY_PATH.exists(), f"missing inventory doc: {INVENTORY_PATH}"
    text = INVENTORY_PATH.read_text(encoding="utf-8")

    for skill_name, skill_path in IN_SCOPE_SKILLS.items():
        assert skill_name in text, f"inventory doc does not mention skill: {skill_name}"
        rel_path = skill_path.relative_to(ROOT).as_posix()
        assert rel_path in text, f"inventory doc does not mention skill file path: {rel_path}"


def test_in_scope_skills_reference_readonly_verifier() -> None:
    for skill_name, skill_path in IN_SCOPE_SKILLS.items():
        assert skill_path.exists(), f"missing skill file: {skill_path}"
        text = skill_path.read_text(encoding="utf-8")
        assert "readonly-verifier" in text, (
            f"{skill_name} SKILL.md does not reference readonly-verifier at its spawn site"
        )

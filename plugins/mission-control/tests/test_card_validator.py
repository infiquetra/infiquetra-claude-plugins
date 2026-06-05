"""Tests for the card_validator shim.

The shim mirrors home-lab/.../card_validator.py's high-leverage checks:
6 required H3 headers, AC has ≥1 checklist item, Verification has ≥1
fenced code block, Files-expected has ≥1 path-like line, no placeholders.
"""

import sys
from pathlib import Path

# Make scripts importable as a package: tests/ is sibling of scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402

VALID_BODY = """### Objective
Add schema validator that gates plan-review on structured card fields.

### Acceptance criteria
- [ ] Validator runs on `projects_v2_item` webhook when status becomes Ready
- [ ] Cards missing required fields get a `needs-author-action` label

### Out-of-scope / non-goals
- Do NOT change the planner prompt in this card
- Do NOT add new required fields beyond those in the plan spec

### Files expected to change
ansible/roles/hermes_orchestrator/files/card_validator.py
ansible/roles/hermes_orchestrator/files/handlers.py

### Tests to add or update
tests/test_card_validator.py::test_accepts_fully_populated_card

### Verification
```bash
cd ansible/roles/hermes_orchestrator/files
pytest tests/test_card_validator.py -v
```

### Notes / conventions
- GitHub issue forms render fields as `### <Field Label>` headers

### Context library links
- architecture_decisions: https://github.com/infiquetra/blueprint/adr/042.md
"""


def test_accepts_fully_populated_card() -> None:
    is_valid, errors = sdlc_manager.validate_card_body(VALID_BODY)
    assert is_valid, f"Expected valid; got errors: {errors}"
    assert errors == []


def test_rejects_missing_required_header() -> None:
    body = VALID_BODY.replace("### Verification\n", "### Removed\n", 1)
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Missing required H3 sections" in e and "Verification" in e for e in errors)


def test_rejects_missing_checklist_in_acceptance_criteria() -> None:
    body = VALID_BODY.replace(
        "- [ ] Validator runs on `projects_v2_item` webhook when status becomes Ready\n"
        "- [ ] Cards missing required fields get a `needs-author-action` label",
        "Validator runs on webhook events. Cards without required fields fail.",
    )
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Acceptance criteria" in e and "checklist" in e for e in errors)


def test_rejects_missing_code_block_in_verification() -> None:
    body = VALID_BODY.replace(
        "```bash\ncd ansible/roles/hermes_orchestrator/files\n"
        "pytest tests/test_card_validator.py -v\n```",
        "Run pytest in the orchestrator role directory.",
    )
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Verification" in e and "fenced code block" in e for e in errors)


def test_rejects_missing_path_line_in_files_expected() -> None:
    body = VALID_BODY.replace(
        "ansible/roles/hermes_orchestrator/files/card_validator.py\n"
        "ansible/roles/hermes_orchestrator/files/handlers.py",
        "TBD — will figure out at implementation time",
    )
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Files expected to change" in e and "path-like" in e for e in errors)


def test_rejects_placeholder_only_section() -> None:
    body = VALID_BODY.replace(
        "Add schema validator that gates plan-review on structured card fields.",
        "_No response_",
    )
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Objective" in e and "placeholder" in e for e in errors)


def test_handles_empty_body() -> None:
    is_valid, errors = sdlc_manager.validate_card_body("")
    assert not is_valid
    # All 6 required sections missing
    assert any("Missing required H3" in e for e in errors)


def test_section_split_handles_h3_with_trailing_whitespace() -> None:
    # Some GitHub markdown renderers add trailing whitespace after the title;
    # the parser must accept it.
    body = VALID_BODY.replace("### Objective\n", "### Objective   \n", 1)
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert is_valid, f"Expected valid even with trailing whitespace; got: {errors}"


def test_h2_headers_do_not_match_h3_parser() -> None:
    # An H2 with the same name should NOT be treated as an H3 section
    body = VALID_BODY.replace("### Objective", "## Objective")
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert not is_valid
    assert any("Missing required H3 sections" in e and "Objective" in e for e in errors)


def test_optional_sections_not_required() -> None:
    # Strip the optional Notes + Context library links sections — body should still validate
    body = VALID_BODY
    body = body.split("### Notes / conventions")[0].rstrip() + "\n"
    is_valid, errors = sdlc_manager.validate_card_body(body)
    assert is_valid, f"Expected valid without optional sections; got: {errors}"


def test_required_headers_match_actual_issue_templates() -> None:
    """Drift guard: the validator's _REQUIRED_H3_HEADERS list must match the
    `label:` fields in `infiquetra-sdlc/.github/ISSUE_TEMPLATE/{capability,
    enhancement,defect}.yml`. If a template adds/renames a section, this
    test fails so the validator can be updated in the same PR.

    This is the test that PR #114's review caught was missing — the original
    validator used 'Out-of-scope or non-goals' (with 'or') while the actual
    templates use 'Out-of-scope / non-goals' (with '/'), and no test was
    pinning the contract end-to-end."""
    import os

    sdlc_path = Path(
        os.environ.get("INFIQUETRA_SDLC_PATH", Path.home() / "workspace/infiquetra/infiquetra-sdlc")
    )
    template_dir = sdlc_path / ".github" / "ISSUE_TEMPLATE"
    if not template_dir.exists():
        # Skip if running outside the developer's workspace (e.g., on a
        # build agent without the sibling repo). The drift guard runs in
        # CI when the repos are checked out together.
        import pytest

        pytest.skip(f"Templates not at {template_dir}; skipping drift check")

    # Extract `label:` strings from the 3 actionable templates
    import re as _re

    template_headers: dict[str, set[str]] = {}
    for tmpl in ("capability.yml", "enhancement.yml", "defect.yml"):
        text = (template_dir / tmpl).read_text()
        labels = set(_re.findall(r"^\s+label:\s*(.+?)\s*$", text, _re.MULTILINE))
        template_headers[tmpl] = labels

    # Every required validator header must appear as a label in every
    # actionable template
    for tmpl, labels in template_headers.items():
        for required in sdlc_manager._REQUIRED_H3_HEADERS:
            assert required in labels, (
                f"Validator requires '{required}' but {tmpl} doesn't have a "
                f"matching `label:` field. Templates have: {sorted(labels)}"
            )

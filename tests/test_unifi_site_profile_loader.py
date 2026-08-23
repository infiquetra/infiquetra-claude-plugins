"""The Claude adapter's site-profile loader, and the record of what was relocated into it.

Why this file exists
--------------------
The ``unifi-network-ops`` agent used to carry one operator's lab topology as prose: a
controller address, four subnets, three host ranges, a Proxmox master, and a camera count.
That knowledge was real and worth keeping, but a plugin every installation receives is the
wrong place for one site's addressing. The topology moved into an operator site profile,
and ``site_profile_loader.py`` is how the Claude adapter reads one.

Relocation is the risky half. Deleting the text would have been trivial; moving it without
losing a fact is what needs a test, so :data:`RELOCATED_SITE_PROFILE` below is the profile
the topology moved into, and :data:`PRIOR_AGENT_FACTS` enumerates what the agent said before
commit ``c1659d83``. Every fact is asserted present in the profile and asserted absent from
the agent, one at a time, so relocation cannot silently drop one and removal cannot silently
skip one.

**Relocation preserves; it does not enrich.** The prior agent text stated exactly one trust
role — the main LAN was "trusted" — and said nothing anywhere about criticality or
ownership. Those fields are therefore omitted from every subject that had no such statement,
which the loader reports as ``unknown``. Reading "isolated" as ``untrusted`` would be an
inference, and the no-inference rule this contract exists to enforce forbids exactly that.

**Where this profile goes next.** The plan's unit U8 transports this content into the private
``home-lab`` repository as ``knowledge/unifi-site-profile.yaml`` and deploys it to the
machine-local runtime path. It lives here as the relocation record — the source U8 transports
from, and the evidence that nothing was lost on the way out of the agent.

The contract itself is ``urn:infiquetra:unifi:site-profile:1.1``, released by Run A on branch
``orch/orch-2026-08-22-unifi-run-a`` at commit ``097909d7`` of ``infiquetra-agent-plugins``.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "unifi"
LOADER_PATH = PLUGIN_ROOT / "skills" / "unifi-network" / "scripts" / "site_profile_loader.py"
AGENT_DOC = PLUGIN_ROOT / "agents" / "unifi-network-ops.md"


def _load_module() -> ModuleType:
    """Import the loader by path; the plugin directory is not an importable package."""
    spec = importlib.util.spec_from_file_location("site_profile_loader", LOADER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because ``@dataclass`` resolves annotations through
    # ``sys.modules[cls.__module__]``; without this the decorator raises on an absent entry.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


loader = _load_module()


# --------------------------------------------------------------------------------------
# The relocated profile, and the prior agent text it came from
# --------------------------------------------------------------------------------------

#: The Infiquetra home-lab topology in the portable profile shape. Authored here by the
#: relocation, transported by U8 into the private ``home-lab`` repository.
RELOCATED_SITE_PROFILE: dict[str, Any] = {
    "schema_version": "1.0",
    "site": {
        "identifier": "infiquetra-home-lab",
        "description": (
            "Infiquetra home lab. A UniFi Dream Machine Pro running UniFi OS 3.x hosts both "
            "the Network and Protect applications, over a fully managed network of multiple "
            "VLANs with firewall rules and WPA3 wireless."
        ),
    },
    "subjects": [
        {
            "kind": "device",
            "identifier": "10.220.1.1",
            "trust_role": "trusted",
            "notes": (
                "UniFi Dream Machine Pro running UniFi OS 3.x. The controller for the "
                "Network application and for Protect, whose built-in network video recorder "
                "manages the cameras."
            ),
        },
        {
            "kind": "device",
            "identifier": "protect-cameras",
            "notes": (
                "Five or more UniFi Protect cameras, G4 series, managed by the Dream Machine "
                "Pro's built-in network video recorder."
            ),
        },
        {
            "kind": "network",
            "identifier": "10.220.1.0/24",
            "trust_role": "trusted",
            "notes": "Main LAN, VLAN 1, described as trusted.",
        },
        {
            "kind": "network",
            "identifier": "10.220.2.0/24",
            "notes": "Management network, VLAN 2, carrying infrastructure.",
        },
        {
            "kind": "network",
            "identifier": "10.220.30.0/24",
            "notes": "IoT network, VLAN 30, described as isolated.",
        },
        {
            "kind": "network",
            "identifier": "10.220.40.0/24",
            "notes": "Guest network, VLAN 40, described as isolated and internet-only.",
        },
        {
            "kind": "host",
            "identifier": "10.220.1.7",
            "notes": "Proxmox master, hostname r420, on the main LAN.",
        },
        {
            "kind": "host",
            "identifier": "10.220.1.50-57",
            "notes": "Agent virtual machines, on the main LAN.",
        },
        {
            "kind": "host",
            "identifier": "10.220.1.60-63",
            "notes": "Service virtual machines, on the main LAN.",
        },
    ],
    "intended_policies": [
        {
            "identifier": "iot-isolated",
            "description": "The IoT network on VLAN 30 is isolated.",
            "applies_to": ["10.220.30.0/24"],
        },
        {
            "identifier": "guest-isolated-internet-only",
            "description": (
                "The guest network on VLAN 40 is isolated and permitted internet access only."
            ),
            "applies_to": ["10.220.40.0/24"],
        },
    ],
}

#: Every fact the agent stated before the relocation, as
#: ``(label, profile_needle, agent_pattern)``. The needle must appear in the profile's
#: serialized form, which proves nothing was lost; the pattern must NOT match the current
#: agent text, which proves nothing was left behind. Read off
#: ``c1659d83:plugins/unifi/agents/unifi-network-ops.md``, sections "Role" and "Lab Topology
#: Knowledge".
#:
#: The pattern is a regular expression rather than a substring for one fact only. "trusted"
#: still occurs inside "untrusted" in the no-inference rule's worked example, which states
#: the opposite of a site fact — naming something as what may not be concluded. The lookbehind
#: keeps that sentence legal while a bare "trusted" claim would still fail.
PRIOR_AGENT_FACTS: tuple[tuple[str, str, str], ...] = (
    ("controller address", "10.220.1.1", r"10\.220\.1\.1"),
    ("controller model", "UniFi Dream Machine Pro", r"UniFi Dream Machine Pro"),
    ("controller operating system", "UniFi OS 3.x", r"UniFi OS 3\.x"),
    ("main LAN subnet", "10.220.1.0/24", r"10\.220\.1\.0/24"),
    ("main LAN vlan", "VLAN 1", r"VLAN 1\b"),
    ("main LAN trust", "trusted", r"(?<!un)\btrusted\b"),
    ("management subnet", "10.220.2.0/24", r"10\.220\.2\.0/24"),
    ("management vlan", "VLAN 2", r"VLAN 2\b"),
    ("management role", "infrastructure", r"\binfrastructure\b"),
    ("iot subnet", "10.220.30.0/24", r"10\.220\.30\.0/24"),
    ("iot vlan", "VLAN 30", r"VLAN 30\b"),
    ("iot isolation", "isolated", r"\bisolated\b"),
    ("guest subnet", "10.220.40.0/24", r"10\.220\.40\.0/24"),
    ("guest vlan", "VLAN 40", r"VLAN 40\b"),
    ("guest internet-only", "internet-only", r"internet-only"),
    ("proxmox master address", "10.220.1.7", r"10\.220\.1\.7"),
    ("proxmox master hostname", "r420", r"\br420\b"),
    ("agent virtual machine range", "10.220.1.50-57", r"10\.220\.1\.50"),
    ("service virtual machine range", "10.220.1.60-63", r"10\.220\.1\.60"),
    ("camera count", "Five or more", r"\b5\+"),
    ("camera series", "G4", r"\bG4\b"),
    ("camera recorder", "network video recorder", r"\bNVR\b"),
    ("wireless standard", "WPA3", r"\bWPA3\b"),
)

_IPV4_RE = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")


@pytest.fixture()
def profile_file(tmp_path: Path) -> Path:
    path = tmp_path / "site-profile.json"
    path.write_text(json.dumps(RELOCATED_SITE_PROFILE), encoding="utf-8")
    return path


def _write_profile(path: Path, document: dict[str, Any]) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _valid_profile() -> dict[str, Any]:
    """A deep copy, so a test that seeds a defect cannot corrupt the relocation record."""
    copied: dict[str, Any] = json.loads(json.dumps(RELOCATED_SITE_PROFILE))
    return copied


# --------------------------------------------------------------------------------------
# 0. The loader enforces the 1.1 contract the package documents
# --------------------------------------------------------------------------------------

_OPAQUE_TOKEN = "qY7vP2xK9rLm4aZbC8dEfGhJkNpQsTuWxYz1234567890"


def _profile_with_notes(version: str, notes: str) -> dict[str, Any]:
    document = _valid_profile()
    document["schema_version"] = version
    document["subjects"][0]["notes"] = notes
    return document


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_both_contract_versions_load(version: str) -> None:
    """The package documents ``1.1``; this loader ships inside that package.

    It was published pinned to ``1.0`` while the portable half advanced to ``1.1``, so an
    operator who wrote the document the package documents had it rejected here — one
    package disagreeing with itself.
    """
    loader.validate_profile(_profile_with_notes(version, "rack B, spare uplink"))


def test_an_unknown_contract_version_is_still_refused_outright() -> None:
    with pytest.raises(loader.UnsupportedSchemaVersionError):
        loader.validate_profile(_profile_with_notes("1.2", "rack B"))


@pytest.mark.parametrize("version", ["1.0", "1.1"])
@pytest.mark.parametrize(
    "notes",
    [
        f"authorization: Bearer {_OPAQUE_TOKEN}",
        f"authorization: Basic {_OPAQUE_TOKEN}",
        f"api_key={_OPAQUE_TOKEN}",
        "controller password=hunter2",
    ],
)
def test_a_credential_written_into_a_free_text_value_is_refused(version: str, notes: str) -> None:
    """``1.1`` is the version that says the secret-free guarantee covers values.

    A ``1.0`` document is held to it too, because a credential in a ``1.0`` profile is
    exactly as exposed. The scheme-word shapes matter on their own: grading only the first
    token of the value graded the word ``Bearer``, which carries no entropy, and cleared
    the credential standing behind it.
    """
    with pytest.raises(loader.ProfileInvalidError) as caught:
        loader.validate_profile(_profile_with_notes(version, notes))
    assert "credential value is not permitted" in str(caught.value)


@pytest.mark.parametrize(
    "notes",
    [
        f"authorization: Bearer <redacted> {_OPAQUE_TOKEN}",
        f"authorization: Bearer ${{UNIFI_API_KEY}} {_OPAQUE_TOKEN}",
        f"authorization: Bearer vault:infiquetra/unifi {_OPAQUE_TOKEN}",
    ],
)
def test_a_credential_hidden_behind_a_placeholder_is_refused(notes: str) -> None:
    """A placeholder between the scheme word and the credential ended the search.

    A fixed two-token window graded the placeholder, saw it names a secret rather
    than being one, and cleared the real credential standing behind it. The walk
    steps over both scheme words and placeholders instead of stopping at them.
    """
    document = _valid_profile()
    document["schema_version"] = "1.1"
    document["subjects"][0]["notes"] = notes
    with pytest.raises(loader.ProfileInvalidError) as caught:
        loader.validate_profile(document)
    assert "credential value is not permitted" in str(caught.value)


@pytest.mark.parametrize(
    "notes",
    [
        "api_key: vault:infiquetra/unifi#api_key",
        "password: <redacted>",
        "api_key: ${UNIFI_API_KEY}",
        "see the runbook for the rotation procedure",
        "the site uses certificate authentication end to end",
        # Prose whose first token is a long English word. Entropy per character
        # does not separate English from a credential -- `rotation` scores 2.50
        # against a 2.50 floor -- so grading token zero unconditionally rejected
        # these as credentials.
        "auth: rotation procedure documented in the runbook",
        "token: rotation happens quarterly",
        "secret: managed elsewhere",
        "auth: Rotation Procedure Documented",
        "secret: internationalization",
        # Carries a digit, but is never graded: the walk stops at the first
        # substantive token rather than searching the sentence.
        "auth: see ticket ABC-1234 for rotation",
    ],
)
def test_a_value_that_names_where_a_secret_lives_is_accepted(notes: str) -> None:
    """A profile is expected to point at where the credential lives, so these must pass.

    Ordinary prose has to pass too: several English words clear the entropy floor on their
    own, so a rule that graded every token of a value would fire on a sentence.
    """
    loader.validate_profile(_profile_with_notes("1.1", notes))


# --------------------------------------------------------------------------------------
# 1. The agent carries no address, and the relocation lost nothing
# --------------------------------------------------------------------------------------


def test_agent_definition_contains_no_address_literal() -> None:
    """No IPv4 literal survives anywhere in the agent definition."""
    found = _IPV4_RE.findall(AGENT_DOC.read_text(encoding="utf-8"))
    assert found == [], f"agent definition still names addresses: {sorted(set(found))}"


def test_plugin_contains_no_controller_address_literal() -> None:
    """The operator's controller address appears nowhere under ``plugins/unifi``."""
    offenders = subprocess.run(
        ["grep", "-rIlF", "10.220.", str(PLUGIN_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    assert offenders == [], f"operator addressing survives in: {offenders}"


@pytest.mark.parametrize(
    ("label", "needle", "pattern"),
    PRIOR_AGENT_FACTS,
    ids=[label for label, _, _ in PRIOR_AGENT_FACTS],
)
def test_every_prior_agent_fact_survives_in_the_relocated_profile(
    label: str, needle: str, pattern: str
) -> None:
    """Field by field, the profile still says what the agent used to say."""
    serialized = json.dumps(RELOCATED_SITE_PROFILE)
    assert needle in serialized, f"relocation lost the {label}: {needle!r}"


@pytest.mark.parametrize(
    ("label", "needle", "pattern"),
    PRIOR_AGENT_FACTS,
    ids=[label for label, _, _ in PRIOR_AGENT_FACTS],
)
def test_no_prior_agent_fact_is_left_behind_in_the_agent(
    label: str, needle: str, pattern: str
) -> None:
    """The agent no longer states any of it, so the profile is the only source."""
    match = re.search(pattern, AGENT_DOC.read_text(encoding="utf-8"))
    assert match is None, f"agent still states the {label}: {match.group(0)!r}"


def test_agent_points_at_the_loader_it_must_read() -> None:
    """A contract nothing presents is not reachable, so the agent names the loader."""
    text = AGENT_DOC.read_text(encoding="utf-8")
    assert "site_profile_loader.py" in text
    assert loader.ENVIRONMENT_VARIABLE in text
    assert loader.DISCOVERY_ONLY_MODE in text


def test_relocated_profile_validates_against_the_loader() -> None:
    """The relocation target is a valid document under the contract it claims."""
    assert loader.validate_profile(_valid_profile()) is not None


def test_relocated_profile_infers_no_intent_it_was_not_given() -> None:
    """Only the one trust role the prior text stated is present; nothing else was invented."""
    subjects = RELOCATED_SITE_PROFILE["subjects"]
    assert not any("criticality" in subject for subject in subjects)
    assert not any("ownership" in subject for subject in subjects)
    with_trust = {
        subject["identifier"] for subject in subjects if subject.get("trust_role") is not None
    }
    assert with_trust == {"10.220.1.1", "10.220.1.0/24"}


# --------------------------------------------------------------------------------------
# 2. Resolution order: environment, then configuration, then none
# --------------------------------------------------------------------------------------


def test_no_profile_anywhere_loads_in_discovery_only_mode(tmp_path: Path) -> None:
    """Absence is a supported state, not an error."""
    context = loader.load_site_context(environ={}, config_path=tmp_path / "absent.json")

    assert context.mode == loader.DISCOVERY_ONLY_MODE
    assert context.has_profile is False
    assert context.path is None


def test_environment_variable_overrides_a_different_configured_path(
    tmp_path: Path, profile_file: Path
) -> None:
    """``UNIFI_SITE_PROFILE`` wins over the remembered configured path."""
    other = _write_profile(
        tmp_path / "other.json",
        {"schema_version": "1.0", "site": {"identifier": "somewhere-else"}},
    )
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"site_profile_path": str(other)}), encoding="utf-8")

    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(profile_file)}, config_path=config
    )

    assert context.source == loader.ENVIRONMENT_SOURCE
    assert context.path == profile_file
    assert context.profile is not None
    assert context.profile.site_identifier == "infiquetra-home-lab"


def test_environment_variable_naming_a_missing_path_fails_loudly(tmp_path: Path) -> None:
    """A named-but-missing profile never degrades to the configured path."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"site_profile_path": str(tmp_path / "real.json")}))

    with pytest.raises(loader.ProfileNotFoundError) as excinfo:
        loader.load_site_context(
            environ={loader.ENVIRONMENT_VARIABLE: str(tmp_path / "gone.json")},
            config_path=config,
        )

    assert loader.ENVIRONMENT_VARIABLE in str(excinfo.value)


def test_empty_environment_variable_is_rejected_rather_than_ignored(tmp_path: Path) -> None:
    """An empty override is a mistake, not a request for discovery-only mode."""
    with pytest.raises(loader.ProfileConfigurationError):
        loader.load_site_context(
            environ={loader.ENVIRONMENT_VARIABLE: "   "}, config_path=tmp_path / "config.json"
        )


def test_configured_path_is_used_when_the_environment_says_nothing(
    tmp_path: Path, profile_file: Path
) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"site_profile_path": str(profile_file)}), encoding="utf-8")

    context = loader.load_site_context(environ={}, config_path=config)

    assert context.source == loader.CONFIGURED_SOURCE
    assert context.mode == loader.PROFILE_MODE


def test_configured_path_that_no_longer_exists_is_reported(tmp_path: Path) -> None:
    """Reverting silently to discovery-only would hide a broken deployment."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"site_profile_path": str(tmp_path / "gone.json")}))

    with pytest.raises(loader.ProfileNotFoundError) as excinfo:
        loader.load_site_context(environ={}, config_path=config)

    assert "no longer exists" in str(excinfo.value)


def test_default_paths_follow_the_xdg_base_directory_specification() -> None:
    environ = {"XDG_CONFIG_HOME": "/xdg"}

    assert loader.config_file_path(environ) == Path("/xdg/infiquetra/unifi/config.json")
    assert loader.default_profile_path(environ) == Path("/xdg/infiquetra/unifi/site-profile.json")
    assert loader.config_file_path({"HOME": "/home/op"}) == Path(
        "/home/op/.config/infiquetra/unifi/config.json"
    )


# --------------------------------------------------------------------------------------
# 3. Validation: the schema version, closed fields, and the credential rule
# --------------------------------------------------------------------------------------


def test_loader_is_pinned_to_the_released_contract() -> None:
    assert loader.SCHEMA_IDENTIFIER == "urn:infiquetra:unifi:site-profile:1.1"
    assert loader.SUPPORTED_SCHEMA_VERSIONS == ("1.0", "1.1")


def test_unrecognized_schema_version_is_rejected_rather_than_partially_applied() -> None:
    document = _valid_profile()
    document["schema_version"] = "2.0"

    with pytest.raises(loader.UnsupportedSchemaVersionError) as excinfo:
        loader.validate_profile(document)

    assert "2.0" in str(excinfo.value)


@pytest.mark.parametrize(
    "field", ["api_key", "password", "authToken", "client_secret", "private_key"]
)
def test_credential_shaped_field_is_rejected_naming_the_offender(field: str) -> None:
    document = _valid_profile()
    document["subjects"][0][field] = "leaked"

    with pytest.raises(loader.ProfileInvalidError) as excinfo:
        loader.validate_profile(document)

    message = str(excinfo.value)
    assert "credential-shaped" in message
    assert field in message


def test_unknown_top_level_field_is_rejected() -> None:
    document = _valid_profile()
    document["discovered_inventory"] = []

    with pytest.raises(loader.ProfileInvalidError) as excinfo:
        loader.validate_profile(document)

    assert "discovered_inventory" in str(excinfo.value)


def test_subject_kind_outside_the_contract_is_rejected() -> None:
    document = _valid_profile()
    document["subjects"][0]["kind"] = "router"

    with pytest.raises(loader.ProfileInvalidError):
        loader.validate_profile(document)


def test_duplicate_subject_is_rejected() -> None:
    document = _valid_profile()
    document["subjects"].append(dict(document["subjects"][0]))

    with pytest.raises(loader.ProfileInvalidError) as excinfo:
        loader.validate_profile(document)

    assert "duplicates subject" in str(excinfo.value)


def test_unparseable_profile_is_reported_as_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(loader.ProfileUnreadableError):
        loader.load_profile_document(path)


# --------------------------------------------------------------------------------------
# 4. The no-inference rule
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["trust_role", "criticality", "ownership", "intended_policies"])
def test_discovery_only_mode_returns_the_explicit_unknown(tmp_path: Path, query: str) -> None:
    context = loader.load_site_context(environ={}, config_path=tmp_path / "absent.json")

    answer = getattr(context, query)("10.220.1.1", kind="device")

    assert answer is loader.UNKNOWN
    assert str(answer) == "unknown"
    assert not answer


def test_subject_the_profile_does_not_name_is_unknown_not_defaulted(profile_file: Path) -> None:
    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(profile_file)}, config_path=None
    )

    assert context.trust_role("203.0.113.9", kind="host") is loader.UNKNOWN
    assert context.criticality("203.0.113.9", kind="host") is loader.UNKNOWN


def test_named_subject_reports_the_operator_intent_it_was_given(profile_file: Path) -> None:
    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(profile_file)}, config_path=None
    )

    assert context.trust_role("10.220.1.1", kind="device") == "trusted"
    # Stated nowhere in the prior agent text, so still unknown rather than filled in.
    assert context.criticality("10.220.1.1", kind="device") is loader.UNKNOWN
    assert context.ownership("10.220.1.1", kind="device") is loader.UNKNOWN


def test_literal_unknown_in_a_document_reads_as_the_explicit_unknown(tmp_path: Path) -> None:
    document = _valid_profile()
    document["subjects"][0]["trust_role"] = "unknown"
    path = _write_profile(tmp_path / "site-profile.json", document)

    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(path)}, config_path=None
    )

    assert context.trust_role("10.220.1.1", kind="device") is loader.UNKNOWN


def test_intended_policies_resolve_for_a_named_subject(profile_file: Path) -> None:
    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(profile_file)}, config_path=None
    )

    policies = context.intended_policies("10.220.30.0/24", kind="network")

    assert [policy["identifier"] for policy in policies] == ["iot-isolated"]


def test_discovery_only_description_states_its_own_limits(tmp_path: Path) -> None:
    context = loader.load_site_context(environ={}, config_path=tmp_path / "absent.json")

    summary = context.describe()

    assert summary["mode"] == loader.DISCOVERY_ONLY_MODE
    assert summary["limits"] == list(loader.DISCOVERY_ONLY_LIMITS)
    assert set(summary["intent_fields"]) == set(loader.INTENT_FIELDS)
    assert set(summary["intent_fields"].values()) == {"unknown"}


def test_profile_mode_description_counts_what_it_holds(profile_file: Path) -> None:
    context = loader.load_site_context(
        environ={loader.ENVIRONMENT_VARIABLE: str(profile_file)}, config_path=None
    )

    summary = context.describe()

    assert summary["mode"] == loader.PROFILE_MODE
    assert summary["site_identifier"] == "infiquetra-home-lab"
    assert summary["subject_count"] == len(RELOCATED_SITE_PROFILE["subjects"])
    assert summary["policy_count"] == len(RELOCATED_SITE_PROFILE["intended_policies"])
    assert "limits" not in summary


# --------------------------------------------------------------------------------------
# 5. The runtime promise: standard library only, and a usable command line
# --------------------------------------------------------------------------------------


def test_loader_imports_nothing_outside_the_standard_library(tmp_path: Path) -> None:
    """A host with no third-party parser can still read a profile.

    Asserted by executing the loader with every third-party path stripped from ``sys.path``,
    so an accidental dependency fails here rather than on a minimal runtime.
    """
    script = (
        "import sys;"
        "sys.path=[p for p in sys.path if 'site-packages' not in p and 'dist-packages' not in p];"
        "import importlib.util;"
        f"spec=importlib.util.spec_from_file_location('spl', {str(LOADER_PATH)!r});"
        "m=importlib.util.module_from_spec(spec);sys.modules['spl']=m;"
        "spec.loader.exec_module(m);"
        "print(m.SCHEMA_IDENTIFIER)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False, cwd=tmp_path
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "urn:infiquetra:unifi:site-profile:1.1"


def test_command_line_reports_discovery_only_mode(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv(loader.ENVIRONMENT_VARIABLE, raising=False)

    exit_code = loader.main(["--config-path", str(tmp_path / "absent.json")])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == loader.DISCOVERY_ONLY_MODE
    assert payload["subjects"] == []


def test_command_line_reports_a_resolved_profile(profile_file: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv(loader.ENVIRONMENT_VARIABLE, str(profile_file))

    exit_code = loader.main([])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == loader.PROFILE_MODE
    assert len(payload["subjects"]) == len(RELOCATED_SITE_PROFILE["subjects"])
    assert len(payload["intended_policies"]) == len(RELOCATED_SITE_PROFILE["intended_policies"])


def test_command_line_reports_a_broken_profile_as_a_structured_error(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv(loader.ENVIRONMENT_VARIABLE, str(tmp_path / "gone.json"))

    exit_code = loader.main([])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] is True
    assert payload["error_type"] == "ProfileNotFoundError"

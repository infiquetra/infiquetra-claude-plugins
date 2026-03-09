"""Tests for marketplace_client.py."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "marketplace-lister" / "skills" / "marketplace-list" / "scripts"))

import marketplace_client as mc


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def icloud_root(tmp_path: Path) -> Path:
    """Create a mock iCloud Drive root."""
    icloud = tmp_path / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    icloud.mkdir(parents=True)
    return icloud


@pytest.fixture
def marketplace_dirs(icloud_root: Path) -> tuple[Path, Path, Path]:
    """Create initialized Marketplace directory structure."""
    base = icloud_root / "Marketplace"
    inbox = base / "inbox"
    unidentified = base / "unidentified"
    inbox.mkdir(parents=True)
    unidentified.mkdir(parents=True)
    return base, inbox, unidentified


@pytest.fixture
def item_folder(marketplace_dirs: tuple[Path, Path, Path]) -> Path:
    """Create an inbox item folder with photos."""
    _, inbox, _ = marketplace_dirs
    folder = inbox / "my-drill"
    folder.mkdir()
    (folder / "photo1.jpg").write_bytes(b"fake-jpeg")
    (folder / "photo2.heic").write_bytes(b"fake-heic")
    (folder / "notes.txt").write_bytes(b"not a photo")
    return folder


@pytest.fixture
def patch_paths(icloud_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch module-level path constants to use tmp_path."""
    base = icloud_root / "Marketplace"
    monkeypatch.setattr(mc, "ICLOUD_BASE", icloud_root)
    monkeypatch.setattr(mc, "MARKETPLACE_BASE", base)
    monkeypatch.setattr(mc, "INBOX", base / "inbox")
    monkeypatch.setattr(mc, "UNIDENTIFIED", base / "unidentified")


# ── _photos_in ────────────────────────────────────────────────────────────────

def test_photos_in_returns_only_images(item_folder: Path) -> None:
    photos = mc._photos_in(item_folder)
    names = {p.name for p in photos}
    assert "photo1.jpg" in names
    assert "photo2.heic" in names
    assert "notes.txt" not in names


def test_photos_in_empty_folder(tmp_path: Path) -> None:
    assert mc._photos_in(tmp_path) == []


# ── _dated_slug ───────────────────────────────────────────────────────────────

def test_dated_slug_format() -> None:
    slug = mc._dated_slug("My Cool Item")
    # Should be YYYY-MM-DD-my-cool-item
    parts = slug.split("-")
    assert len(parts) >= 4
    assert parts[0].isdigit() and len(parts[0]) == 4  # year
    assert parts[1].isdigit() and len(parts[1]) == 2  # month
    assert parts[2].isdigit() and len(parts[2]) == 2  # day
    assert "my" in slug
    assert "cool" in slug
    assert "item" in slug


# ── cmd_init ──────────────────────────────────────────────────────────────────

def test_init_creates_dirs(icloud_root: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_init([])
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert (icloud_root / "Marketplace" / "inbox").exists()
    assert (icloud_root / "Marketplace" / "unidentified").exists()


def test_init_already_exists(marketplace_dirs: tuple, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_init([])
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["created"] == []  # nothing new created


def test_init_no_icloud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    # iCloud root does not exist
    fake_icloud = tmp_path / "nonexistent"
    monkeypatch.setattr(mc, "ICLOUD_BASE", fake_icloud)
    monkeypatch.setattr(mc, "MARKETPLACE_BASE", fake_icloud / "Marketplace")
    monkeypatch.setattr(mc, "INBOX", fake_icloud / "Marketplace" / "inbox")
    monkeypatch.setattr(mc, "UNIDENTIFIED", fake_icloud / "Marketplace" / "unidentified")
    with pytest.raises(SystemExit):
        mc.cmd_init([])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


# ── cmd_scan ──────────────────────────────────────────────────────────────────

def test_scan_lists_folders(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_scan([])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["folders"][0]["folder"] == "my-drill"
    assert out["folders"][0]["photo_count"] == 2


def test_scan_empty_inbox(marketplace_dirs: tuple, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_scan([])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 0
    assert out["folders"] == []


def test_scan_with_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    subdir = tmp_path / "custom"
    subdir.mkdir()
    (subdir / "item1").mkdir()
    (subdir / "item1" / "photo.jpg").write_bytes(b"fake")
    mc.cmd_scan(["--path", str(subdir)])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1


def test_scan_missing_inbox(patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    # inbox doesn't exist (patch_paths sets it but doesn't create dirs)
    with pytest.raises(SystemExit):
        mc.cmd_scan([])


# ── cmd_photos ────────────────────────────────────────────────────────────────

def test_photos_lists_images(item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_photos(["--folder", str(item_folder)])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2
    names = {Path(p).name for p in out["photos"]}
    assert "photo1.jpg" in names
    assert "photo2.heic" in names


def test_photos_no_args(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        mc.cmd_photos([])


def test_photos_inbox_relative(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    # Use just the folder name (relative to inbox)
    mc.cmd_photos(["my-drill"])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


# ── cmd_organize ──────────────────────────────────────────────────────────────

def test_organize_moves_folder(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    base, _, _ = marketplace_dirs
    mc.cmd_organize(["--source", str(item_folder), "--name", "dewalt-drill"])
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert not item_folder.exists()
    new_path = Path(out["to"])
    assert new_path.exists()
    assert "dewalt-drill" in new_path.name


def test_organize_dest_already_exists(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    base, _, _ = marketplace_dirs
    # Manually create destination
    mc.cmd_organize(["--source", str(item_folder), "--name", "dewalt-drill"])
    capsys.readouterr()  # clear first output
    # Now try to organize something else to same name on same day
    folder2 = marketplace_dirs[1] / "another-drill"
    folder2.mkdir()
    with pytest.raises(SystemExit):
        mc.cmd_organize(["--source", str(folder2), "--name", "dewalt-drill"])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_organize_missing_args(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        mc.cmd_organize(["--source", "/some/path"])


# ── cmd_unidentified ──────────────────────────────────────────────────────────

def test_unidentified_moves_folder(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    _, _, unidentified = marketplace_dirs
    mc.cmd_unidentified(["--source", str(item_folder)])
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert not item_folder.exists()
    dest = Path(out["to"])
    assert dest.exists()
    assert dest.parent == unidentified


# ── cmd_listing ───────────────────────────────────────────────────────────────

SAMPLE_LISTING_JSON = {
    "title": "Cooler Master Hyper 212 CPU Cooler - Good",
    "category": "Electronics > Computer Components",
    "condition": "Good",
    "description": "Solid CPU cooler that handles most builds easily.",
    "location": "Indianapolis, IN",
    "pricing": {
        "quick_sale": 20,
        "fair_market": 28,
        "above_market": 32,
        "maximum": 38,
        "reasoning": "eBay sold comps show $25-35 for Good condition",
    },
    "strategy": ["List on Thursday for weekend traffic"],
    "photo_coaching": ["Add a photo from the side showing the fan height"],
    "specs": {"Brand": "Cooler Master", "Model": "Hyper 212"},
}


def test_listing_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(SAMPLE_LISTING_JSON)))
    mc.cmd_listing(["--folder", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    listing_file = tmp_path / "listing.md"
    assert listing_file.exists()
    content = listing_file.read_text()
    assert "Cooler Master Hyper 212" in content
    assert "Quick Sale" in content
    assert "Thursday" in content


def test_listing_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("not valid json"))
    with pytest.raises(SystemExit):
        mc.cmd_listing(["--folder", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_listing_missing_folder(capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        mc.cmd_listing([])


def test_listing_nonexistent_folder(capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(SAMPLE_LISTING_JSON)))
    with pytest.raises(SystemExit):
        mc.cmd_listing(["--folder", "/nonexistent/path/that/does/not/exist"])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


# ── cmd_status ────────────────────────────────────────────────────────────────

def test_status_lists_organized_items(marketplace_dirs: tuple, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    base, _, _ = marketplace_dirs
    # Create organized item folders
    item1 = base / "2026-03-09-yeti-cooler"
    item1.mkdir()
    (item1 / "photo.jpg").write_bytes(b"fake")
    (item1 / "listing.md").write_text("# YETI")

    item2 = base / "2026-03-08-dewalt-drill"
    item2.mkdir()

    mc.cmd_status([])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2
    folders = {i["folder"] for i in out["items"]}
    assert "2026-03-09-yeti-cooler" in folders
    assert "2026-03-08-dewalt-drill" in folders

    # Check has_listing flag
    yeti = next(i for i in out["items"] if "yeti" in i["folder"])
    assert yeti["has_listing"] is True
    drill = next(i for i in out["items"] if "dewalt" in i["folder"])
    assert drill["has_listing"] is False


def test_status_excludes_inbox_and_unidentified(marketplace_dirs: tuple, item_folder: Path, patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    mc.cmd_status([])
    out = json.loads(capsys.readouterr().out)
    folders = [i["folder"] for i in out["items"]]
    assert "inbox" not in folders
    assert "unidentified" not in folders
    assert "my-drill" not in folders  # inbox subfolder, not organized


def test_status_not_initialized(patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    # patch_paths sets paths but marketplace_dirs fixture wasn't used, so dirs don't exist
    with pytest.raises(SystemExit):
        mc.cmd_status([])

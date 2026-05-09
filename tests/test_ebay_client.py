"""Tests for ebay_client.py."""

import json
import sys
import time
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest

# Add script directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent
        / "plugins"
        / "marketplace-lister"
        / "skills"
        / "marketplace-list"
        / "scripts"
    ),
)

import ebay_client as ec

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def marketplace_base(tmp_path: Path) -> Path:
    base = tmp_path / "Marketplace"
    base.mkdir()
    return base


@pytest.fixture
def item_folder(marketplace_base: Path) -> Path:
    folder = marketplace_base / "2026-03-11-cisco-switch"
    folder.mkdir()
    (folder / "photo1.jpg").write_bytes(b"fake-jpeg")
    (folder / "photo2.jpg").write_bytes(b"fake-jpeg-2")
    return folder


@pytest.fixture
def patch_paths(marketplace_base: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec, "MARKETPLACE_BASE", marketplace_base)
    monkeypatch.setattr(ec, "LIMITS_FILE", marketplace_base / "ebay-limits.json")


@pytest.fixture
def token_cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / ".ebay-token.json"
    monkeypatch.setattr(ec, "TOKEN_CACHE_FILE", cache)
    return cache


@pytest.fixture
def ebay_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("EBAY_REFRESH_TOKEN", "test-refresh-token")


# ── EBayAuth ──────────────────────────────────────────────────────────────────


def test_auth_missing_credentials_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("EBAY_REFRESH_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        ec.EBayAuth()
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_auth_uses_cached_token(
    ebay_env: None, token_cache_path: Path, capsys: pytest.CaptureFixture
) -> None:
    # Write a fresh (non-expired) token to cache
    token_data = {
        "access_token": "cached-access-token",
        "expires_at": time.time() + 3600,
        "sandbox": False,
    }
    token_cache_path.write_text(json.dumps(token_data))

    auth = ec.EBayAuth(sandbox=False)
    token = auth.get_access_token()
    assert token == "cached-access-token"


def test_auth_refreshes_expired_token(
    ebay_env: None, token_cache_path: Path, capsys: pytest.CaptureFixture
) -> None:
    # Write an expired token to cache
    token_data = {
        "access_token": "old-token",
        "expires_at": time.time() - 100,  # expired
        "sandbox": False,
    }
    token_cache_path.write_text(json.dumps(token_data))

    auth = ec.EBayAuth(sandbox=False)

    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "new-token", "expires_in": 7200}

    with mock.patch("requests.post", return_value=mock_response):
        token = auth.get_access_token()

    assert token == "new-token"
    # Verify new token was cached
    cached = json.loads(token_cache_path.read_text())
    assert cached["access_token"] == "new-token"


def test_auth_does_not_reuse_sandbox_token_for_production(
    ebay_env: None, token_cache_path: Path
) -> None:
    # Cached token is for sandbox, but we want production
    token_data = {
        "access_token": "sandbox-token",
        "expires_at": time.time() + 3600,
        "sandbox": True,
    }
    token_cache_path.write_text(json.dumps(token_data))

    auth = ec.EBayAuth(sandbox=False)

    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "production-token", "expires_in": 7200}

    with mock.patch("requests.post", return_value=mock_response):
        token = auth.get_access_token()

    assert token == "production-token"


def test_auth_token_refresh_failure_exits(
    ebay_env: None, token_cache_path: Path, capsys: pytest.CaptureFixture
) -> None:
    # No cached token, refresh fails
    mock_response = mock.Mock()
    mock_response.status_code = 401
    mock_response.text = "invalid_client"

    with mock.patch("requests.post", return_value=mock_response):
        auth = ec.EBayAuth(sandbox=False)
        with pytest.raises(SystemExit):
            auth.get_access_token()

    out = json.loads(capsys.readouterr().out)
    assert "error" in out


# ── Limit tracking ────────────────────────────────────────────────────────────


def test_load_limits_defaults(patch_paths: None) -> None:
    limits = ec._load_limits()
    assert limits["monthly_item_limit"] == 20
    assert limits["monthly_amount_limit"] == 1000.0
    assert limits["items_listed"] == 0
    assert limits["amount_listed"] == 0.0


def test_save_and_load_limits(patch_paths: None, marketplace_base: Path) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 5
    limits["amount_listed"] = 245.0
    ec._save_limits(limits)

    loaded = ec._load_limits()
    assert loaded["items_listed"] == 5
    assert loaded["amount_listed"] == 245.0


def test_limits_ok_under_threshold(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 5
    limits["amount_listed"] = 200.0
    result = ec._limits_ok(limits, 50.0)
    assert result["ok"] is True
    assert "warning" not in result


def test_limits_ok_warns_at_80_percent(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 16  # 80% of 20
    limits["amount_listed"] = 0.0
    result = ec._limits_ok(limits, 0.0)
    assert result["ok"] is True
    assert "warning" in result


def test_limits_ok_blocks_at_limit(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 20  # at max
    limits["amount_listed"] = 0.0
    result = ec._limits_ok(limits, 0.0)
    assert result["ok"] is False
    assert "reason" in result


def test_limits_ok_blocks_at_amount_limit(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 0
    limits["amount_listed"] = 990.0
    result = ec._limits_ok(limits, 50.0)  # $990 + $50 = $1040 > $1000
    assert result["ok"] is False


def test_record_listing(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits = ec._record_listing(limits, "listing-123", "/some/folder", 80.0)
    assert limits["items_listed"] == 1
    assert limits["amount_listed"] == 80.0
    assert len(limits["listings"]) == 1
    assert limits["listings"][0]["listing_id"] == "listing-123"


def test_check_period_resets_new_month(patch_paths: None) -> None:
    limits = ec._load_limits()
    limits["current_period"] = "2025-01"  # old month
    limits["items_listed"] = 10
    limits["amount_listed"] = 500.0

    updated = ec._check_period(limits)
    assert updated["items_listed"] == 0
    assert updated["amount_listed"] == 0.0
    assert updated["listings"] == []


# ── ebay.json state ───────────────────────────────────────────────────────────


def test_save_and_load_ebay_state(item_folder: Path) -> None:
    state = {
        "listing_id": "123456",
        "offer_id": "offer-abc",
        "sku": "MKPL-2026-03-11-cisco-switch",
        "status": "active",
    }
    ec._save_ebay_state(item_folder, state)
    loaded = ec._load_ebay_state(item_folder)
    assert loaded["listing_id"] == "123456"
    assert loaded["status"] == "active"


def test_load_ebay_state_missing_returns_empty(item_folder: Path) -> None:
    state = ec._load_ebay_state(item_folder)
    assert state == {}


def test_sku_from_folder(item_folder: Path) -> None:
    sku = ec._sku_from_folder(item_folder)
    assert sku == "MKPL-2026-03-11-cisco-switch"


# ── cmd_publish ───────────────────────────────────────────────────────────────


def test_cmd_publish_missing_folder_exits(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        ec.cmd_publish([])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_publish_returns_review_json(
    ebay_env: None,
    token_cache_path: Path,
    item_folder: Path,
    patch_paths: None,
    capsys: pytest.CaptureFixture,
) -> None:
    # Write a fresh token
    token_cache_path.write_text(
        json.dumps(
            {"access_token": "test-token", "expires_at": time.time() + 3600, "sandbox": False}
        )
    )

    mock_cat_resp = mock.Mock()
    mock_cat_resp.status_code = 200
    mock_cat_resp.json.return_value = {
        "categorySuggestions": [
            {
                "category": {"categoryId": "11176", "categoryName": "Switches & Hubs"},
                "categoryTreeNodeAncestors": [{"categoryName": "Networking"}],
            }
        ]
    }

    mock_aspects_resp = mock.Mock()
    mock_aspects_resp.status_code = 200
    mock_aspects_resp.json.return_value = {
        "aspects": [
            {
                "localizedAspectName": "Brand",
                "aspectConstraint": {"aspectRequired": True},
                "aspectValues": [{"localizedValue": "Cisco"}],
            }
        ]
    }

    with mock.patch("requests.request", side_effect=[mock_cat_resp, mock_aspects_resp]):
        ec.cmd_publish(["--folder", str(item_folder)])

    out = json.loads(capsys.readouterr().out)
    assert "category_suggestions" in out
    assert len(out["category_suggestions"]) >= 1
    assert out["category_suggestions"][0]["category_name"] == "Switches & Hubs"
    assert "limits" in out
    assert out["sku"] == "MKPL-2026-03-11-cisco-switch"


# ── cmd_publish_confirm ───────────────────────────────────────────────────────


CONFIRMED_JSON = {
    "title": "Cisco SG300-28 28-Port Gigabit Managed Switch Good",
    "price": 80.0,
    "category_id": "11176",
    "sku": "MKPL-2026-03-11-cisco-switch",
    "condition_code": 5000,
    "condition_description": "Minor cosmetic wear only, fully functional.",
    "listing_format": "fixed_price",
    "ebay_description": "<div><h2>Cisco SG300-28</h2></div>",
    "item_specifics": {"Brand": "Cisco", "Model": "SG300-28"},
    "fulfillment_policy_id": "fp-123",
    "payment_policy_id": "pay-123",
    "return_policy_id": "ret-123",
}


def test_cmd_publish_confirm_success(
    ebay_env: None,
    token_cache_path: Path,
    item_folder: Path,
    patch_paths: None,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_cache_path.write_text(
        json.dumps(
            {"access_token": "test-token", "expires_at": time.time() + 3600, "sandbox": False}
        )
    )
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(CONFIRMED_JSON)))

    # Mock image upload, inventory create, offer create, offer publish
    upload_resp = mock.Mock()
    upload_resp.status_code = 200
    upload_resp.json.return_value = {"mediaUrl": "https://i.ebayimg.com/photo1.jpg"}

    inv_resp = mock.Mock()
    inv_resp.status_code = 204

    offer_create_resp = mock.Mock()
    offer_create_resp.status_code = 201
    offer_create_resp.json.return_value = {"offerId": "offer-xyz"}

    offer_pub_resp = mock.Mock()
    offer_pub_resp.status_code = 200
    offer_pub_resp.json.return_value = {"listingId": "987654321"}

    call_responses = [upload_resp, upload_resp, inv_resp, offer_create_resp, offer_pub_resp]

    with (
        mock.patch("requests.request", side_effect=call_responses[2:]),
        mock.patch("requests.post", side_effect=call_responses[:2]),
    ):
        ec.cmd_publish_confirm(["--folder", str(item_folder)])

    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["listing_id"] == "987654321"
    assert "ebay.com/itm/987654321" in out["url"]

    # Verify ebay.json was saved
    state = ec._load_ebay_state(item_folder)
    assert state["listing_id"] == "987654321"
    assert state["status"] == "active"

    # Verify limits were updated
    limits = ec._load_limits()
    assert limits["items_listed"] == 1
    assert limits["amount_listed"] == 80.0


def test_cmd_publish_confirm_blocks_at_limit(
    ebay_env: None,
    token_cache_path: Path,
    item_folder: Path,
    patch_paths: None,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    marketplace_base: Path,
) -> None:
    token_cache_path.write_text(
        json.dumps(
            {"access_token": "test-token", "expires_at": time.time() + 3600, "sandbox": False}
        )
    )
    # Pre-fill limits to max
    limits = ec._load_limits()
    limits["items_listed"] = 20
    ec._save_limits(limits)

    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(CONFIRMED_JSON)))

    with pytest.raises(SystemExit):
        ec.cmd_publish_confirm(["--folder", str(item_folder)])

    out = json.loads(capsys.readouterr().out)
    assert "error" in out
    assert "limit" in out["error"].lower()


# ── cmd_limits ────────────────────────────────────────────────────────────────


def test_cmd_limits_shows_usage(
    patch_paths: None, capsys: pytest.CaptureFixture, marketplace_base: Path
) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 5
    limits["amount_listed"] = 245.0
    ec._save_limits(limits)

    ec.cmd_limits([])
    out = json.loads(capsys.readouterr().out)
    assert out["items"]["used"] == 5
    assert out["items"]["limit"] == 20
    assert out["items"]["remaining"] == 15
    assert out["amount"]["used"] == 245.0


def test_cmd_limits_warns_at_80_percent(patch_paths: None, capsys: pytest.CaptureFixture) -> None:
    limits = ec._load_limits()
    limits["items_listed"] = 17  # 85% of 20
    ec._save_limits(limits)

    ec.cmd_limits([])
    out = json.loads(capsys.readouterr().out)
    assert "warning" in out


# ── cmd_status ────────────────────────────────────────────────────────────────


def test_cmd_status_single_folder_no_state(
    item_folder: Path, capsys: pytest.CaptureFixture
) -> None:
    with pytest.raises(SystemExit):
        ec.cmd_status(["--folder", str(item_folder)])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_status_all_shows_items_with_state(
    patch_paths: None,
    marketplace_base: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    # Create two item folders, one with ebay.json
    folder1 = marketplace_base / "2026-03-09-cisco-switch"
    folder1.mkdir()
    ec._save_ebay_state(folder1, {"listing_id": "111", "status": "active", "price": 80.0})

    folder2 = marketplace_base / "2026-03-10-yeti-cooler"
    folder2.mkdir()  # no ebay.json

    ec.cmd_status([])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1  # only the one with ebay.json
    assert out["items"][0]["listing_id"] == "111"


# ── cmd_categories ────────────────────────────────────────────────────────────


def test_cmd_categories_missing_query_exits(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        ec.cmd_categories([])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_categories_returns_suggestions(
    ebay_env: None, token_cache_path: Path, capsys: pytest.CaptureFixture
) -> None:
    token_cache_path.write_text(
        json.dumps(
            {"access_token": "test-token", "expires_at": time.time() + 3600, "sandbox": False}
        )
    )

    mock_resp = mock.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "categorySuggestions": [
            {
                "category": {"categoryId": "11176", "categoryName": "Switches & Hubs"},
                "categoryTreeNodeAncestors": [{"categoryName": "Networking"}],
            },
            {
                "category": {"categoryId": "11189", "categoryName": "Enterprise Networking"},
                "categoryTreeNodeAncestors": [{"categoryName": "Networking"}],
            },
        ]
    }

    with mock.patch("requests.request", return_value=mock_resp):
        ec.cmd_categories(["--query", "managed switch"])

    out = json.loads(capsys.readouterr().out)
    assert out["query"] == "managed switch"
    assert out["count"] >= 1
    assert out["categories"][0]["category_name"] == "Switches & Hubs"


# ── _maybe_convert_heic ───────────────────────────────────────────────────────


def test_maybe_convert_heic_returns_raw_for_jpg(tmp_path: Path) -> None:
    jpg = tmp_path / "photo.jpg"
    jpg.write_bytes(b"fake-jpeg-data")
    result = ec._maybe_convert_heic(jpg)
    assert result == b"fake-jpeg-data"


def test_maybe_convert_heic_returns_raw_when_pillow_missing(tmp_path: Path) -> None:
    """When Pillow is not installed, HEIC files should return raw bytes gracefully."""
    heic = tmp_path / "photo.heic"
    heic.write_bytes(b"fake-heic-data")

    with mock.patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
        result = ec._maybe_convert_heic(heic)
    # Should return raw bytes without crashing
    assert result == b"fake-heic-data"


# ── cmd_ship ─────────────────────────────────────────────────────────────────


def test_cmd_ship_missing_args_exits(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        ec.cmd_ship(["--folder", "/some/path"])
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_ship_no_ebay_json_exits(
    item_folder: Path, ebay_env: None, token_cache_path: Path, capsys: pytest.CaptureFixture
) -> None:
    token_cache_path.write_text(
        json.dumps(
            {"access_token": "test-token", "expires_at": time.time() + 3600, "sandbox": False}
        )
    )

    # No ebay.json — but we need to handle that the auth setup happens then order lookup fails
    ec._save_ebay_state(item_folder, {"listing_id": "999", "offer_id": "offer-999"})

    mock_orders_resp = mock.Mock()
    mock_orders_resp.status_code = 200
    mock_orders_resp.json.return_value = {"orders": []}  # No matching order

    with mock.patch("requests.request", return_value=mock_orders_resp), pytest.raises(SystemExit):
        ec.cmd_ship(
            [
                "--folder",
                str(item_folder),
                "--tracking",
                "1Z123456",
                "--carrier",
                "UPS",
            ]
        )
    out = json.loads(capsys.readouterr().out)
    assert "error" in out

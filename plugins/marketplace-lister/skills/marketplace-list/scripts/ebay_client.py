#!/usr/bin/env python3
"""
eBay API Client for Claude Code marketplace plugin.

Handles OAuth token management, inventory creation, offer publishing,
fulfillment, and monthly limit tracking.

Commands:
  publish --folder <path>               Prepare listing data and query eBay for category/aspects
  publish-confirm --folder <path>       Execute publish (stdin: confirmed JSON). Uploads photos,
                                        creates inventory item, creates offer, publishes.
  status [--folder <path>]              Check listing status for one item or all
  relist --folder <path>                Re-publish an ended listing
  ship --folder <path> --tracking NUM --carrier NAME  Add shipping fulfillment
  messages [--limit N]                  View recent buyer messages
  limits                                Show current monthly limit usage
  categories --query TEXT               Search eBay categories

Environment variables:
  EBAY_CLIENT_ID        App ID from developer.ebay.com
  EBAY_CLIENT_SECRET    Cert ID (not the Dev ID)
  EBAY_REFRESH_TOKEN    Long-lived user token
  EBAY_SANDBOX=true     Optional — use sandbox API for testing
"""

import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import requests

# ── Constants ─────────────────────────────────────────────────────────────────

ICLOUD_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
MARKETPLACE_BASE = ICLOUD_BASE / "Marketplace"
LIMITS_FILE = MARKETPLACE_BASE / "ebay-limits.json"
TOKEN_CACHE_FILE = Path.home() / ".ebay-token.json"

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}

PRODUCTION_API_BASE = "https://api.ebay.com"
SANDBOX_API_BASE = "https://api.sandbox.ebay.com"
PRODUCTION_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

OAUTH_SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/commerce.taxonomy.readonly",
]

MONTHLY_ITEM_LIMIT = 20
MONTHLY_AMOUNT_LIMIT = 1000.00


# ── Helpers ───────────────────────────────────────────────────────────────────


def _success(data: dict) -> None:
    print(json.dumps(data, indent=2))


def _error(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def _is_sandbox() -> bool:
    return os.environ.get("EBAY_SANDBOX", "").lower() in ("true", "1", "yes")


def _photos_in(folder: Path) -> list[Path]:
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in PHOTO_EXTS)


# ── Auth ──────────────────────────────────────────────────────────────────────


class EBayAuth:
    """OAuth 2.0 token management. Caches tokens to avoid repeated refresh calls."""

    def __init__(self, sandbox: bool = False) -> None:
        self.sandbox = sandbox
        self.token_url = SANDBOX_TOKEN_URL if sandbox else PRODUCTION_TOKEN_URL
        self.client_id = os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
        self.refresh_token_value = os.environ.get("EBAY_REFRESH_TOKEN", "")

        missing = [
            name
            for name, val in [
                ("EBAY_CLIENT_ID", self.client_id),
                ("EBAY_CLIENT_SECRET", self.client_secret),
                ("EBAY_REFRESH_TOKEN", self.refresh_token_value),
            ]
            if not val
        ]
        if missing:
            _error(
                f"Missing eBay credentials: {', '.join(missing)}. See references/ebay-fields.md."
            )

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing from eBay if expired."""
        cached = self._load_cached_token()
        if cached and not self._is_expired(cached):
            return str(cached["access_token"])
        return self._refresh_access_token()

    def invalidate_cache(self) -> None:
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()

    def _load_cached_token(self) -> dict | None:
        if TOKEN_CACHE_FILE.exists():
            try:
                data = json.loads(TOKEN_CACHE_FILE.read_text())
                # Don't reuse a production token for sandbox or vice versa
                if data.get("sandbox") == self.sandbox:
                    return cast(dict[str, Any], data)
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _is_expired(self, token_data: dict) -> bool:
        # Refresh 60 seconds before actual expiry
        return float(time.time()) >= float(token_data.get("expires_at", 0)) - 60

    def _refresh_access_token(self) -> str:
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        response = requests.post(
            self.token_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token_value,
                "scope": " ".join(OAUTH_SCOPES),
            },
            timeout=30,
        )

        if response.status_code != 200:
            _error(f"eBay token refresh failed ({response.status_code}): {response.text}")

        data = response.json()
        token_data = {
            "access_token": data["access_token"],
            "expires_at": time.time() + data.get("expires_in", 7200),
            "sandbox": self.sandbox,
        }
        TOKEN_CACHE_FILE.write_text(json.dumps(token_data))
        TOKEN_CACHE_FILE.chmod(0o600)  # Token is sensitive — owner-only read/write
        return str(token_data["access_token"])


# ── API wrapper ───────────────────────────────────────────────────────────────


class EBayAPI:
    """eBay REST API wrapper with auto-retry on 401."""

    def __init__(self, auth: EBayAuth) -> None:
        self.auth = auth
        self.base_url = SANDBOX_API_BASE if auth.sandbox else PRODUCTION_API_BASE

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: object) -> requests.Response:
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, headers=self._headers(), **kwargs)  # type: ignore[arg-type]
        if response.status_code == 401:
            # Token rejected — force refresh and retry once
            self.auth.invalidate_cache()
            response = requests.request(method, url, headers=self._headers(), **kwargs)  # type: ignore[arg-type]
        return response

    # ── Taxonomy ──────────────────────────────────────────────────────────────

    def get_category_suggestions(self, query: str) -> dict:
        resp = self._request(
            "GET",
            "/commerce/taxonomy/v1/category_tree/0/get_category_suggestions",
            params={"q": query},
            timeout=15,
        )
        return dict(resp.json())

    def get_item_aspects(self, category_id: str) -> dict:
        resp = self._request(
            "GET",
            "/commerce/taxonomy/v1/category_tree/0/get_item_aspects_for_category",
            params={"category_id": category_id},
            timeout=15,
        )
        return dict(resp.json())

    # ── Inventory ─────────────────────────────────────────────────────────────

    def create_or_replace_inventory_item(self, sku: str, data: dict) -> requests.Response:
        return self._request(
            "PUT",
            f"/sell/inventory/v1/inventory_item/{sku}",
            json=data,
            timeout=30,
        )

    def create_offer(self, data: dict) -> requests.Response:
        return self._request(
            "POST",
            "/sell/inventory/v1/offer",
            json=data,
            timeout=30,
        )

    def publish_offer(self, offer_id: str) -> requests.Response:
        return self._request(
            "POST",
            f"/sell/inventory/v1/offer/{offer_id}/publish",
            timeout=30,
        )

    def revise_offer(self, offer_id: str, data: dict) -> requests.Response:
        return self._request(
            "PATCH",
            f"/sell/inventory/v1/offer/{offer_id}",
            json=data,
            timeout=30,
        )

    def get_offer(self, sku: str) -> requests.Response:
        return self._request(
            "GET",
            "/sell/inventory/v1/offer",
            params={"sku": sku},
            timeout=15,
        )

    # ── Account policies ──────────────────────────────────────────────────────

    def get_fulfillment_policies(self) -> requests.Response:
        return self._request(
            "GET",
            "/sell/account/v1/fulfillment_policy",
            params={"marketplace_id": "EBAY_US"},
            timeout=15,
        )

    def get_payment_policies(self) -> requests.Response:
        return self._request(
            "GET",
            "/sell/account/v1/payment_policy",
            params={"marketplace_id": "EBAY_US"},
            timeout=15,
        )

    def get_return_policies(self) -> requests.Response:
        return self._request(
            "GET",
            "/sell/account/v1/return_policy",
            params={"marketplace_id": "EBAY_US"},
            timeout=15,
        )

    # ── Fulfillment (orders + shipping) ───────────────────────────────────────

    def get_orders(self, limit: int = 20) -> requests.Response:
        return self._request(
            "GET",
            "/sell/fulfillment/v1/order",
            params={"limit": limit},
            timeout=15,
        )

    def create_shipping_fulfillment(
        self, order_id: str, tracking_number: str, carrier: str
    ) -> requests.Response:
        data = {
            "lineItems": [],  # empty = all items in order
            "shippingCarrierCode": carrier,
            "trackingNumber": tracking_number,
        }
        return self._request(
            "POST",
            f"/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            json=data,
            timeout=30,
        )

    # ── Messaging ─────────────────────────────────────────────────────────────

    def get_messages(self, limit: int = 20) -> requests.Response:
        return self._request(
            "GET",
            "/sell/message/v1/conversation",
            params={"limit": limit},
            timeout=15,
        )

    # ── Image upload ──────────────────────────────────────────────────────────

    def upload_image(self, image_path: Path) -> str:
        """Upload an image file to eBay and return the hosted image URL."""
        path = Path(image_path)
        image_data = _maybe_convert_heic(path)
        content_type = "image/jpeg" if image_data != path.read_bytes() else _mime_type(path)

        resp = requests.post(
            f"{self.base_url}/sell/media/v1_beta/media_item",
            headers={
                "Authorization": f"Bearer {self.auth.get_access_token()}",
                "Content-Type": content_type,
            },
            data=image_data,
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            _error(f"Image upload failed for {path.name}: {resp.status_code} {resp.text}")

        resp_data = resp.json()
        return str(resp_data.get("mediaUrl", resp_data.get("imageUrl", "")))


def _mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext.lstrip("."), "image/jpeg")


def _maybe_convert_heic(path: Path) -> bytes:
    """Convert HEIC to JPEG if Pillow is available; otherwise return raw bytes."""
    if path.suffix.lower() not in (".heic", ".heif"):
        return path.read_bytes()
    try:
        from PIL import Image  # type: ignore[import-untyped]

        img = Image.open(path)
        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except ImportError:
        # Pillow not installed — return raw bytes and hope eBay accepts HEIC
        return path.read_bytes()
    except Exception:
        return path.read_bytes()


# ── Limits ────────────────────────────────────────────────────────────────────


def _load_limits() -> dict:
    if LIMITS_FILE.exists():
        try:
            return dict(json.loads(LIMITS_FILE.read_text()))
        except json.JSONDecodeError:
            pass
    return {
        "monthly_item_limit": MONTHLY_ITEM_LIMIT,
        "monthly_amount_limit": MONTHLY_AMOUNT_LIMIT,
        "current_period": datetime.now().strftime("%Y-%m"),
        "items_listed": 0,
        "amount_listed": 0.0,
        "listings": [],
    }


def _save_limits(limits: dict) -> None:
    MARKETPLACE_BASE.mkdir(parents=True, exist_ok=True)
    LIMITS_FILE.write_text(json.dumps(limits, indent=2))


def _check_period(limits: dict) -> dict:
    """Reset counters if we've entered a new month."""
    current_period = datetime.now().strftime("%Y-%m")
    if limits.get("current_period") != current_period:
        limits["current_period"] = current_period
        limits["items_listed"] = 0
        limits["amount_listed"] = 0.0
        limits["listings"] = []
    return limits


def _limits_ok(limits: dict, price: float) -> dict:
    """Return dict with 'ok' bool and optional 'warning' message."""
    items_after = limits["items_listed"] + 1
    amount_after = limits["amount_listed"] + price

    if items_after > limits["monthly_item_limit"]:
        return {
            "ok": False,
            "reason": f"Item limit reached: {limits['items_listed']}/{limits['monthly_item_limit']} this month",
        }
    if amount_after > limits["monthly_amount_limit"]:
        return {
            "ok": False,
            "reason": f"Amount limit reached: ${limits['amount_listed']:.2f}/${limits['monthly_amount_limit']:.2f} this month",
        }

    result: dict = {"ok": True}
    item_pct = items_after / limits["monthly_item_limit"]
    amount_pct = amount_after / limits["monthly_amount_limit"]
    if item_pct >= 0.8 or amount_pct >= 0.8:
        result["warning"] = (
            f"Approaching limits: {items_after}/{limits['monthly_item_limit']} items, "
            f"${amount_after:.2f}/${limits['monthly_amount_limit']:.2f}"
        )
    return result


def _record_listing(limits: dict, listing_id: str, folder_path: str, price: float) -> dict:
    limits["items_listed"] += 1
    limits["amount_listed"] += price
    limits["listings"].append(
        {
            "listing_id": listing_id,
            "folder": folder_path,
            "price": price,
            "listed_at": datetime.now().isoformat(),
        }
    )
    return limits


# ── ebay.json state ───────────────────────────────────────────────────────────


def _load_ebay_state(folder: Path) -> dict:
    state_file = folder / "ebay.json"
    if state_file.exists():
        return dict(json.loads(state_file.read_text()))
    return {}


def _save_ebay_state(folder: Path, state: dict) -> None:
    (folder / "ebay.json").write_text(json.dumps(state, indent=2))


def _sku_from_folder(folder: Path) -> str:
    return f"MKPL-{folder.name}"


# ── Commands ──────────────────────────────────────────────────────────────────


def cmd_publish(args: list[str]) -> None:
    """Prepare listing data and query eBay taxonomy for category suggestions."""
    if "--folder" not in args:
        _error("Usage: ebay_client.py publish --folder <path>")
        return

    folder = Path(args[args.index("--folder") + 1])
    if not folder.exists():
        _error(f"Folder not found: {folder}")
        return

    # Load listing data if available
    listing_data: dict = {}
    listing_json_path = folder / "listing.json"
    if listing_json_path.exists():
        listing_data = json.loads(listing_json_path.read_text())

    # Extract search query from listing data or folder name
    title = listing_data.get("ebay_title") or listing_data.get("title") or folder.name
    price = float(listing_data.get("pricing", {}).get("ebay_price", 0))

    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    # Query category suggestions
    cat_resp = api.get_category_suggestions(title)
    suggestions = cat_resp.get("categorySuggestions", [])[:5]
    categories = [
        {
            "rank": i + 1,
            "category_id": s.get("category", {}).get("categoryId", ""),
            "category_name": s.get("category", {}).get("categoryName", ""),
            "category_tree_node_ancestors": [
                a.get("categoryName", "") for a in s.get("categoryTreeNodeAncestors", [])
            ],
        }
        for i, s in enumerate(suggestions)
    ]

    # Get aspects for top suggested category
    top_aspects: list = []
    if categories:
        aspects_resp = api.get_item_aspects(categories[0]["category_id"])
        aspect_list = aspects_resp.get("aspects", [])
        top_aspects = [
            {
                "name": a.get("localizedAspectName", ""),
                "required": a.get("aspectConstraint", {}).get("aspectRequired", False),
                "values": a.get("aspectValues", [{"localizedValue": ""}])[:3],
            }
            for a in aspect_list[:15]
        ]

    # Load limits
    limits = _check_period(_load_limits())

    _success(
        {
            "folder": str(folder),
            "sku": _sku_from_folder(folder),
            "title": title,
            "price": price,
            "category_suggestions": categories,
            "top_category_aspects": top_aspects,
            "existing_listing_data": listing_data,
            "photos": [p.name for p in _photos_in(folder)],
            "limits": {
                "items_listed": limits["items_listed"],
                "monthly_item_limit": limits["monthly_item_limit"],
                "amount_listed": limits["amount_listed"],
                "monthly_amount_limit": limits["monthly_amount_limit"],
                "current_period": limits["current_period"],
            },
            "sandbox": _is_sandbox(),
        }
    )


def cmd_publish_confirm(args: list[str]) -> None:
    """Execute eBay publish: upload photos, create inventory item, create offer, publish."""
    if "--folder" not in args:
        _error("Usage: echo '<confirmed-json>' | ebay_client.py publish-confirm --folder <path>")
        return

    folder = Path(args[args.index("--folder") + 1])
    if not folder.exists():
        _error(f"Folder not found: {folder}")
        return

    try:
        confirmed = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        _error(f"Invalid JSON from stdin: {e}")
        return

    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    price = float(confirmed.get("price", 0))
    category_id = str(confirmed.get("category_id", ""))
    sku = confirmed.get("sku") or _sku_from_folder(folder)
    title = str(confirmed.get("title", folder.name))
    ebay_description = str(confirmed.get("ebay_description", ""))
    condition_code = str(confirmed.get("condition_code", 5000))
    condition_description = str(confirmed.get("condition_description", ""))
    listing_format = str(confirmed.get("listing_format", "fixed_price"))
    fulfillment_policy_id = str(confirmed.get("fulfillment_policy_id", ""))
    payment_policy_id = str(confirmed.get("payment_policy_id", ""))
    return_policy_id = str(confirmed.get("return_policy_id", ""))
    item_specifics = confirmed.get("item_specifics", {})

    # Check limits before proceeding
    limits = _check_period(_load_limits())
    limit_check = _limits_ok(limits, price)
    if not limit_check["ok"]:
        _error(f"Cannot publish: {limit_check['reason']}")
        return

    # Upload photos
    photos = _photos_in(folder)
    image_urls: list[str] = []
    for photo in photos:
        url = api.upload_image(photo)
        if url:
            image_urls.append(url)

    # Map condition code to eBay condition enum
    condition_map = {
        "1000": "NEW",
        "1500": "LIKE_NEW",
        "2000": "NEW_OTHER",
        "2500": "SELLER_REFURBISHED",
        "3000": "USED_EXCELLENT",
        "4000": "USED_VERY_GOOD",
        "5000": "USED_GOOD",
        "6000": "USED_ACCEPTABLE",
        "7000": "FOR_PARTS_OR_NOT_WORKING",
    }
    condition_enum = condition_map.get(str(condition_code), "USED_GOOD")

    # Build aspects from item_specifics
    aspects = {k: [v] for k, v in item_specifics.items()} if item_specifics else {}

    # Create inventory item
    inventory_data: dict = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": condition_enum,
        "product": {
            "title": title,
            "description": ebay_description,
            "imageUrls": image_urls,
            "aspects": aspects,
        },
    }
    if condition_description:
        inventory_data["conditionDescription"] = condition_description

    inv_resp = api.create_or_replace_inventory_item(sku, inventory_data)
    if inv_resp.status_code not in (200, 204):
        _error(f"Inventory item creation failed ({inv_resp.status_code}): {inv_resp.text}")
        return

    # Build offer
    ebay_format = "FIXED_PRICE" if listing_format == "fixed_price" else "AUCTION"
    offer_data: dict = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": ebay_format,
        "availableQuantity": 1,
        "categoryId": category_id,
        "listingDescription": ebay_description,
        "pricingSummary": {"price": {"currency": "USD", "value": f"{price:.2f}"}},
    }
    if fulfillment_policy_id:
        offer_data.setdefault("listingPolicies", {})["fulfillmentPolicyId"] = fulfillment_policy_id
    if payment_policy_id:
        offer_data.setdefault("listingPolicies", {})["paymentPolicyId"] = payment_policy_id
    if return_policy_id:
        offer_data.setdefault("listingPolicies", {})["returnPolicyId"] = return_policy_id

    offer_resp = api.create_offer(offer_data)
    if offer_resp.status_code not in (200, 201):
        _error(f"Offer creation failed ({offer_resp.status_code}): {offer_resp.text}")
        return

    offer_id = str(offer_resp.json().get("offerId", ""))

    # Publish offer
    pub_resp = api.publish_offer(offer_id)
    if pub_resp.status_code not in (200, 201):
        _error(f"Offer publish failed ({pub_resp.status_code}): {pub_resp.text}")
        return

    listing_id = str(pub_resp.json().get("listingId", ""))
    listing_url = f"https://www.ebay.com/itm/{listing_id}"
    if _is_sandbox():
        listing_url = f"https://www.sandbox.ebay.com/itm/{listing_id}"

    # Save per-item state
    state = {
        "listing_id": listing_id,
        "offer_id": offer_id,
        "sku": sku,
        "status": "active",
        "listing_format": listing_format,
        "published_at": datetime.now().isoformat(),
        "price": price,
        "category_id": category_id,
        "url": listing_url,
        "views": 0,
        "watchers": 0,
    }
    _save_ebay_state(folder, state)

    # Update limits
    limits = _record_listing(limits, listing_id, str(folder), price)
    _save_limits(limits)

    result: dict = {
        "success": True,
        "listing_id": listing_id,
        "offer_id": offer_id,
        "url": listing_url,
        "sku": sku,
        "price": price,
        "photos_uploaded": len(image_urls),
        "sandbox": _is_sandbox(),
        "limits": {
            "items_listed": limits["items_listed"],
            "monthly_item_limit": limits["monthly_item_limit"],
            "amount_listed": limits["amount_listed"],
            "monthly_amount_limit": limits["monthly_amount_limit"],
        },
    }
    if limit_check.get("warning"):
        result["warning"] = limit_check["warning"]
    _success(result)


def cmd_status(args: list[str]) -> None:
    """Check listing status. With --folder, checks one item; without, checks all."""
    if "--folder" in args:
        folder = Path(args[args.index("--folder") + 1])
        state = _load_ebay_state(folder)
        if not state:
            _error(f"No ebay.json found in {folder}. Publish first.")
            return

        auth = EBayAuth(sandbox=_is_sandbox())
        api = EBayAPI(auth)
        offer_resp = api.get_offer(state.get("sku", ""))
        if offer_resp.status_code == 200:
            offers = offer_resp.json().get("offers", [])
            if offers:
                offer = offers[0]
                state["status"] = offer.get("status", state.get("status", "unknown")).lower()

        _success({"folder": str(folder), **state})
    else:
        # Status for all organized items
        if not MARKETPLACE_BASE.exists():
            _error("Marketplace not initialized.")
            return
        items = []
        for item in sorted(MARKETPLACE_BASE.iterdir()):
            if item.is_dir() and item.name not in ("inbox", "unidentified"):
                state = _load_ebay_state(item)
                if state:
                    items.append({"folder": item.name, "path": str(item), **state})
        _success({"items": items, "count": len(items)})


def cmd_relist(args: list[str]) -> None:
    """Re-publish a previously ended listing."""
    if "--folder" not in args:
        _error("Usage: ebay_client.py relist --folder <path>")
        return

    folder = Path(args[args.index("--folder") + 1])
    state = _load_ebay_state(folder)
    if not state.get("sku"):
        _error(f"No ebay.json found in {folder}. Nothing to relist.")
        return

    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    # Re-publish existing offer (eBay creates new listing_id on relist)
    offer_id = state.get("offer_id", "")
    if not offer_id:
        _error("No offer_id in ebay.json. Cannot relist.")
        return

    pub_resp = api.publish_offer(offer_id)
    if pub_resp.status_code not in (200, 201):
        _error(f"Relist failed ({pub_resp.status_code}): {pub_resp.text}")
        return

    new_listing_id = str(pub_resp.json().get("listingId", ""))
    state["listing_id"] = new_listing_id
    state["status"] = "active"
    state["url"] = f"https://www.ebay.com/itm/{new_listing_id}"
    _save_ebay_state(folder, state)

    _success({"success": True, "listing_id": new_listing_id, "url": state["url"]})


def cmd_revise(args: list[str]) -> None:
    """Revise an active listing. Reads revision JSON from stdin."""
    if "--folder" not in args:
        _error("Usage: echo '<revision-json>' | ebay_client.py revise --folder <path>")
        return

    folder = Path(args[args.index("--folder") + 1])
    state = _load_ebay_state(folder)
    if not state.get("offer_id"):
        _error(f"No ebay.json found in {folder}.")
        return

    try:
        revision = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        _error(f"Invalid JSON from stdin: {e}")
        return

    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    resp = api.revise_offer(state["offer_id"], revision)
    if resp.status_code not in (200, 204):
        _error(f"Revise failed ({resp.status_code}): {resp.text}")
        return

    _success({"success": True, "offer_id": state["offer_id"], "revised": list(revision.keys())})


def cmd_ship(args: list[str]) -> None:
    """Add shipping fulfillment after a sale."""
    if "--folder" not in args or "--tracking" not in args or "--carrier" not in args:
        _error("Usage: ebay_client.py ship --folder <path> --tracking <number> --carrier <name>")
        return

    folder = Path(args[args.index("--folder") + 1])
    tracking = args[args.index("--tracking") + 1]
    carrier = args[args.index("--carrier") + 1]
    state = _load_ebay_state(folder)

    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    # Find the order associated with this listing
    orders_resp = api.get_orders()
    if orders_resp.status_code != 200:
        _error(f"Could not fetch orders ({orders_resp.status_code}): {orders_resp.text}")
        return

    orders = orders_resp.json().get("orders", [])
    listing_id = state.get("listing_id", "")
    order_id = None
    for order in orders:
        for line_item in order.get("lineItems", []):
            if line_item.get("listingId") == listing_id:
                order_id = order["orderId"]
                break
        if order_id:
            break

    if not order_id:
        _error(f"No order found for listing {listing_id}. Check eBay Seller Hub for the order ID.")
        return

    ship_resp = api.create_shipping_fulfillment(order_id, tracking, carrier)
    if ship_resp.status_code not in (200, 201):
        _error(f"Shipping fulfillment failed ({ship_resp.status_code}): {ship_resp.text}")
        return

    state["status"] = "shipped"
    state["tracking_number"] = tracking
    state["carrier"] = carrier
    _save_ebay_state(folder, state)

    _success(
        {
            "success": True,
            "order_id": order_id,
            "tracking_number": tracking,
            "carrier": carrier,
        }
    )


def cmd_messages(args: list[str]) -> None:
    """View recent buyer messages."""
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 20
    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    resp = api.get_messages(limit)
    if resp.status_code != 200:
        _error(f"Could not fetch messages ({resp.status_code}): {resp.text}")
        return

    data = resp.json()
    conversations = data.get("conversations", [])
    result = []
    for conv in conversations:
        result.append(
            {
                "conversation_id": conv.get("conversationId"),
                "item_id": conv.get("itemId"),
                "buyer": conv.get("buyer", {}).get("username", ""),
                "status": conv.get("conversationStatus"),
                "unread": conv.get("unread", False),
                "last_message": conv.get("lastMessageDate"),
            }
        )
    _success({"messages": result, "count": len(result)})


def cmd_limits(_args: list[str]) -> None:
    """Show current monthly limit usage."""
    limits = _check_period(_load_limits())
    items_remaining = limits["monthly_item_limit"] - limits["items_listed"]
    amount_remaining = limits["monthly_amount_limit"] - limits["amount_listed"]
    item_pct = limits["items_listed"] / limits["monthly_item_limit"] * 100
    amount_pct = limits["amount_listed"] / limits["monthly_amount_limit"] * 100

    result: dict = {
        "current_period": limits["current_period"],
        "items": {
            "used": limits["items_listed"],
            "limit": limits["monthly_item_limit"],
            "remaining": items_remaining,
            "percent_used": round(item_pct, 1),
        },
        "amount": {
            "used": round(limits["amount_listed"], 2),
            "limit": limits["monthly_amount_limit"],
            "remaining": round(amount_remaining, 2),
            "percent_used": round(amount_pct, 1),
        },
        "listings": limits.get("listings", []),
    }
    if item_pct >= 80 or amount_pct >= 80:
        result["warning"] = (
            "Approaching monthly limits. Consider requesting a limit increase from eBay."
        )
    _success(result)


def cmd_categories(args: list[str]) -> None:
    """Search eBay categories by keyword."""
    if "--query" not in args:
        _error("Usage: ebay_client.py categories --query 'networking switch'")
        return

    query = args[args.index("--query") + 1]
    auth = EBayAuth(sandbox=_is_sandbox())
    api = EBayAPI(auth)

    resp = api.get_category_suggestions(query)
    suggestions = resp.get("categorySuggestions", [])[:10]
    categories = [
        {
            "rank": i + 1,
            "category_id": s.get("category", {}).get("categoryId", ""),
            "category_name": s.get("category", {}).get("categoryName", ""),
            "path": " > ".join(
                a.get("categoryName", "") for a in s.get("categoryTreeNodeAncestors", [])
            ),
        }
        for i, s in enumerate(suggestions)
    ]
    _success({"query": query, "categories": categories, "count": len(categories)})


# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "publish": cmd_publish,
    "publish-confirm": cmd_publish_confirm,
    "status": cmd_status,
    "relist": cmd_relist,
    "revise": cmd_revise,
    "ship": cmd_ship,
    "messages": cmd_messages,
    "limits": cmd_limits,
    "categories": cmd_categories,
}


def main() -> None:
    if len(sys.argv) < 2:
        _error(f"Usage: ebay_client.py <command> [args...]\nCommands: {', '.join(COMMANDS)}")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMANDS:
        _error(f"Unknown command: {command}. Available: {', '.join(COMMANDS)}")
        return

    try:
        COMMANDS[command](args)
    except SystemExit:
        raise
    except Exception as e:
        _error(str(e))


if __name__ == "__main__":
    main()

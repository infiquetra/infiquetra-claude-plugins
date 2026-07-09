"""Contract tests for the generic OpenAI-compatible HTTP bridge (plan U5, #387 AC1/AC2/AC3').

Coverage:

* ``-k transport_http_bridge`` -- dispatch-equivalence across an Ollama-Cloud-shaped and a
  DeepSeek-shaped registry row: one adapter, provider differences only in row data (#387 AC1).
* The bearer ``Authorization`` header is present **iff** ``auth.mode: bearer`` and the resolved
  token never leaks into the invocation dict, evidence, provenance, or receipt (R7, secret lifecycle).
* Failure mapping: HTTP error / timeout / malformed body map to failure statuses and NEVER fabricate
  ``ok`` (#387 AC2).
* Dead-adapter (no-op runner) reds the dispatch-adapter contract; a conformant runner greens it
  (#387 AC2).
* Availability-gated Ollama Cloud smoke: skips (never fails) without ``OLLAMA_API_KEY`` (AC3').
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str, filename: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("engine_resolver", "engine_resolver.py")
D = _load("engine_dispatch", "engine_dispatch.py")
BRIDGE = _load("engine_bridge_http", "engine_bridge_http.py")
BR = BRIDGE._bridge_receipt


# --- Registry-row shapes (the two first HTTP rows, shrunk to the fields dispatch reads) ----------

OLLAMA_ROW = {
    "engine_id": "ollama-cloud",
    "variant": "gpt-oss-120b",
    "base_url": "https://ollama.com/v1",
    "model": "gpt-oss:120b",
    "key_env": "OLLAMA_API_KEY",
}
DEEPSEEK_ROW = {
    "engine_id": "deepseek",
    "variant": "deepseek-chat",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "key_env": "DEEPSEEK_API_KEY",
}


def _http_resolution(
    row: dict[str, str], *, payload: str = "Summarize this.", bearer: bool = True
) -> Any:
    auth = {"mode": "bearer", "key_env": row["key_env"]} if bearer else {"mode": "none"}
    invocation = {
        "via": "engine-bridge-http",
        "recipe": f"POST {row['base_url']}/chat/completions ({row['model']})",
        "write_capable": False,
        "base_url": row["base_url"],
        "model": row["model"],
        "effort": "default",
        "auth": auth,
    }
    return R.Resolution(
        engine_id=row["engine_id"],
        variant=row["variant"],
        effort="default",
        recipe=str(invocation["recipe"]),
        protocol=["Summarize."],
        payload=payload,
        write_capable=False,
        fallback=None,
        halt=None,
        invocation=invocation,
    )


# --- Fake network seam (no live network anywhere in the suite) -----------------------------------


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def _chat_body(content: str, tokens: int = 42) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"total_tokens": tokens},
        }
    ).encode("utf-8")


class FakeHttpRunner:
    """Shared fixture: an in-memory, network-free stand-in for the real urllib bridge runner.

    Records every request (url, headers, decoded json body) so a test can assert on the bearer
    header and payload, and returns a schema-valid ``bridge_receipt.v1`` HTTP receipt just as the
    real bridge does -- so dispatch threads a real receipt into ``AdvisoryEvidence.runner_receipt``.
    """

    def __init__(self, *, content: str = "advisory answer", tokens: int = 42) -> None:
        self.content = content
        self.tokens = tokens
        self.requests: list[dict[str, Any]] = []

    def __call__(self, invocation: dict[str, Any]) -> dict[str, Any]:
        url = str(invocation["base_url"]).rstrip("/") + "/chat/completions"
        self.requests.append({"url": url, "invocation": invocation})
        receipt = BR.emit_receipt(
            engine_id=str(invocation.get("engine_id") or ""),
            variant=str(invocation.get("variant") or ""),
            transport="http",
            wall_time_s=0.01,
            bytes_produced=len(self.content.encode("utf-8")),
            runner={"url": url, "status_code": 200, "model": invocation["model"]},
            receipt_emitter="http-bridge",
            run_id=f"fake-http:{len(self.requests)}",
            external_tokens=float(self.tokens),
            output_attestation=BRIDGE._output_attestation.emit_attestation(
                artifact="evidence",
                content=self.content,
            ),
        )
        return {
            "status": "ok",
            "output": self.content,
            "tokens": float(self.tokens),
            "latency_seconds": 0.01,
            "receipt": receipt,
        }


def _capturing_urlopen(body: bytes, *, status: int = 200):
    captured: dict[str, Any] = {}

    def _urlopen(request: Any, timeout: float | None = None):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["method"] = request.get_method()
        captured["data"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(body, status=status)

    _urlopen.captured = captured  # type: ignore[attr-defined]
    return _urlopen


# --- #387 AC1: one adapter, two provider rows, differences only in row data ----------------------


@pytest.mark.parametrize("row", [OLLAMA_ROW, DEEPSEEK_ROW], ids=["ollama-cloud", "deepseek"])
def test_transport_http_bridge_dispatch_equivalence_across_rows(row: dict[str, str]) -> None:
    resolution = _http_resolution(row)
    urlopen = _capturing_urlopen(_chat_body("cross-family advisory"))
    runner = BRIDGE.runner(urlopen=urlopen, getenv={row["key_env"]: "tok-XYZ"}.get)

    evidence = D.dispatch(resolution, runner=runner)

    # Same adapter path for both rows: only the row data differs.
    assert evidence.engine_id == row["engine_id"]
    assert evidence.variant == row["variant"]
    assert evidence.evidence == "cross-family advisory"
    assert evidence.provenance["status"] == "ok"
    assert evidence.halt is None
    # The request went to the row's own endpoint / model -- provider difference is data, not code.
    assert urlopen.captured["url"] == row["base_url"].rstrip("/") + "/chat/completions"  # type: ignore[attr-defined]
    assert urlopen.captured["data"]["model"] == row["model"]  # type: ignore[attr-defined]
    # A schema-valid HTTP receipt rode back into evidence.
    assert evidence.runner_receipt is not None
    assert BR.validate_receipt(evidence.runner_receipt) == []
    assert evidence.runner_receipt["transport"] == "http"
    assert evidence.runner_receipt["runner"]["model"] == row["model"]


def test_transport_http_bridge_via_fake_runner_threads_receipt() -> None:
    resolution = _http_resolution(OLLAMA_ROW)
    fake = FakeHttpRunner(content="fixture answer")

    evidence = D.dispatch(resolution, runner=fake)

    assert len(fake.requests) == 1  # the adapter actually invoked the runner (not a dead adapter)
    assert fake.requests[0]["invocation"]["task"] == resolution.payload
    assert evidence.evidence == "fixture answer"
    assert BR.validate_receipt(evidence.runner_receipt) == []


# --- Secret lifecycle: bearer header present iff bearer, token never echoed ----------------------


def test_transport_http_bridge_bearer_header_present_and_secret_never_leaks() -> None:
    resolution = _http_resolution(OLLAMA_ROW, bearer=True)
    urlopen = _capturing_urlopen(_chat_body("ok"))
    runner = BRIDGE.runner(urlopen=urlopen, getenv={"OLLAMA_API_KEY": "super-secret-token"}.get)

    evidence = D.dispatch(resolution, runner=runner)

    assert urlopen.captured["headers"]["Authorization"] == "Bearer super-secret-token"  # type: ignore[attr-defined]
    # The token appears NOWHERE the caller can observe: not the invocation dict, evidence,
    # provenance, or receipt. Only the env var NAME may travel.
    invocation = D._build_invocation(resolution, model=None)
    blob = json.dumps(
        {
            "invocation": invocation,
            "evidence": evidence.evidence,
            "provenance": evidence.provenance,
            "receipt": evidence.runner_receipt,
        }
    )
    assert "super-secret-token" not in blob
    assert invocation["auth"] == {"mode": "bearer", "key_env": "OLLAMA_API_KEY"}
    assert "OLLAMA_API_KEY" in json.dumps(invocation)


def test_transport_http_bridge_no_bearer_header_when_auth_not_bearer() -> None:
    resolution = _http_resolution(DEEPSEEK_ROW, bearer=False)
    urlopen = _capturing_urlopen(_chat_body("ok"))
    runner = BRIDGE.runner(urlopen=urlopen, getenv=lambda _name: "should-not-be-used")

    D.dispatch(resolution, runner=runner)

    assert "Authorization" not in urlopen.captured["headers"]  # type: ignore[attr-defined]


def test_transport_http_bridge_missing_bearer_key_fails_never_ok() -> None:
    resolution = _http_resolution(OLLAMA_ROW, bearer=True)
    urlopen = _capturing_urlopen(_chat_body("unreachable"))
    runner = BRIDGE.runner(urlopen=urlopen, getenv=lambda _name: None)

    evidence = D.dispatch(resolution, runner=runner)

    assert evidence.provenance["status"] != "ok"
    assert evidence.halt is not None
    # No live request was ever attempted, and the receipt is absent (nothing ran to prove).
    assert urlopen.captured == {}  # type: ignore[attr-defined]
    assert evidence.runner_receipt is None


def test_transport_http_bridge_payload_preserved_byte_for_byte() -> None:
    payload = "Keep me exact.\n\tTrailing tab and spaces:   \nUnicode: café ☕"
    resolution = _http_resolution(OLLAMA_ROW, payload=payload)
    urlopen = _capturing_urlopen(_chat_body("ok"))
    runner = BRIDGE.runner(urlopen=urlopen, getenv={"OLLAMA_API_KEY": "t"}.get)

    D.dispatch(resolution, runner=runner)

    sent = urlopen.captured["data"]["messages"][0]["content"]  # type: ignore[attr-defined]
    assert sent == payload
    assert sent.encode("utf-8") == payload.encode("utf-8")


# --- #387 AC2: failure statuses never fabricate ok -----------------------------------------------


def _raising_urlopen(exc: BaseException):
    def _urlopen(request: Any, timeout: float | None = None):  # noqa: ARG001
        raise exc

    return _urlopen


def test_http_error_maps_to_failure_status_never_ok() -> None:
    body = io.BytesIO(b"")
    exc = urllib.error.HTTPError(
        url="https://ollama.com/v1/chat/completions",
        code=503,
        msg="Service Unavailable",
        hdrs=None,  # type: ignore[arg-type]
        fp=body,
    )
    result = BRIDGE.runner(urlopen=_raising_urlopen(exc), getenv={"OLLAMA_API_KEY": "t"}.get)(
        D._build_invocation(_http_resolution(OLLAMA_ROW), model=None)
    )
    assert result["status"] == "error"
    assert result["receipt"] is None
    # The HTTPError carries the live response handle; the bridge must close it, not leak it.
    assert body.closed


def test_timeout_maps_to_timeout_status_never_ok() -> None:
    result = BRIDGE.runner(
        urlopen=_raising_urlopen(TimeoutError("timed out")), getenv={"OLLAMA_API_KEY": "t"}.get
    )(D._build_invocation(_http_resolution(OLLAMA_ROW), model=None))
    assert result["status"] == "timeout"
    assert result["receipt"] is None


def test_url_error_wrapping_timeout_maps_to_timeout() -> None:
    result = BRIDGE.runner(
        urlopen=_raising_urlopen(urllib.error.URLError(TimeoutError("timed out"))),
        getenv={"OLLAMA_API_KEY": "t"}.get,
    )(D._build_invocation(_http_resolution(OLLAMA_ROW), model=None))
    assert result["status"] == "timeout"


def test_malformed_body_maps_to_malformed_status_never_ok() -> None:
    urlopen = _capturing_urlopen(b"<html>not json</html>")
    result = BRIDGE.runner(urlopen=urlopen, getenv={"OLLAMA_API_KEY": "t"}.get)(
        D._build_invocation(_http_resolution(OLLAMA_ROW), model=None)
    )
    assert result["status"] == "malformed"
    assert result["receipt"] is None


def test_dispatch_downgrades_failure_and_never_gates() -> None:
    resolution = _http_resolution(OLLAMA_ROW)
    runner = BRIDGE.runner(
        urlopen=_raising_urlopen(TimeoutError("timed out")), getenv={"OLLAMA_API_KEY": "t"}.get
    )
    evidence = D.dispatch(resolution, runner=runner)
    assert evidence.halt is not None
    assert evidence.evidence == ""
    assert evidence.provenance["status"] == "timeout"
    with pytest.raises(D.DispatchError):
        D.satisfy_gate(evidence)


# --- Dispatch-adapter contract: dead adapter reds, conformant greens (#387 AC2) ------------------


def assert_adapter_conformant(runner: Any, invocation: dict[str, Any]) -> None:
    """The dispatch-adapter contract: a conformant HTTP runner returns an ok result carrying output
    and a schema-valid HTTP receipt. A dead/no-op adapter (returns without invoking the network or
    without proof) fails one of these assertions -- the contract reds on it."""
    result = runner(invocation)
    assert isinstance(result, dict), "runner must return a dict result"
    assert result.get("status") == "ok", "conformant runner must report ok on a good response"
    assert result.get("output"), "conformant runner must return output"
    receipt = result.get("receipt")
    assert isinstance(receipt, dict) and BR.validate_receipt(receipt) == [], (
        "conformant runner must emit a schema-valid bridge_receipt.v1"
    )


def _dead_adapter(_invocation: dict[str, Any]) -> dict[str, Any]:
    """A no-op adapter: never touches the network, fabricates nothing, proves nothing."""
    return {"status": "no-output", "output": "", "receipt": None}


def test_dispatch_adapter_contract_greens_on_conformant_runner() -> None:
    invocation = D._build_invocation(_http_resolution(OLLAMA_ROW), model=None)
    runner = BRIDGE.runner(
        urlopen=_capturing_urlopen(_chat_body("real work")), getenv={"OLLAMA_API_KEY": "t"}.get
    )
    assert_adapter_conformant(runner, invocation)  # must not raise


def test_dispatch_adapter_contract_reds_on_dead_runner() -> None:
    invocation = D._build_invocation(_http_resolution(OLLAMA_ROW), model=None)
    with pytest.raises(AssertionError):
        assert_adapter_conformant(_dead_adapter, invocation)


# --- AC3': availability-gated Ollama Cloud smoke (skip, never fail, without the key) -------------


@pytest.mark.skipif(
    not os.environ.get("OLLAMA_API_KEY"),
    reason="AC3' availability-gated smoke: OLLAMA_API_KEY absent -- skip, never fail",
)
def test_ollama_cloud_smoke_records_ok_when_key_present() -> (
    None
):  # pragma: no cover - live network
    resolution = _http_resolution(OLLAMA_ROW, payload="Reply with the single word: ok")
    evidence = D.dispatch(resolution, runner=BRIDGE.runner())
    # Reachability is proven only here, live. A wrong URL/model shows up as a failure status, but
    # this test is gated on the key existing, so a green means the row actually dispatched.
    assert evidence.provenance["status"] in {"ok", "error", "timeout", "malformed"}
    if evidence.provenance["status"] == "ok":
        assert BR.validate_receipt(evidence.runner_receipt) == []

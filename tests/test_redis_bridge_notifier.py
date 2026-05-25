"""Tests for the channel-notification emitters."""

from __future__ import annotations

import asyncio
import threading

from server import notifier  # type: ignore[import-not-found]


def test_recording_notifier_appends() -> None:
    n = notifier.RecordingNotifier()
    n.emit({"text": "hi"})
    n.emit({"text": "bye"})
    assert n.emitted == [{"text": "hi"}, {"text": "bye"}]


def test_recording_notifier_threadsafe() -> None:
    n = notifier.RecordingNotifier()

    def _hammer() -> None:
        for i in range(50):
            n.emit({"i": i})

    threads = [threading.Thread(target=_hammer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(n.emitted) == 500


def test_noop_notifier_drops_silently() -> None:
    n = notifier.NoopNotifier()
    n.emit({"any": "payload"})  # no exception, no observable effect


def test_async_notifier_schedules_coroutine() -> None:
    """AsyncNotifier.emit() schedules send_notification on the captured loop."""

    sent: list = []

    class StubSession:
        async def send_notification(self, notif):  # noqa: ANN001
            sent.append(notif)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    try:
        n = notifier.AsyncNotifier(StubSession(), loop)
        n.emit({"text": "hello", "chat_id": "c1"})
        # Give the loop a tick to process
        for _ in range(50):
            if sent:
                break
            import time

            time.sleep(0.02)
        assert len(sent) == 1
        notif = sent[0]
        assert notif.method == notifier.CHANNEL_NOTIFICATION_METHOD
        assert notif.params == {"text": "hello", "chat_id": "c1"}
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2.0)
        loop.close()


def test_async_notifier_swallows_loop_errors() -> None:
    """If the loop is closed at emit time, emit() must not raise."""
    loop = asyncio.new_event_loop()
    loop.close()  # close before emit so run_coroutine_threadsafe raises

    class StubSession:
        async def send_notification(self, notif):  # noqa: ANN001
            pass

    n = notifier.AsyncNotifier(StubSession(), loop)
    # Should not raise
    n.emit({"text": "should be dropped"})


def test_channel_method_constant() -> None:
    assert notifier.CHANNEL_NOTIFICATION_METHOD == "notifications/claude/channel"

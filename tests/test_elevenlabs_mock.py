import time
from malachi.conversation.conversation_manager import ConversationManager


def test_mock_lifecycle_duplicate_and_jaw(settings):
    manager = ConversationManager(settings)
    assert manager.start()
    assert not manager.start()
    event = manager.events.get(timeout=2)
    assert event.kind == "connected"
    manager.mark(event, 10)
    deadline = time.monotonic() + 1
    positions = []
    while time.monotonic() < deadline:
        positions.append(manager.jaws.get(timeout=1)[1])
        if max(positions) > 0.1:
            break
    assert max(positions) > 0.1
    manager.shutdown()
    events = []
    while not manager.events.empty():
        events.append(manager.events.get())
    assert any(e.kind == "closed" for e in events)
    for event in events:
        manager.mark(event, 12)
    assert manager.sessions == 1 and manager.total_seconds == 2
    assert manager.playback.samples == 0


def test_auth_failure_is_not_retried(settings):
    settings.conversation_backend = "elevenlabs"

    class Failed:
        attempts = 0

        def __init__(self, *args):
            pass

        async def run(self, stop):
            Failed.attempts += 1
            raise ValueError("missing credentials")

    manager = ConversationManager(settings, Failed)
    manager.start()
    manager.thread.join(2)
    assert Failed.attempts == 1 and manager.failures == 1
    kinds = []
    while not manager.events.empty():
        kinds.append(manager.events.get().kind)
    assert "error" in kinds and kinds[-1] == "closed"


def test_network_retries_are_bounded_and_cancellable(settings):
    settings.conversation_backend = "elevenlabs"

    class Failed:
        attempts = 0

        def __init__(self, *args):
            pass

        async def run(self, stop):
            Failed.attempts += 1
            raise OSError("offline")

    manager = ConversationManager(settings, Failed)
    manager.start()
    event = manager.events.get(timeout=2)
    assert event.kind == "scene" and event.detail == "Disabled"
    event = manager.events.get(timeout=2)
    assert event.kind == "summary"
    manager.shutdown()
    assert not manager.thread.is_alive() and Failed.attempts == 1

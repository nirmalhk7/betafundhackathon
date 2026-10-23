import asyncio
from types import SimpleNamespace

import pytest
from livekit import rtc


class RoomEvents(rtc.EventEmitter):
    """In-memory RTC event boundary: no network or model sessions."""

    def __init__(self, metadata="{}"):
        super().__init__()
        self.metadata = metadata
        self.remote_participants = {"chert-bridge-test": object()}

    def update_metadata(self, value):
        old = self.metadata
        self.metadata = value
        self.emit("room_metadata_changed", old, value)


@pytest.mark.asyncio
async def test_greeting_waits_for_bridge_signal_and_runs_once():
    from chert_bridge import greet_on_bridge_ready

    room = RoomEvents()
    greetings = []

    async def greet():
        greetings.append("greeted")

    task = asyncio.create_task(greet_on_bridge_ready(room, "chert-bridge-test", greet))
    await asyncio.sleep(0)
    room.emit("participant_connected", SimpleNamespace(identity="chert-bridge-test"))
    room.update_metadata('{"chert_bridge_ready": false}')
    await asyncio.sleep(0)
    assert greetings == []
    room.update_metadata('{"chert_bridge_ready": true}')
    assert await asyncio.wait_for(task, 1) is True
    room.update_metadata('{"chert_bridge_ready": true}')
    assert greetings == ["greeted"]


@pytest.mark.asyncio
async def test_signal_received_during_model_startup_is_not_lost():
    from chert_bridge import greet_on_bridge_ready

    room = RoomEvents('{"chert_bridge_ready": true}')
    greetings = []

    async def greet():
        greetings.append("greeted")

    assert await greet_on_bridge_ready(room, "chert-bridge-test", greet) is True
    assert greetings == ["greeted"]


@pytest.mark.asyncio
async def test_no_late_greeting_after_caller_disconnects():
    from chert_bridge import greet_on_bridge_ready

    room = RoomEvents()
    greetings = []

    async def greet():
        greetings.append("greeted")

    task = asyncio.create_task(greet_on_bridge_ready(room, "chert-bridge-test", greet))
    await asyncio.sleep(0)
    room.remote_participants.clear()
    room.emit("participant_disconnected", SimpleNamespace(identity="chert-bridge-test"))
    room.update_metadata('{"chert_bridge_ready": true}')
    assert await asyncio.wait_for(task, 1) is False
    assert greetings == []


@pytest.mark.asyncio
async def test_malformed_metadata_does_not_trigger_greeting_and_room_close_stops_wait():
    from chert_bridge import greet_on_bridge_ready

    room = RoomEvents("invalid json")

    async def greet():
        pytest.fail("must not greet without readiness")

    task = asyncio.create_task(greet_on_bridge_ready(room, "chert-bridge-test", greet))
    await asyncio.sleep(0)
    room.emit("disconnected", None)
    assert await asyncio.wait_for(task, 1) is False


@pytest.mark.asyncio
async def test_cancelled_wait_removes_listeners():
    from chert_bridge import greet_on_bridge_ready

    room = RoomEvents()

    async def greet():
        pytest.fail("must not greet after cancellation")

    task = asyncio.create_task(greet_on_bridge_ready(room, "chert-bridge-test", greet))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    room.update_metadata('{"chert_bridge_ready": true}')

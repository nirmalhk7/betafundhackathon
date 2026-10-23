"""Chert's greeting signal is separate from LiveKit participant arrival."""

import asyncio
import json
from collections.abc import Awaitable, Callable

from livekit import rtc


def bridge_ready(metadata: str) -> bool:
    try:
        data = json.loads(metadata or "{}")
    except (TypeError, ValueError):
        return False
    return isinstance(data, dict) and data.get("chert_bridge_ready") is True


async def greet_on_bridge_ready(
    room: rtc.Room, caller_identity: str, greet: Callable[[], Awaitable[object]]
) -> bool:
    """Greet once after readiness; abandon the greeting when the caller leaves."""
    signal = asyncio.Event()
    ended = False

    def metadata_changed(*_args: object) -> None:
        if bridge_ready(room.metadata):
            signal.set()

    def disconnected(*_args: object) -> None:
        nonlocal ended
        ended = True
        signal.set()

    def participant_left(participant: rtc.RemoteParticipant) -> None:
        if participant.identity == caller_identity:
            disconnected()

    room.on("room_metadata_changed", metadata_changed)
    room.on("disconnected", disconnected)
    room.on("participant_disconnected", participant_left)
    try:
        metadata_changed()
        if caller_identity not in room.remote_participants:
            return False
        await signal.wait()
        if ended or caller_identity not in room.remote_participants:
            return False
        if not bridge_ready(room.metadata):
            return False
        await greet()
        return True
    finally:
        room.off("room_metadata_changed", metadata_changed)
        room.off("disconnected", disconnected)
        room.off("participant_disconnected", participant_left)

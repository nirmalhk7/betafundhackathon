"""Publish a still picture from the same participant as the agent's voice."""

import asyncio
from pathlib import Path

from livekit import rtc
from PIL import Image


def load_picture_frame(path: Path) -> rtc.VideoFrame:
    with Image.open(path) as image:
        image.thumbnail((640, 640))
        rgba = image.convert("RGBA")
        return rtc.VideoFrame(
            rgba.width, rgba.height, rtc.VideoBufferType.RGBA, rgba.tobytes()
        )


async def publish_computer_picture(room: rtc.Room):
    """Keep sending the still frame, including for bridges joining later."""
    frame = load_picture_frame(Path(__file__).parents[1] / "assets" / "computer.png")
    source = rtc.VideoSource(frame.width, frame.height)
    track = rtc.LocalVideoTrack.create_video_track("computer-picture", source)
    publication = await room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(
            source=rtc.TrackSource.SOURCE_CAMERA,
            simulcast=False,
            video_codec=rtc.VideoCodec.VP8,
            video_encoding=rtc.VideoEncoding(max_framerate=5, max_bitrate=350_000),
        ),
    )

    async def stream():
        while True:
            source.capture_frame(frame)
            await asyncio.sleep(0.2)

    task = asyncio.create_task(stream(), name="computer-picture")

    async def close():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            if room.isconnected():
                await room.local_participant.unpublish_track(publication.sid)
        finally:
            await source.aclose()

    return close

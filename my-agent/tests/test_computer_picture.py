from pathlib import Path

from livekit import rtc


def test_computer_picture_decodes_to_bounded_rgba_video_frame():
    from computer_picture import load_picture_frame

    image = Path(__file__).parents[1] / "assets" / "computer.png"
    frame = load_picture_frame(image)
    assert isinstance(frame, rtc.VideoFrame)
    assert frame.type == rtc.VideoBufferType.RGBA
    assert 0 < frame.width <= 640
    assert 0 < frame.height <= 640
    assert len(frame.data) == frame.width * frame.height * 4
    assert len(set(frame.data)) > 10

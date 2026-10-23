import math

import numpy as np

from vision import BodyLanguageReport, FrameSignals, face_signals, head_pose

STRAIGHT = np.eye(4)


def turned(yaw_deg):
    a = math.radians(yaw_deg)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = (
        math.cos(a),
        math.sin(a),
        -math.sin(a),
        math.cos(a),
    )
    return m


def report(frames):
    r = BodyLanguageReport()
    for i, s in enumerate(frames):
        r.add(i / 5, s)
    return r


def test_head_pose_reads_yaw():
    assert head_pose(STRAIGHT) == (0, 0)
    yaw, pitch = head_pose(turned(30))
    assert round(yaw) == 30
    assert round(pitch) == 0


def test_face_signals_eye_contact_when_facing_camera():
    s = face_signals({}, STRAIGHT, (0.5, 0.5))
    assert s.eye_contact
    assert s.look_away is None


def test_face_signals_detects_looking_down_sideways_and_smile():
    assert (
        face_signals(
            {"eyeLookDownLeft": 0.9, "eyeLookDownRight": 0.9}, STRAIGHT, (0.5, 0.5)
        ).look_away
        == "down"
    )
    assert face_signals({}, turned(35), (0.5, 0.5)).look_away == "sideways"
    smile = face_signals(
        {"mouthSmileLeft": 0.8, "mouthSmileRight": 0.7}, STRAIGHT, (0.5, 0.5)
    )
    assert smile.smiling
    assert smile.eye_contact


def test_too_few_frames_says_skip_body_language():
    text = report([FrameSignals(face=True, eye_contact=True)] * 3).summary()
    assert "No usable camera video" in text


def test_summary_reports_eye_contact_and_direction():
    looking = FrameSignals(face=True, eye_contact=True, nose=(0.5, 0.5))
    down = FrameSignals(face=True, look_away="down", nose=(0.5, 0.5))
    text = report([looking] * 10 + [down] * 10).summary()
    assert "Eye contact with the camera 50 percent" in text
    assert "mostly down" in text
    assert "dropped from 100 percent" in text
    assert "held their head steady" in text


def test_summary_flags_face_out_of_frame():
    text = report(
        [FrameSignals(face=False)] * 15
        + [FrameSignals(face=True, eye_contact=True)] * 5
    ).summary()
    assert "in frame only 25 percent" in text


def test_hands_gesturing_and_gesture_counts():
    frames = []
    for i in range(20):
        x = 0.3 if i % 2 else 0.5  # wrist swinging each frame
        gestures = ("Thumb_Up",) if i in (3, 4, 12) else ()
        frames.append(
            FrameSignals(
                face=True,
                eye_contact=True,
                nose=(0.5, 0.5),
                wrists=((x, 0.8),),
                gestures=gestures,
            )
        )
    text = report(frames).summary()
    assert "gestured actively" in text
    assert "thumbs up 2 times" in text


def test_hands_out_of_view():
    text = report([FrameSignals(face=True, eye_contact=True)] * 20).summary()
    assert "hands were out of view" in text


def test_reset_clears_report():
    r = report([FrameSignals(face=True, eye_contact=True)] * 20)
    r.reset()
    assert len(r) == 0


def test_brief_gesture_with_hands_mostly_hidden_is_not_contradictory():
    frames = [FrameSignals(face=True, eye_contact=True)] * 30
    frames[10] = FrameSignals(
        face=True, eye_contact=True, wrists=((0.5, 0.8),), gestures=("Thumb_Up",)
    )
    text = report(frames).summary()
    assert "mostly out of view" in text
    assert "no hand gestures" not in text
    assert "thumbs up 1 time" in text


def test_short_burst_of_gesturing_counts_relative_to_visible_hands():
    still = FrameSignals(face=True, eye_contact=True)
    frames = [still] * 20 + [
        FrameSignals(
            face=True, eye_contact=True, wrists=((0.3 if i % 2 else 0.5, 0.8),)
        )
        for i in range(5)
    ]
    assert "gestured actively" in report(frames).summary()


def test_hands_rarely_in_view_suggests_framing():
    hands = FrameSignals(face=True, eye_contact=True, wrists=((0.5, 0.8),))
    frames = [FrameSignals(face=True, eye_contact=True)] * 14 + [hands] * 6
    text = report(frames).summary()
    assert "in view only 30 percent" in text
    assert "mostly still" not in text

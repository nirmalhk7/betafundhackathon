"""Body-language observations from the caller's camera.

MediaPipe runs locally on sampled frames: no extra model costs and no frames
leave the agent. The coach reads a plain-English summary through a tool.
"""

import asyncio
import contextlib
import logging
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from livekit import rtc

logger = logging.getLogger("agent-coach.vision")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
FACE_MODEL = MODELS_DIR / "face_landmarker.task"
GESTURE_MODEL = MODELS_DIR / "gesture_recognizer.task"

SAMPLE_FPS = 5
MIN_FRAMES = 10  # about two seconds of video before we say anything

# Head turned further than this from the camera is not eye contact.
MAX_YAW_DEG = 18
MAX_PITCH_DEG = 18
# Gaze blendshapes above this mean the eyes are looking away. Looking down is
# lenient because on FaceTime people read the screen just below the camera.
MAX_GAZE_SIDE = 0.55
MAX_GAZE_UP = 0.55
MAX_GAZE_DOWN = 0.7
SMILE_MIN = 0.4
FROWN_MIN = 0.45
# Normalized wrist travel between samples that counts as gesturing.
HAND_MOTION_MIN = 0.02
# Normalized nose-position spread that counts as a restless head.
HEAD_RESTLESS_STD = 0.035

GESTURE_NAMES = {
    "Thumb_Up": "thumbs up",
    "Thumb_Down": "thumbs down",
    "Open_Palm": "open palm",
    "Pointing_Up": "pointing up",
    "Victory": "victory sign",
    "Closed_Fist": "closed fist",
    "ILoveYou": "I love you sign",
}


@dataclass(frozen=True)
class FrameSignals:
    face: bool
    eye_contact: bool = False
    look_away: str | None = None  # "down", "up", "sideways"
    smiling: bool = False
    frowning: bool = False
    nose: tuple[float, float] | None = None
    wrists: tuple[tuple[float, float], ...] = ()
    gestures: tuple[str, ...] = ()
    # Raw measurements, kept for calibration output.
    yaw: float | None = None
    pitch: float | None = None
    gaze: tuple[float, float, float] | None = None  # side, up, down


def head_pose(matrix) -> tuple[float, float]:
    """Yaw and pitch in degrees from MediaPipe's facial transformation matrix."""
    r = np.asarray(matrix, dtype=float)[:3, :3]
    yaw = math.degrees(math.atan2(r[0, 2], r[2, 2]))
    pitch = math.degrees(math.atan2(-r[1, 2], r[2, 2]))
    return yaw, pitch


def face_signals(
    blendshapes: dict[str, float], matrix, nose: tuple[float, float]
) -> FrameSignals:
    def pair(name: str) -> float:
        return (
            blendshapes.get(f"{name}Left", 0) + blendshapes.get(f"{name}Right", 0)
        ) / 2

    yaw, pitch = head_pose(matrix)
    side = (
        max(
            blendshapes.get("eyeLookOutLeft", 0) + blendshapes.get("eyeLookInRight", 0),
            blendshapes.get("eyeLookInLeft", 0) + blendshapes.get("eyeLookOutRight", 0),
        )
        / 2
    )
    down, up = pair("eyeLookDown"), pair("eyeLookUp")

    look_away = None
    if abs(yaw) > MAX_YAW_DEG or side > MAX_GAZE_SIDE:
        look_away = "sideways"
    elif pitch < -MAX_PITCH_DEG or down > MAX_GAZE_DOWN:
        look_away = "down"
    elif pitch > MAX_PITCH_DEG or up > MAX_GAZE_UP:
        look_away = "up"

    return FrameSignals(
        face=True,
        eye_contact=look_away is None,
        look_away=look_away,
        smiling=pair("mouthSmile") > SMILE_MIN,
        frowning=pair("browDown") > FROWN_MIN,
        nose=nose,
        yaw=yaw,
        pitch=pitch,
        gaze=(side, up, down),
    )


def _pct(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


class BodyLanguageReport:
    """Aggregates per-frame signals into observations the coach can speak about."""

    def __init__(self) -> None:
        self._frames: list[tuple[float, FrameSignals]] = []

    def __len__(self) -> int:
        return len(self._frames)

    def add(self, t: float, signals: FrameSignals) -> None:
        self._frames.append((t, signals))

    def reset(self) -> None:
        self._frames.clear()

    def summary(self) -> str:
        frames = [s for _, s in self._frames]
        if len(frames) < MIN_FRAMES:
            return "No usable camera video. Do not comment on body language this round."

        total = len(frames)
        seconds = round(self._frames[-1][0] - self._frames[0][0])
        faces = [s for s in frames if s.face]
        lines = [f"Camera observations over the last {seconds} seconds."]

        face_pct = _pct(len(faces), total)
        if face_pct < 60:
            lines.append(
                f"Their face was in frame only {face_pct} percent of the time, "
                "so they may be too close, off-center, or poorly lit."
            )
        if len(faces) < MIN_FRAMES:
            return " ".join(lines)

        eye_pct = _pct(sum(s.eye_contact for s in faces), len(faces))
        away = [s.look_away for s in faces if s.look_away]
        eye_line = f"Eye contact with the camera {eye_pct} percent of the time"
        if away:
            direction = max(set(away), key=away.count)
            eye_line += f"; when they looked away it was mostly {direction}"
        lines.append(eye_line + ".")

        half = len(faces) // 2
        first = _pct(sum(s.eye_contact for s in faces[:half]), half)
        second = _pct(sum(s.eye_contact for s in faces[half:]), len(faces) - half)
        if abs(first - second) >= 20:
            trend = "dropped" if second < first else "improved"
            lines.append(
                f"Eye contact {trend} from {first} percent in the first half "
                f"to {second} percent in the second half."
            )

        smile_pct = _pct(sum(s.smiling for s in faces), len(faces))
        frown_pct = _pct(sum(s.frowning for s in faces), len(faces))
        if smile_pct >= 40:
            lines.append(f"They smiled a lot, {smile_pct} percent of the time.")
        elif smile_pct >= 10:
            lines.append(f"They smiled some of the time, {smile_pct} percent.")
        else:
            lines.append("They rarely smiled; their expression was mostly neutral.")
        if frown_pct >= 25:
            lines.append(
                f"Their brow was furrowed {frown_pct} percent of the time, "
                "which can read as tense or unsure."
            )

        noses = np.array([s.nose for s in faces if s.nose])
        if len(noses) >= MIN_FRAMES:
            spread = float(noses.std(axis=0).max())
            lines.append(
                "Their head moved around a lot, which can look restless."
                if spread > HEAD_RESTLESS_STD
                else "They held their head steady."
            )

        lines.append(self._hands_line(frames))
        return " ".join(lines)

    @staticmethod
    def _hands_line(frames: list[FrameSignals]) -> str:
        total = len(frames)
        visible = sum(bool(s.wrists) for s in frames)
        moving = 0
        for prev, cur in zip(frames, frames[1:], strict=False):
            if prev.wrists and cur.wrists:
                travel = max(
                    math.dist(a, b)
                    for a, b in zip(prev.wrists, cur.wrists, strict=False)
                )
                moving += travel > HAND_MOTION_MIN

        counts: dict[str, int] = {}
        for prev, cur in zip([FrameSignals(face=False), *frames], frames, strict=False):
            for g in set(cur.gestures) - set(prev.gestures):
                counts[g] = counts.get(g, 0) + 1

        visible_pct = _pct(visible, total)
        if visible_pct < 10 and counts:
            line = "Their hands were mostly out of view."
        elif visible_pct < 10:
            line = "Their hands were out of view, so no hand gestures were seen."
        elif _pct(moving, visible) >= 30:
            line = (
                f"Their hands were visible {visible_pct} percent of the time and "
                "they gestured actively while talking."
            )
        elif visible_pct < 40:
            line = (
                f"Their hands were in view only {visible_pct} percent of the time, "
                "so gestures were hard to judge."
            )
        else:
            line = (
                f"Their hands were visible {visible_pct} percent of the time but "
                "mostly still."
            )
        if 10 <= visible_pct < 40:
            line += " Sitting a little farther from the camera would show them."
        if counts:
            seen = ", ".join(
                f"{GESTURE_NAMES.get(g, g)} {n} time{'s' if n > 1 else ''}"
                for g, n in sorted(counts.items(), key=lambda kv: -kv[1])
            )
            line += f" Gestures recognized: {seen}."
        return line


class FrameAnalyzer:
    """Runs MediaPipe on RGB frames. Not thread-safe: call from one thread."""

    def __init__(self) -> None:
        from mediapipe.tasks.python import BaseOptions, vision

        self._face = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(FACE_MODEL)),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
            )
        )
        self._gestures = vision.GestureRecognizer.create_from_options(
            vision.GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path=str(GESTURE_MODEL)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
            )
        )
        self._last_ts = -1

    def analyze(self, rgb: np.ndarray, timestamp_ms: int) -> FrameSignals:
        import mediapipe as mp

        # MediaPipe video mode requires strictly increasing timestamps.
        timestamp_ms = max(timestamp_ms, self._last_ts + 1)
        self._last_ts = timestamp_ms
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        face = self._face.detect_for_video(image, timestamp_ms)
        hands = self._gestures.recognize_for_video(image, timestamp_ms)

        wrists = tuple((h[0].x, h[0].y) for h in hands.hand_landmarks)
        gestures = tuple(
            g[0].category_name
            for g in hands.gestures
            if g and g[0].category_name in GESTURE_NAMES and g[0].score > 0.6
        )
        if not face.face_blendshapes:
            return FrameSignals(face=False, wrists=wrists, gestures=gestures)

        blendshapes = {c.category_name: c.score for c in face.face_blendshapes[0]}
        nose = face.face_landmarks[0][1]
        signals = face_signals(
            blendshapes, face.facial_transformation_matrixes[0], (nose.x, nose.y)
        )
        return replace(signals, wrists=wrists, gestures=gestures)

    def close(self) -> None:
        self._face.close()
        self._gestures.close()


class VisionTracker:
    """Samples the caller's camera track and keeps a running body-language report."""

    def __init__(self, room: rtc.Room, participant_identity: str | None = None) -> None:
        self._room = room
        self._identity = participant_identity
        self.report = BodyLanguageReport()
        self._analyzer: FrameAnalyzer | None = None
        self._task: asyncio.Task | None = None
        self._track_sid: str | None = None
        self._start = time.monotonic()

    @property
    def watching(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        self._room.on("track_published", self._on_published)
        self._room.on("track_subscribed", self._on_subscribed)
        self._room.on("track_unsubscribed", self._on_unsubscribed)
        for participant in self._room.remote_participants.values():
            for pub in participant.track_publications.values():
                self._on_published(pub, participant)
                if pub.track:
                    self._on_subscribed(pub.track, pub, participant)

    def summary(self, *, reset: bool = True) -> str:
        text = self.report.summary()
        if not self.watching and len(self.report) == 0:
            text = (
                "The camera is off or this is an audio call. Do not comment on "
                "body language."
            )
        if reset:
            self.report.reset()
        return text

    def _wanted(self, participant: rtc.RemoteParticipant) -> bool:
        if self._identity is not None:
            return participant.identity == self._identity
        # Never watch the coach's own avatar.
        return participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT

    def _on_published(
        self, pub: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ) -> None:
        # Chert rooms connect audio-only; opt in to the caller's camera.
        if pub.kind == rtc.TrackKind.KIND_VIDEO and self._wanted(participant):
            pub.set_subscribed(True)

    def _on_subscribed(
        self,
        track: rtc.Track,
        pub: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_VIDEO or not self._wanted(participant):
            return
        if self._track_sid == pub.sid:
            return
        if self._task:
            self._task.cancel()
        self._track_sid = pub.sid
        logger.info("watching camera of %s", participant.identity)
        self._task = asyncio.create_task(self._consume(track))

    def _on_unsubscribed(
        self,
        _track: rtc.Track,
        pub: rtc.RemoteTrackPublication,
        _participant: rtc.RemoteParticipant,
    ) -> None:
        # Close the stream while the room is still alive, not at teardown.
        if pub.sid == self._track_sid and self._task:
            self._task.cancel()
            self._track_sid = None

    async def _consume(self, track: rtc.Track) -> None:
        stream = rtc.VideoStream(track, format=rtc.VideoBufferType.RGB24)
        next_at = 0.0
        try:
            if self._analyzer is None:
                self._analyzer = await asyncio.to_thread(FrameAnalyzer)
            async for event in stream:
                now = time.monotonic()
                if now < next_at:
                    continue
                next_at = now + 1 / SAMPLE_FPS
                frame = event.frame
                rgb = np.frombuffer(frame.data, dtype=np.uint8).reshape(
                    frame.height, frame.width, 3
                )
                t = now - self._start
                signals = await asyncio.to_thread(
                    self._analyzer.analyze, rgb.copy(), int(t * 1000)
                )
                self.report.add(t, signals)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("vision pipeline stopped")
        finally:
            await stream.aclose()

    async def aclose(self) -> None:
        self._room.off("track_published", self._on_published)
        self._room.off("track_subscribed", self._on_subscribed)
        self._room.off("track_unsubscribed", self._on_unsubscribed)
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._analyzer:
            self._analyzer.close()

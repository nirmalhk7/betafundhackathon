"""Try the body-language tracker on your webcam, no LiveKit or FaceTime needed.

    uv run --python 3.13 python scripts/vision_check.py --seconds 20

Talk to the camera as if you were pitching; the script prints a live line per
second and then the summary the coach would receive.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vision import SAMPLE_FPS, BodyLanguageReport, FrameAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit("Could not open the camera. Allow camera access for your terminal.")

    analyzer, report = FrameAnalyzer(), BodyLanguageReport()
    start = next_at = time.monotonic()
    last_print = 0.0
    try:
        while (now := time.monotonic()) - start < args.seconds:
            ok, bgr = cap.read()
            if not ok or now < next_at:
                continue
            next_at = now + 1 / SAMPLE_FPS
            t = now - start
            s = analyzer.analyze(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), int(t * 1000))
            report.add(t, s)
            if t - last_print >= 1:
                last_print = t
                raw = ""
                if s.yaw is not None:
                    side, up, down = s.gaze
                    raw = (
                        f" yaw={s.yaw:+5.0f} pitch={s.pitch:+5.0f} "
                        f"gaze side={side:.2f} up={up:.2f} down={down:.2f}"
                    )
                print(
                    f"{t:5.1f}s face={s.face!s:5} eye_contact={s.eye_contact!s:5} "
                    f"away={s.look_away or '-':8} smile={s.smiling!s:5} "
                    f"hands={len(s.wrists)} gestures={','.join(s.gestures) or '-'}"
                    + raw
                )
    finally:
        cap.release()
        analyzer.close()

    print("\nWhat the coach receives:\n")
    print(report.summary())


if __name__ == "__main__":
    main()

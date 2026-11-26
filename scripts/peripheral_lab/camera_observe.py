"""Bounded, local-only console observation; no audio or network access."""
import argparse
from pathlib import Path
import time

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--seconds", type=int, default=100)
    parser.add_argument("--exposure", type=int, default=-6)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error("duration must be 1..120 seconds")
    args.out.mkdir(exist_ok=False)
    camera = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    try:
        if not camera.isOpened():
            raise RuntimeError("camera unavailable")
        camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        changed = camera.set(cv2.CAP_PROP_EXPOSURE, args.exposure)
        print(f"camera_opened=1 exposure_request_accepted={int(changed)}", flush=True)
        end, next_frame, index = time.monotonic() + args.seconds, 0, 0
        while time.monotonic() < end:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("camera read failed")
            if time.monotonic() >= next_frame:
                index += 1
                if not cv2.imwrite(str(args.out / f"frame_{index:03d}.jpg"), frame):
                    raise RuntimeError("cannot save local frame")
                next_frame = time.monotonic() + 2
        print(f"frames_saved={index}", flush=True)
    finally:
        camera.release()


if __name__ == "__main__":
    main()

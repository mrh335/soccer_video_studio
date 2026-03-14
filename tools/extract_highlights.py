"""Basic goalie-highlight extractor.

This script is intentionally conservative and modular:
- Uses frame-difference motion inside a goal-area ROI as a proxy for action.
- Converts high-motion windows into keep-segments.
- Exports either:
  1) a CSV list of segments, or
  2) a stitched highlight video via ffmpeg.

You can later replace `motion_score` with YOLO-based ball/goalie logic while
keeping the same segment-generation pipeline.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import tempfile
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Segment:
    start: float
    end: float


def parse_roi(roi: str, width: int, height: int) -> tuple[int, int, int, int]:
    """Parse ROI as fractions: x,y,w,h in [0,1]."""
    x, y, w, h = [float(v.strip()) for v in roi.split(",")]
    return int(x * width), int(y * height), int(w * width), int(h * height)


def merge_segments(segments: list[Segment], max_gap: float) -> list[Segment]:
    if not segments:
        return []
    merged = [segments[0]]
    for seg in segments[1:]:
        if seg.start - merged[-1].end <= max_gap:
            merged[-1].end = max(merged[-1].end, seg.end)
        else:
            merged.append(seg)
    return merged


def detect_motion_segments(
    video_path: str,
    roi_frac: str,
    threshold: float,
    min_len: float,
    pre_pad: float,
    post_pad: float,
    merge_gap: float,
) -> tuple[list[Segment], float]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count else 0.0

    ok, prev = cap.read()
    if not ok:
        raise RuntimeError("Video has no readable frames")

    h, w = prev.shape[:2]
    rx, ry, rw, rh = parse_roi(roi_frac, w, h)

    prev_gray = cv2.cvtColor(prev[ry : ry + rh, rx : rx + rw], cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (5, 5), 0)

    scores: list[float] = [0.0]

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cur_gray = cv2.cvtColor(frame[ry : ry + rh, rx : rx + rw], cv2.COLOR_BGR2GRAY)
        cur_gray = cv2.GaussianBlur(cur_gray, (5, 5), 0)
        diff = cv2.absdiff(prev_gray, cur_gray)
        score = float(np.mean(diff))
        scores.append(score)
        prev_gray = cur_gray

    cap.release()

    smooth_window = max(1, int(1.5 * fps))
    kernel = np.ones(smooth_window, dtype=np.float32) / smooth_window
    smooth_scores = np.convolve(np.array(scores, dtype=np.float32), kernel, mode="same")

    active = smooth_scores >= threshold

    segments: list[Segment] = []
    start_idx = None
    for idx, on in enumerate(active):
        if on and start_idx is None:
            start_idx = idx
        elif not on and start_idx is not None:
            end_idx = idx
            start_t = max(0.0, start_idx / fps - pre_pad)
            end_t = min(duration, end_idx / fps + post_pad)
            if end_t - start_t >= min_len:
                segments.append(Segment(start_t, end_t))
            start_idx = None

    if start_idx is not None:
        start_t = max(0.0, start_idx / fps - pre_pad)
        end_t = duration
        if end_t - start_t >= min_len:
            segments.append(Segment(start_t, end_t))

    segments = merge_segments(segments, merge_gap)
    return segments, duration


def write_segments_csv(segments: list[Segment], output_csv: str) -> None:
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start_sec", "end_sec", "duration_sec"])
        for s in segments:
            writer.writerow([f"{s.start:.3f}", f"{s.end:.3f}", f"{(s.end - s.start):.3f}"])


def render_with_ffmpeg(video_path: str, segments: list[Segment], output_path: str) -> None:
    with tempfile.TemporaryDirectory(prefix="highlights_") as tmpdir:
        concat_list = os.path.join(tmpdir, "concat.txt")
        clip_paths: list[str] = []

        for i, seg in enumerate(segments, start=1):
            clip_path = os.path.join(tmpdir, f"clip_{i:04d}.mp4")
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{seg.start:.3f}",
                "-to",
                f"{seg.end:.3f}",
                "-i",
                video_path,
                "-c",
                "copy",
                clip_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_paths.append(clip_path)

        with open(concat_list, "w", encoding="utf-8") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-c",
            "copy",
            output_path,
        ]
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract goalie highlights from a full game video.")
    parser.add_argument("input", help="Input game video path")
    parser.add_argument("--roi", default="0.2,0.25,0.6,0.5", help="Goal ROI as x,y,w,h fractions")
    parser.add_argument("--threshold", type=float, default=7.0, help="Motion threshold")
    parser.add_argument("--min-len", type=float, default=2.0, help="Minimum segment length (sec)")
    parser.add_argument("--pre-pad", type=float, default=4.0, help="Seconds before detected action")
    parser.add_argument("--post-pad", type=float, default=3.0, help="Seconds after detected action")
    parser.add_argument("--merge-gap", type=float, default=4.0, help="Merge segments separated by <= this gap")
    parser.add_argument("--segments-csv", default="segments.csv", help="Output CSV path")
    parser.add_argument("--render", help="Optional output .mp4 highlight path")
    args = parser.parse_args()

    segments, duration = detect_motion_segments(
        video_path=args.input,
        roi_frac=args.roi,
        threshold=args.threshold,
        min_len=args.min_len,
        pre_pad=args.pre_pad,
        post_pad=args.post_pad,
        merge_gap=args.merge_gap,
    )

    write_segments_csv(segments, args.segments_csv)

    total_keep = sum(s.end - s.start for s in segments)
    print(f"Video duration: {duration:.1f}s")
    print(f"Detected segments: {len(segments)}")
    print(f"Kept duration: {total_keep:.1f}s ({(100 * total_keep / duration) if duration else 0:.1f}%)")
    print(f"Wrote: {args.segments_csv}")

    if args.render:
        render_with_ffmpeg(args.input, segments, args.render)
        print(f"Wrote highlight video: {args.render}")


if __name__ == "__main__":
    main()

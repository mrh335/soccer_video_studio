# Goalie Highlight Automation Plan

This guide outlines a practical way to automate your current manual process:

- Input: one full-length game recording (e.g., 80 minutes from a GoPro behind the net).
- Output: short highlight video (~10 minutes) containing only goalie actions near the goal.

## Approach summary

Use a 3-stage workflow:

1. **Detect likely action windows** with computer vision (ball + player activity near the goal).
2. **Review and tweak timestamps quickly** (optional lightweight human pass).
3. **Auto-render final highlight reel** with FFmpeg.

This keeps your editing time low while preserving control.

---

## Recommended stack

- Python 3.10+
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) for object detection/tracking
- OpenCV for frame processing
- FFmpeg for slicing + concatenating clips

> You can keep using PowerDirector for final polish. This pipeline can generate clip timestamps (or small clips) first, then you import those into PowerDirector.

---

## Detection logic (goalie-focused)

Score each moment as an "action probability" based on:

- **Ball inside a goal-zone ROI** (region of interest) in front of your net.
- **Ball speed spike / direction change** (shots, deflections, rebounds).
- **Goalie proximity to ball** (ball close to detected player near center of goal).
- **Goalie posture/motion burst** (dives, blocks, kicks).

Then:

- Smooth scores over time (e.g., rolling 1.5–2.0 seconds).
- Keep windows above threshold.
- Add padding (e.g., `+4s` before and `+3s` after).
- Merge nearby windows (e.g., gaps shorter than 4s).

This usually converts 80 minutes into a short set of candidate clips.

---

## Net-removal options (from behind-net camera)

Completely removing the net in all frames is hard, but these options help:

1. **Best practical: camera placement tweak**
   - Raise camera and zoom/crop so net lines are out of focus and less dominant.
   - Use wider distance and crop in post.

2. **Post-process mask/inpaint (semi-automatic)**
   - Build a static net mask from the first seconds.
   - Apply line detection + inpainting for thin strands.
   - Works best when the net is sharp and background is stable.

3. **AI segmentation/compositing (advanced)**
   - Segment players + ball and reconstruct background.
   - Higher compute and still imperfect for fast action.

In practice, a mild crop + contrast tuning is often more reliable than full net removal.

---

## Suggested workflow

1. Record as usual.
2. Run an analysis script to output `segments.csv`.
3. Auto-create clips (or one merged highlight MP4).
4. Optional quick review pass to delete bad segments.
5. Deliver final video.

---

## Notes for PowerDirector users

If you want to keep PowerDirector as the editor:

- Generate clip files from the script (`clip_001.mp4`, `clip_002.mp4`, ...).
- Import all clips into PowerDirector media bin.
- Drop all clips on timeline at once and add your titles/music.

This avoids manual trimming of the full game.

---

## Simple GUI launcher (Windows)

A `run.bat` file is included at the project root.

- Double-click `run.bat` to launch a PySide6 desktop app.
- The GUI lets you:
  - pick a video,
  - preview your ROI on the first frame,
  - run analysis to generate `segments.csv`,
  - optionally render a stitched highlight video.

Install dependencies first:

```bash
pip install pyside6 opencv-python numpy
```


---

## Change this project to a different Git repo

If you want this project to live in another repository, run:

```bash
python tools/change_repo_remote.py --new-url <NEW_REPO_URL> --show
```

Examples:

```bash
python tools/change_repo_remote.py --new-url git@github.com:your-org/goalie-highlights.git --show
python tools/change_repo_remote.py --new-url https://github.com/your-org/goalie-highlights.git --remote upstream --show
```

Then push the current branch to the new remote:

```bash
git push -u origin work
```

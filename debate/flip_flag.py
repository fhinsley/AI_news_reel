#!/usr/bin/env python3
"""flip_flag.py
Horizontally flips stock_videos/OldGloryCrop.mp4 and saves as
stock_videos/OldGloryFlip.mp4.

Run once from project root:
  python debate/flip_flag.py
"""

from pathlib import Path
from moviepy import VideoFileClip, vfx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT  = PROJECT_ROOT / "stock_videos" / "OldGloryCrop.mp4"
OUTPUT = PROJECT_ROOT / "stock_videos" / "OldGloryFlip.mp4"

if not INPUT.exists():
    raise FileNotFoundError(f"Input not found: {INPUT}")

print(f"Flipping: {INPUT}")
clip = VideoFileClip(str(INPUT)).with_effects([vfx.MirrorX()])
clip.write_videofile(str(OUTPUT), codec="libx264", audio_codec="aac", logger="bar")
print(f"Saved: {OUTPUT}")

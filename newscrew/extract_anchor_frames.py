#!/usr/bin/env python3
"""
extract_anchor_frames.py — Extract sample frames from an anchor clip
so you can browse and pick the best natural resting face.

Saves one JPG per interval into a preview folder alongside the clip.
Open the folder in Finder/Preview, pick your favorite, note the frame number,
then set it as the anchor's rest_frame in config.py.

Usage:
    # Extract every 0.5 seconds from a specific clip
    python extract_anchor_frames.py path/to/clip.mp4

    # Extract every 1 second
    python extract_anchor_frames.py path/to/clip.mp4 --interval 1.0

    # Extract all clips in anchor_clips/ for the current episode
    python extract_anchor_frames.py --all
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from moviepy import VideoFileClip

import config


def extract_frames(clip_path: Path, interval: float = 0.5) -> Path:
    """
    Extract frames every `interval` seconds from clip_path.
    Saves JPGs to a subfolder named <clip_stem>_frames/ next to the clip.
    Returns the output folder path.
    """
    out_dir = clip_path.parent / f"{clip_path.stem}_frames"
    out_dir.mkdir(exist_ok=True)

    print(f"  Loading: {clip_path.name}")
    clip = VideoFileClip(str(clip_path))
    duration = clip.duration
    print(f"  Duration: {duration:.1f}s  →  extracting every {interval}s")

    timestamps = []
    t = 0.0
    while t <= duration:
        timestamps.append(t)
        t += interval

    for t in timestamps:
        frame = clip.get_frame(min(t, duration - 0.05))   # avoid exact end
        img = Image.fromarray(frame.astype(np.uint8))
        label = f"{t:06.2f}s".replace(".", "_")
        out_path = out_dir / f"frame_{label}.jpg"
        img.save(str(out_path), quality=90)

    clip.close()

    print(f"  Saved {len(timestamps)} frames to: {out_dir}")
    print(f"  Open in Finder: open \"{out_dir}\"")
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Extract anchor clip frames for rest-face selection")
    parser.add_argument("clip", nargs="?", type=Path, help="Path to anchor clip MP4")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between frames (default 0.5)")
    parser.add_argument("--all", action="store_true", help="Extract from all clips in current episode's anchor_clips/")
    args = parser.parse_args()

    if args.all:
        clips_dir = config.ANCHOR_CLIPS_DIR
        if not clips_dir.exists():
            print(f"ERROR: anchor_clips dir not found: {clips_dir}")
            sys.exit(1)
        clips = sorted(clips_dir.glob("*.mp4"))
        # Skip _short clips
        clips = [c for c in clips if "_short" not in c.stem and "_frames" not in c.stem]
        if not clips:
            print(f"No clips found in {clips_dir}")
            sys.exit(1)
        print(f"Found {len(clips)} clips in {clips_dir}\n")
        for clip_path in clips:
            extract_frames(clip_path, args.interval)
            print()
    elif args.clip:
        if not args.clip.exists():
            print(f"ERROR: file not found: {args.clip}")
            sys.exit(1)
        extract_frames(args.clip, args.interval)
    else:
        parser.print_help()
        sys.exit(1)

    print("\nDone. Browse the _frames folders, pick your favorite timestamp for each anchor,")
    print("then add REST_FRAME_<ANCHOR_ID> entries to config.py (or note them for build_video.py).")


if __name__ == "__main__":
    main()

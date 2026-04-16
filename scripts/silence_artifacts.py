#!/usr/bin/env python3
"""Silence TTS artifacts in multi-clip audio files.

ElevenLabs sometimes produces a brief noise or click at SSML break tag
boundaries. This script finds those regions in each clip's timestamp file
and uses ffmpeg to zero out the audio there.

Operates in-place on each mp3 in the week folder.
Pipeline position: run after newsreel_tts.py, before build_video.py.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Core functions (unchanged from original — work on a single timestamp file)
# ---------------------------------------------------------------------------

def find_artifact_regions(timestamp_file, speed_factor=1.0):
    """Return list of (start, end) tuples in seconds where artifacts occur."""
    with open(timestamp_file, "r") as f:
        data = json.load(f)

    characters = data["characters"]
    starts     = data["character_start_times_seconds"]
    ends       = data["character_end_times_seconds"]

    silence_regions = []
    i = 0

    while i < len(characters):
        if characters[i] == "<" and i + 5 < len(characters):
            tag = "".join(characters[i:i+6])
            if tag == "<break":
                j = i - 1
                while j >= 0 and characters[j] in [" ", "\n"]:
                    j -= 1

                if j >= 0 and ends[j] < starts[i]:
                    region_start = max(0, ends[j] - 0.05) / speed_factor
                    region_end   = starts[i] / speed_factor
                    if region_end - region_start > 0.05:
                        silence_regions.append((region_start, region_end))
        i += 1

    return silence_regions


def build_ffmpeg_filter(silence_regions):
    """Build an ffmpeg audio filter string to zero out the given regions."""
    if not silence_regions:
        return "anull"
    parts = [
        f"volume=enable='between(t,{s:.3f},{e:.3f})':volume=0"
        for s, e in silence_regions
    ]
    return ",".join(parts)


def silence_clip(mp3_path: Path, ts_path: Path) -> int:
    """Apply artifact silencing to one mp3 clip. Returns number of regions fixed."""
    regions = find_artifact_regions(str(ts_path))
    if not regions:
        return 0

    af = build_ffmpeg_filter(regions)

    # Write to a temp file then replace original
    tmp = mp3_path.with_suffix(".tmp.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-af", af,
        "-c:a", "libmp3lame",
        str(tmp)
    ], check=True, capture_output=True)

    tmp.replace(mp3_path)
    return len(regions)


# ---------------------------------------------------------------------------
# Main — process all clips in the manifest
# ---------------------------------------------------------------------------

def main() -> int:
    week  = Path(config.WEEK_FOLDER)
    total = 0

    for stem, label in config.VIDEO_CLIP_MANIFEST:
        mp3_path = week / f"{stem}.mp3"
        ts_path  = week / f"{stem}_timestamps.json"

        if not mp3_path.exists():
            print(f"  SKIP: {stem}.mp3 not found")
            continue
        if not ts_path.exists():
            print(f"  SKIP: {stem}_timestamps.json not found")
            continue

        count = silence_clip(mp3_path, ts_path)
        if count:
            print(f"  {stem}: silenced {count} artifact region(s)")
        else:
            print(f"  {stem}: no artifacts found")
        total += count

    print(f"\nDone. {total} artifact region(s) silenced across all clips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

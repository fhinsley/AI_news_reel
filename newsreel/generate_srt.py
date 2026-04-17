#!/usr/bin/env python3
"""Generate an SRT caption file from the multi-clip timestamp data.

Reads each clip's timestamp JSON and the CLIP_MANIFEST to reconstruct
the full timeline, then groups characters into 5-7 word caption chunks
and writes a standard SRT file.

Pipeline position: run after build_video.py (needs the same clip set).
Output: <WEEK_FOLDER>/Captions.srt
"""

import json
from pathlib import Path
import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def srt_timecode(seconds: float) -> str:
    """Convert seconds to SRT timecode: HH:MM:SS,mmm"""
    ms  = int(round(seconds * 1000))
    hh  = ms // 3_600_000;  ms %= 3_600_000
    mm  = ms // 60_000;     ms %= 60_000
    ss  = ms // 1_000;      ms %= 1_000
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"


def load_timestamps(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def chars_to_words(characters, start_times, end_times):
    """Group character-level data into (word, start, end) tuples.

    SSML tags like <break time="1s" /> are stripped before grouping —
    they appear in the character stream but should never appear in captions.
    """
    words = []
    current_word = ""
    word_start   = None
    word_end     = None
    in_tag       = False  # True while inside an SSML < ... > tag

    for char, t_start, t_end in zip(characters, start_times, end_times):
        # Track SSML tag boundaries and skip tag characters entirely
        if char == "<":
            in_tag = True
            continue
        if char == ">":
            in_tag = False
            continue
        if in_tag:
            continue

        if char in (" ", "\n", "\t"):
            if current_word:
                words.append((current_word, word_start, word_end))
                current_word = ""
                word_start   = None
        else:
            if word_start is None:
                word_start = t_start
            current_word += char
            word_end = t_end

    if current_word:
        words.append((current_word, word_start, word_end))

    return words


def chunk_words(words, target=config.SRT_TARGET_WORDS, max_duration=config.SRT_MAX_DURATION):
    """Group words into caption-sized chunks of ~target words."""
    chunks = []
    current = []

    for word, t_start, t_end in words:
        current.append((word, t_start, t_end))

        chunk_duration = current[-1][2] - current[0][1]
        if len(current) >= target or chunk_duration >= max_duration:
            chunks.append(current)
            current = []

    if current:
        chunks.append(current)

    return chunks


def build_srt_entries(chunks, time_offset: float):
    """Convert word chunks to (start, end, text) triples with timeline offset."""
    entries = []
    for chunk in chunks:
        if not chunk:
            continue
        text  = " ".join(w for w, _, _ in chunk)
        start = chunk[0][1] + time_offset
        end   = chunk[-1][2] + time_offset
        # Enforce min/max duration
        end   = max(end, start + config.SRT_MIN_DURATION)
        end   = min(end, start + config.SRT_MAX_DURATION)
        entries.append((start, end, text))
    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    week   = Path(config.WEEK_FOLDER)
    cursor = config.VIDEO_INTRO_SILENCE
    all_entries = []

    for stem, label in config.VIDEO_CLIP_MANIFEST:
        ts_path = week / f"{stem}_timestamps.json"
        mp3_path = week / f"{stem}.mp3"

        if not mp3_path.exists():
            print(f"  SKIP: {stem}.mp3 not found")
            cursor += config.VIDEO_INTER_CLIP_SILENCE
            continue

        # Get clip duration from audio file
        from moviepy import AudioFileClip
        clip_duration = AudioFileClip(str(mp3_path)).duration

        if not ts_path.exists():
            print(f"  WARNING: no timestamps for {stem} — captions skipped for this clip")
            cursor += clip_duration + config.VIDEO_INTER_CLIP_SILENCE
            continue

        ts   = load_timestamps(ts_path)
        words = chars_to_words(
            ts["characters"],
            ts["character_start_times_seconds"],
            ts["character_end_times_seconds"],
        )
        chunks  = chunk_words(words)
        entries = build_srt_entries(chunks, time_offset=cursor)
        all_entries.extend(entries)

        print(f"  {stem}: {len(entries)} captions")
        cursor += clip_duration + config.VIDEO_INTER_CLIP_SILENCE

    # Write SRT
    lines = []
    for i, (start, end, text) in enumerate(all_entries, start=1):
        lines.append(str(i))
        lines.append(f"{srt_timecode(start)} --> {srt_timecode(end)}")
        lines.append(text)
        lines.append("")

    config.SRT_OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{len(all_entries)} captions written to: {config.SRT_OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

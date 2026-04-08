#!/usr/bin/env python3
"""Build the final newsreel video from multi-voice audio clips and json.

Pipeline:
  1. Load json — source of truth for overlays and sources
  2. Stitch the sequenced audio clips (00-99) into one timeline
  3. Build overlay list (section headers + story titles) with absolute timestamps
  4. Build background video segments keyed to section change points
  5. Composite everything and write News.mp4
"""

from moviepy import (
    AudioClip, AudioFileClip, ColorClip, CompositeVideoClip,
    TextClip, VideoFileClip, concatenate_audioclips, vfx
)
import numpy as np
import config
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Clip manifest — must match files produced by newsreel_tts.py, in order
# ---------------------------------------------------------------------------

CLIP_MANIFEST = [
    ("00_intro",                        "intro"),
    ("01_core_tech_releases",           "Core Tech Releases"),
    ("02_directions_in_ai_architecture","Directions in AI Architecture"),
    ("03_ai_for_productivity",          "AI For Productivity"),
    ("04_world_impact",                 "World Impact"),
    ("99_outro",                        "outro"),
]

# ---------------------------------------------------------------------------
# Helpers carried forward from original build_video.py
# ---------------------------------------------------------------------------

def load_timestamps(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def find_timestamp(search_text, timestamps):
    """Return start time (seconds) of first occurrence of search_text."""
    full_text = "".join(timestamps["characters"])
    pos = full_text.find(search_text)
    if pos == -1:
        return None
    return timestamps["character_start_times_seconds"][pos]


def make_text_clip(text, font_size, color, duration, position):
    return (
        TextClip(text=text, font=config.FONT, font_size=font_size, color=color)
        .with_position(position)
        .with_duration(duration)
    )


def make_text_clip_with_bg(text, font_size, color, duration, position):
    txt = TextClip(text=text, font=config.FONT, font_size=font_size, color=color)
    w, h = txt.size
    bg = (
        ColorClip(
            size=(w + config.OVERLAY_BG_PADDING * 2, h + config.OVERLAY_BG_PADDING * 2),
            color=config.OVERLAY_BG_COLOR,
        )
        .with_opacity(config.OVERLAY_BG_OPACITY)
        .with_duration(duration)
        .with_position(position)
    )
    txt = txt.with_duration(duration).with_position(position)
    return bg, txt


def build_background_from_timestamps(video_files, change_points, total_duration, section_map=None):
    segments = []
    video_index = 0
    for i, (start_time, label) in enumerate(change_points):
        duration = (
            change_points[i + 1][0] - start_time
            if i + 1 < len(change_points)
            else total_duration - start_time
        )
        if section_map and label in section_map:
            video_file = section_map[label]
        else:
            video_file = video_files[video_index % len(video_files)]
            video_index += 1
        clip = (
            VideoFileClip(video_file)
            .with_effects([vfx.Loop(duration=duration)])
            .resized((1920, 1080))
            .with_start(start_time)
        )
        segments.append(clip)
    return segments


def wrap_sources(sources_text, max_line_length=60):
    items = [s.strip() for s in sources_text.split(",")]
    lines = []
    current_line = ""
    for item in items:
        test_line = current_line + ", " + item if current_line else item
        if len(test_line) > max_line_length and current_line:
            lines.append(current_line + ",")
            current_line = item
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)


def generate_overlay_clips(timestamps, overlays, clips, time_offset=0.0):
    """Generate section and story overlay clips.

    time_offset: absolute start of this clip in the final stitched timeline.
    Section headers are placed at time_offset directly — they are visual only.
    Story titles are looked up in the timestamp data.
    """
    last_section_end = 0

    for kind, text in overlays:
        if kind == "section":
            # Place at clip start — no timestamp lookup needed
            t = time_offset
            bg, txt = make_text_clip_with_bg(
                text=text,
                font_size=config.SECTION_STYLE["font_size"],
                color=config.SECTION_STYLE["color"],
                duration=config.SECTION_STYLE["duration"],
                position=config.SECTION_STYLE["position"],
            )
            clips.append(bg.with_start(t))
            clips.append(txt.with_start(t))
            last_section_end = t + config.SECTION_STYLE["duration"]
            continue

        # Story titles — look up in timestamp data
        t = find_timestamp(text, timestamps)
        if t is None:
            print(f"  WARNING: could not find timestamp for: {text!r}")
            continue

        t = t + time_offset - config.OVERLAY_ANTICIPATION
        phase1_start = max(t, last_section_end)

        phase1 = make_text_clip(
            text=text,
            font_size=config.STORY_STYLE1["font_size"],
            color=config.STORY_STYLE1["color"],
            duration=config.STORY_STYLE1["duration"],
            position=config.STORY_STYLE1["position"],
        ).with_start(phase1_start)
        clips.append(phase1)

        phase2 = make_text_clip(
            text=text,
            font_size=config.STORY_STYLE2["font_size"],
            color=config.STORY_STYLE2["color"],
            duration=config.STORY_STYLE2["duration"],
            position=config.STORY_STYLE2["position"],
        ).with_start(phase1_start + config.STORY_STYLE1["duration"])
        clips.append(phase2)

# ---------------------------------------------------------------------------
# New functions for multi-clip architecture
# ---------------------------------------------------------------------------

def load_stories_json():
    """Load stories.json and return the parsed dict."""
    stories_file = config.ANTHROPIC_JSON_FILE
    with open(stories_file, "r") as f:
        return json.load(f)


def parse_overlays_from_json(data):
    """Build overlay list from stories.json.

    Returns list of (section_name, [(kind, text), ...]) tuples —
    one entry per section clip, in manifest order.
    """
    sections_by_name = {s["section"]: s["stories"] for s in data.get("sections", [])}
    result = []
    for stem, section_label in CLIP_MANIFEST:
        if section_label in ("intro", "outro"):
            result.append((stem, section_label, []))
            continue
        stories = sections_by_name.get(section_label, [])
        overlays = [("section", section_label)]
        for story in stories:
            title = story.get("title", "").strip()
            if title:
                overlays.append(("story", title))
        result.append((stem, section_label, overlays))
    return result


def build_sources_overlay(data, clips, outro_start, total_duration):
    """Pull unique source names from json and show during outro."""
    seen = set()
    source_names = []
    for section in data.get("sections", []):
        for story in section.get("stories", []):
            name = story.get("source_name", "").strip()
            if name and name not in seen:
                seen.add(name)
                source_names.append(name)

    if not source_names:
        return

    sources_str = ", ".join(source_names)
    duration = total_duration - outro_start

    header = make_text_clip(
        "Sources",
        config.SECTION_STYLE["font_size"],
        config.SECTION_STYLE["color"],
        duration,
        ("center", 400),
    ).with_start(outro_start)
    clips.append(header)

    body = make_text_clip(
        wrap_sources(sources_str),
        config.RUNDOWN_STYLE["font_size"],
        config.RUNDOWN_STYLE["color"],
        duration,
        ("center", 480),
    ).with_start(outro_start)
    clips.append(body)


def make_silence(duration: float):
    """Return a silent stereo AudioClip of the given duration in seconds."""
    return AudioClip(
        lambda t: np.zeros((2,)),
        duration=duration,
        fps=44100,
    )


def stitch_audio(clip_manifest, intro_silence=2.0, inter_clip_silence=1.0):
    """Concatenate audio clips in manifest order with surrounding silence.

    Returns (combined_audio, start_times) where start_times maps
    each stem to its absolute start position in the final timeline.
    """
    week = Path(config.WEEK_FOLDER)
    audio_clips = []
    start_times = {}
    cursor = intro_silence

    for stem, label in clip_manifest:
        path = week / f"{stem}.mp3"
        if not path.exists():
            print(f"  WARNING: {path} not found — skipping.")
            continue
        ac = AudioFileClip(str(path))
        start_times[stem] = cursor
        cursor += ac.duration + inter_clip_silence
        audio_clips.append(ac)
        audio_clips.append(make_silence(inter_clip_silence))

    if not audio_clips:
        raise RuntimeError("No audio clips found in week folder.")

    # Prepend intro silence, then clips each followed by inter-clip silence
    combined = concatenate_audioclips([make_silence(intro_silence)] + audio_clips)
    return combined, start_times


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    week = Path(config.WEEK_FOLDER)
    data = load_stories_json()
    clip_sections = parse_overlays_from_json(data)

    print(f"\nBuilding video for: {data.get('week_of', 'unknown')}")
    print(f"Week folder: {config.WEEK_FOLDER}\n")

    # --- Stitch audio ---
    print("Stitching audio clips...")
    audio, start_times = stitch_audio(CLIP_MANIFEST)
    total_duration = audio.duration
    print(f"  Total duration: {total_duration:.1f}s\n")

    # --- Build overlays and change points ---
    clips = []
    change_points = [(0.0, "intro")]
    outro_start = None

    for stem, section_label, overlays in clip_sections:
        clip_start = start_times.get(stem)
        if clip_start is None:
            continue

        # Track section change points for background video switching
        if section_label not in ("intro", "outro"):
            change_points.append((clip_start, section_label))
        elif section_label == "outro":
            outro_start = clip_start
            change_points.append((clip_start, "outro"))

        if not overlays:
            continue

        # Load this clip's timestamps
        ts_path = week / f"{stem}_timestamps.json"
        if not ts_path.exists():
            print(f"  WARNING: timestamps not found for {stem} — skipping overlays.")
            continue
        timestamps = load_timestamps(str(ts_path))

        # Add story-level change points so background video cycles per story
        for kind, text in overlays:
            if kind == "story":
                t = find_timestamp(text, timestamps)
                if t is not None:
                    change_points.append((clip_start + t, text))

        generate_overlay_clips(timestamps, overlays, clips, time_offset=clip_start)

    change_points.sort(key=lambda x: x[0])

    # --- Background video ---
    print("Building background segments...")
    background_clips = build_background_from_timestamps(
        config.BG_VIDEOS, change_points, total_duration,
        section_map=config.SECTION_VIDEOS,
    )

    # --- Opening title card ---
    opening = make_text_clip(
        text=config.OPENING_TITLE,
        font_size=config.OPENING_STYLE["font_size"],
        color=config.OPENING_STYLE["color"],
        duration=config.OPENING_STYLE["duration"],
        position=config.OPENING_STYLE["position"],
    ).with_start(0)

    all_clips = background_clips + [opening] + clips

    # --- Sources overlay during outro ---
    if outro_start is not None:
        build_sources_overlay(data, all_clips, outro_start, total_duration)

    # --- Composite and write ---
    print("Compositing final video...")
    final = CompositeVideoClip(all_clips)
    final = final.with_audio(audio)
    final.write_videofile(config.OUTPUT_VIDEO, fps=24, audio_codec=config.AUDIO_CODEC)
    print(f"\nDone! Saved to {config.OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()

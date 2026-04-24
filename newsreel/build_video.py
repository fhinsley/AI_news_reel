#!/usr/bin/env python3
"""Build the final newsreel video from multi-voice audio clips and json.

Pipeline:
  1. Load json — source of truth for overlays and sources
  2. Stitch the sequenced audio clips (00-99) into one timeline
  3. Build overlay list (section headers + story titles) with absolute timestamps
  4. Build background video segments keyed to section change points
  5. Composite everything and write News.mp4
"""

from importlib.resources import path

from matplotlib.pyplot import stem

from moviepy import (
    AudioClip, AudioFileClip, ColorClip, CompositeAudioClip, CompositeVideoClip,
    TextClip, VideoFileClip, concatenate_audioclips, vfx
)
from moviepy.audio.fx import MultiplyVolume, AudioFadeOut, AudioFadeIn
import numpy as np
import config
import json
from pathlib import Path

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


def make_lower_third(title: str, source: str, t_start: float, clips: list,
                     duration: float | None = None) -> None:
    """Broadcast-style lower third: title line + source subtext on a dark bar.

    Composited as three layers: background bar, title text, source text.
    All three share the same start time and duration.
    Duration defaults to LOWER_THIRD_DURATION if not specified.
    """
    duration = duration if duration is not None else config.LOWER_THIRD_DURATION
    y        = config.LOWER_THIRD_Y

    # Measure title text width to size the background bar
    title_clip = TextClip(
        text=title,
        font=config.FONT,
        font_size=config.LOWER_THIRD_TITLE_STYLE["font_size"],
        color=config.LOWER_THIRD_TITLE_STYLE["color"],
    )
    bar_w = min(title_clip.size[0] + config.OVERLAY_BG_PADDING * 4, 1800)
    bar_h = 70  # fits two lines of text

    bg = (
        ColorClip(size=(bar_w, bar_h), color=config.LOWER_THIRD_BG_COLOR)
        .with_opacity(config.LOWER_THIRD_BG_OPACITY)
        .with_duration(duration)
        .with_start(t_start)
        .with_position((60, y))
    )

    title_txt = (
        TextClip(
            text=title,
            font=config.FONT,
            font_size=config.LOWER_THIRD_TITLE_STYLE["font_size"],
            color=config.LOWER_THIRD_TITLE_STYLE["color"],
        )
        .with_duration(duration)
        .with_start(t_start)
        .with_position((80, y + 6))
    )

    source_txt = (
        TextClip(
            text=source,
            font=config.FONT,
            font_size=config.LOWER_THIRD_SOURCE_STYLE["font_size"],
            color=config.LOWER_THIRD_SOURCE_STYLE["color"],
        )
        .with_duration(duration)
        .with_start(t_start)
        .with_position((80, y + 38))
    )

    clips.extend([bg, title_txt, source_txt])


def generate_overlay_clips(timestamps, overlays, clips, time_offset=0.0):
    """Generate section and story overlay clips.

    time_offset: absolute start of this clip in the final stitched timeline.
    Section headers are placed at time_offset directly — they are visual only.
    Story titles are looked up in the timestamp data.
    """
    last_section_end = 0

    for idx, item in enumerate(overlays):
        kind = item[0]

        if kind == "section":
            text = item[1]
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

        # Story: item = ("story", display_title, spoken_title, source_name)
        display_title = item[1]
        spoken_title  = item[2]
        source_name   = item[3] if len(item) > 3 else ""

        # Use spoken title to find timestamp, display title for overlay text
        t = find_timestamp(spoken_title, timestamps)
        if t is None:
            print(f"  WARNING: could not find timestamp for: {spoken_title!r}")
            continue

        t = t + time_offset - config.OVERLAY_ANTICIPATION
        phase1_start = max(t, last_section_end)

        # Phase1 — announcement card, styled to match chyron aesthetic
        phase1_bg, phase1_txt = make_text_clip_with_bg(
            text=display_title,
            font_size=config.LOWER_THIRD_TITLE_STYLE["font_size"] + 8,
            color=config.LOWER_THIRD_TITLE_STYLE["color"],
            duration=config.SECTION_STYLE["duration"],
            position="center",
        )
        # Override bg color to match chyron
        phase1_bg = (
            ColorClip(
                size=phase1_bg.size,
                color=config.LOWER_THIRD_BG_COLOR,
            )
            .with_opacity(config.LOWER_THIRD_BG_OPACITY)
            .with_duration(config.SECTION_STYLE["duration"])
            .with_position("center")
        )
        clips.append(phase1_bg.with_start(phase1_start))
        clips.append(phase1_txt.with_start(phase1_start))

        # Lower third chyron — lasts from after phase1 until the next story starts.
        # Look ahead in overlays to find the next story timestamp.
        if source_name:
            chyron_start = phase1_start + config.SECTION_STYLE["duration"]
            chyron_end   = None
            for next_item in overlays[idx + 1:]:
                if next_item[0] == "story":
                    next_t = find_timestamp(next_item[2], timestamps)
                    if next_t is not None:
                        chyron_end = next_t + time_offset - config.OVERLAY_ANTICIPATION
                    break

            make_lower_third(display_title, source_name, chyron_start, clips,
                             duration=config.LOWER_THIRD_DURATION)

# ---------------------------------------------------------------------------
# New functions for multi-clip architecture
# ---------------------------------------------------------------------------

def load_stories_json():
    """Load stories.json and return the parsed dict."""
    # stories_file = config.ANTHROPIC_SHORT_JSON_FILE
    stories_file = config.ANTHROPIC_JSON_FILE
    with open(stories_file, "r") as f:
        return json.load(f)


def to_sentence_case(text: str) -> str:
    """Match the case transformation applied in newsreel_tts.py.
    Ensures timestamp lookups find the title as it was actually spoken.
    """
    if not text:
        return text
    return text[0].upper() + text[1:].lower()


def parse_overlays_from_json(data):
    """Build overlay list from stories.json.

    Returns list of (section_name, [(kind, text), ...]) tuples —
    one entry per section clip, in manifest order.
    Story titles are converted to sentence case to match the spoken audio.
    """
    sections_by_name = {s["section"]: s["stories"] for s in data.get("sections", [])}
    result = []
    for stem, section_label in config.VIDEO_CLIP_MANIFEST:
        if section_label in ("intro", "outro"):
            result.append((stem, section_label, []))
            continue
        stories = sections_by_name.get(section_label, [])
        overlays = [("section", section_label)]
        for story in stories:
            display_title = story.get("title", "").strip()
            spoken_title  = to_sentence_case(display_title)
            source_name   = story.get("source_name", "").strip()
            if display_title:
                overlays.append(("story", display_title, spoken_title, source_name))
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

    # Header and body with dark background matching chyron style
    hdr_bg, hdr_txt = make_text_clip_with_bg(
        "Sources",
        config.SECTION_STYLE["font_size"],
        config.SECTION_STYLE["color"],
        duration,
        ("center", 400),
    )
    hdr_bg = (
        ColorClip(size=hdr_bg.size, color=config.LOWER_THIRD_BG_COLOR)
        .with_opacity(config.LOWER_THIRD_BG_OPACITY)
        .with_duration(duration)
        .with_position(("center", 400))
    )
    clips.append(hdr_bg.with_start(outro_start))
    clips.append(hdr_txt.with_start(outro_start))

    body_bg, body_txt = make_text_clip_with_bg(
        wrap_sources(sources_str),
        config.RUNDOWN_STYLE["font_size"],
        config.RUNDOWN_STYLE["color"],
        duration,
        ("center", 480),
    )
    body_bg = (
        ColorClip(size=body_bg.size, color=config.LOWER_THIRD_BG_COLOR)
        .with_opacity(config.LOWER_THIRD_BG_OPACITY)
        .with_duration(duration)
        .with_position(("center", 480))
    )
    clips.append(body_bg.with_start(outro_start))
    clips.append(body_txt.with_start(outro_start))


def make_silence(duration: float):
    """Return a silent stereo AudioClip of the given duration in seconds."""
    return AudioClip(
        lambda t: np.zeros((2,)),
        duration=duration,
        fps=44100,
    )


def stitch_audio(clip_manifest = config.VIDEO_CLIP_MANIFEST, intro_silence=config.VIDEO_INTRO_SILENCE, inter_clip_silence=config.VIDEO_INTER_CLIP_SILENCE):
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
        
        boost = config.VOICE_VOLUME_BOOST.get(stem)
        if boost:
            ac = ac.with_effects([MultiplyVolume(boost)])
        
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
# Music
# ---------------------------------------------------------------------------

def _make_bed_segment(bed_raw: "AudioFileClip", t_start: float, duration: float, volume: float) -> "AudioFileClip":
    """Return a bed clip of exactly `duration` seconds placed at t_start.
    Loops the source if needed, trims to fit.
    """
    loops_needed = int(duration / bed_raw.duration) + 2
    looped = concatenate_audioclips([bed_raw] * loops_needed)
    return (
        looped
        .subclipped(0, duration)
        .with_start(t_start)
        .with_effects([MultiplyVolume(volume)])
    )


def build_music_track(total_duration: float, narration_start: float,
                      start_times: dict, outro_start: float | None,
                      clip_sections: list) -> "CompositeAudioClip | None":
    """Build the full music track:

    - Sting: t=0 full volume, ducks to bed volume as anchor intro starts,
             plays through anchor intro then stops.
    - Bed:   plays during each section and its stories, stops between clips,
             restarts at each new section clip start.
    - Outro sting: plays from outro_start to end at bed volume.
    """
    sting_path = Path(config.MUSIC_STING_FILE)
    tracks     = []

    # --- Sting: intro ---
    if sting_path.exists():
        intro_clip_start = start_times.get("00_intro", narration_start)
        # Sting plays from t=0 at full volume, then ducks at intro start,
        # fades out by end of intro clip duration
        sting_raw = AudioFileClip(str(sting_path))
        sting_dur = config.MUSIC_STING_DURATION

        # Full-volume portion: t=0 to narration_start
        if narration_start > 0:
            sting_loud = (
                sting_raw
                .subclipped(0, min(narration_start, sting_raw.duration))
                .with_effects([MultiplyVolume(config.MUSIC_STING_VOLUME)])
                .with_start(0)
            )
            tracks.append(sting_loud)

        # Ducked portion: narration_start to sting_dur, fades out
        duck_start = narration_start
        duck_end   = min(sting_dur, sting_raw.duration)
        if duck_end > duck_start:
            sting_duck = (
                sting_raw
                .subclipped(duck_start, duck_end)
                .with_effects([MultiplyVolume(config.MUSIC_BED_VOLUME)])
                .with_effects([AudioFadeOut(config.MUSIC_STING_FADE_OUT)])
                .with_start(duck_start)
            )
            tracks.append(sting_duck)
        print(f"  Sting (intro): {sting_path.name} (full to {narration_start:.1f}s, ducked to {duck_end:.1f}s)")
    else:
        print(f"  WARNING: sting not found: {sting_path}")

    # --- Bed: one segment per section clip, each with its own music file ---
    # section_stems preserves manifest order for correct duration calculation
    section_stems = [
        stem for stem, label, _ in clip_sections
        if label not in ("intro", "outro")
    ]
    for i, stem in enumerate(section_stems):
        seg_cfg = config.MUSIC_SEGMENTS.get(stem)
        bed_volume = seg_cfg.get("volume") if seg_cfg else config.MUSIC_BED_VOLUME
        bed_file = seg_cfg.get("file") if seg_cfg else None
        if not bed_file:
            print(f"  WARNING: no bed file configured for {stem} — skipping.")
            continue
        bed_path = Path(bed_file)
        if not bed_path.exists():
            print(f"  WARNING: bed not found for {stem}: {bed_path}")
            continue

        t_start = start_times.get(stem)
        if t_start is None:
            continue

        # Duration: this stem start to next stem start (or outro/end)
        if i + 1 < len(section_stems):
            t_end = start_times.get(section_stems[i + 1], total_duration)
        else:
            t_end = outro_start if outro_start is not None else total_duration

        duration = t_end - t_start
        if duration <= 0:
            continue

        bed_raw = AudioFileClip(str(bed_path))
        seg = _make_bed_segment(bed_raw, t_start, duration, volume=bed_volume)
        tracks.append(seg)
        print(f"  Bed segment: {stem} ({bed_path.name}) {t_start:.1f}s → {t_end:.1f}s ({duration:.1f}s)")

    # --- Sting: outro ---
    if sting_path.exists() and outro_start is not None:
        outro_dur = total_duration - outro_start
        sting_outro = (
            AudioFileClip(str(sting_path))
            .subclipped(0, min(outro_dur, AudioFileClip(str(sting_path)).duration))
            .with_effects([MultiplyVolume(config.MUSIC_OUTRO_VOLUME)])
            .with_effects([AudioFadeIn(1.0)])
            .with_start(outro_start)
        )
        tracks.append(sting_outro)
        print(f"  Sting (outro): starts at {outro_start:.1f}s")

    if not tracks:
        return None

    return CompositeAudioClip(tracks)


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
    audio, start_times = stitch_audio()
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
        for item in overlays:
            if item[0] == "story":
                spoken_title = item[2]
                t = find_timestamp(spoken_title, timestamps)
                if t is not None:
                    change_points.append((clip_start + t, spoken_title))

        generate_overlay_clips(timestamps, overlays, clips, time_offset=clip_start)

    change_points.sort(key=lambda x: x[0])

    # --- Background video ---
    print("Building background segments...")
    background_clips = build_background_from_timestamps(
        config.BG_VIDEOS, change_points, total_duration,
        section_map=config.SECTION_VIDEOS,
    )

    # --- Opening title card — dark background matching chyron style ---
    opening_bg, opening_txt = make_text_clip_with_bg(
        text=config.OPENING_TITLE,
        font_size=config.OPENING_STYLE["font_size"],
        color=config.OPENING_STYLE["color"],
        duration=config.OPENING_STYLE["duration"],
        position=config.OPENING_STYLE["position"],
    )
    opening_bg = (
        ColorClip(
            size=opening_bg.size,
            color=config.LOWER_THIRD_BG_COLOR,
        )
        .with_opacity(config.LOWER_THIRD_BG_OPACITY)
        .with_duration(config.OPENING_STYLE["duration"])
        .with_position(config.OPENING_STYLE["position"])
    )
    opening_bg  = opening_bg.with_start(0)
    opening_txt = opening_txt.with_start(0)

    all_clips = background_clips + [opening_bg, opening_txt] + clips

    # --- Sources overlay during outro ---
    if outro_start is not None:
        build_sources_overlay(data, all_clips, outro_start, total_duration)

    # --- Mix music with narration ---
    print("Building music track...")
    narration_start = start_times.get("00_intro", config.VIDEO_INTRO_SILENCE)
    music = build_music_track(
        total_duration  = total_duration,
        narration_start = narration_start,
        start_times     = start_times,
        outro_start     = outro_start,
        clip_sections   = clip_sections,
    )
    if music is not None:
        final_audio = CompositeAudioClip([audio, music])
        final_audio = final_audio.with_duration(total_duration)
    else:
        final_audio = audio

    # --- Composite and write ---
    print("Compositing final video...")
    final = CompositeVideoClip(all_clips)
    final = final.with_audio(final_audio)
    final.write_videofile(config.OUTPUT_VIDEO, fps=24, audio_codec=config.AUDIO_CODEC)
    print(f"\nDone! Saved to {config.OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()

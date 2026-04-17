#!/usr/bin/env python3
"""Build the Two-Sides debate video from audio clips and story.json.

Structural mirror of scripts/build_video.py.

Assembly order:
  00_anchor_intro      — anchor frames the proposition
  01_opener            — opener's affirmative argument
  [framing card]       — silent visual: the proposition statement
  02_responder         — responder's rebuttal + argument
  03_opener_rebuttal   — opener's closing rebuttal
  04_anchor_outro      — anchor summarizes and closes
"""

import json
from pathlib import Path

import numpy as np
from moviepy import (
    AudioClip, AudioFileClip, ColorClip, CompositeVideoClip,
    TextClip, VideoFileClip, concatenate_audioclips, vfx,
)

import config

# ---------------------------------------------------------------------------
# Helpers — direct ports of build_video.py utilities
# ---------------------------------------------------------------------------

def load_timestamps(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def find_timestamp(search_text, timestamps):
    full_text = "".join(timestamps["characters"])
    pos = full_text.find(search_text)
    if pos == -1:
        return None
    return timestamps["character_start_times_seconds"][pos]


def make_silence(duration: float):
    """Silent stereo AudioClip — identical to build_video.py."""
    return AudioClip(
        lambda t: np.zeros((2,)),
        duration=duration,
        fps=44100,
    )


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


# ---------------------------------------------------------------------------
# Audio stitching
# ---------------------------------------------------------------------------

def stitch_audio():
    """Concatenate debate audio clips with surrounding silence.

    The framing card (silent visual beat before the responder) is injected
    here as a silence block so the video timeline stays accurate.

    Returns (combined_audio, start_times).
    """
    week        = Path(config.WEEK_FOLDER)
    audio_clips = []
    start_times = {}
    cursor      = config.VIDEO_INTRO_SILENCE

    for stem, label in config.DEBATE_CLIP_MANIFEST:
        path = week / f"{stem}.mp3"
        if not path.exists():
            print(f"  WARNING: {path} not found — skipping.")
            continue

        # Insert framing card silence before the responder's turn
        if stem == "02_responder":
            start_times["__framing_card__"] = cursor
            cursor += config.FRAMING_CARD_DURATION + config.VIDEO_INTER_CLIP_SILENCE
            audio_clips.append(make_silence(config.FRAMING_CARD_DURATION))
            audio_clips.append(make_silence(config.VIDEO_INTER_CLIP_SILENCE))

        ac = AudioFileClip(str(path))
        start_times[stem] = cursor
        cursor += ac.duration + config.VIDEO_INTER_CLIP_SILENCE
        audio_clips.append(ac)
        audio_clips.append(make_silence(config.VIDEO_INTER_CLIP_SILENCE))

    if not audio_clips:
        raise RuntimeError("No audio clips found in week folder.")

    # Prepend intro silence once — cursor was already initialised to VIDEO_INTRO_SILENCE
    # so start_times are correct.  Do NOT add it again to audio_clips.
    combined = concatenate_audioclips(
        [make_silence(config.VIDEO_INTRO_SILENCE)] + audio_clips
    )
    return combined, start_times


# ---------------------------------------------------------------------------
# Background video — tinted flag
# ---------------------------------------------------------------------------

def _load_looped_video(video_path: str, duration: float, start_time: float):
    """Load a video file, loop it to exactly `duration` seconds, resize to
    1280x720, clamp its duration, and set its start in the parent timeline.

    Using .with_duration() after .with_effects([Loop(...)]) ensures MoviePy
    never extends the clip beyond the segment boundary — which is the root
    cause of black-screen gaps and total-duration bloat.
    """
    clip = (
        VideoFileClip(str(video_path))
        .with_effects([vfx.Loop(duration=duration)])
        .resized((1280, 720))
        .with_duration(duration)        # hard clamp — Loop alone does not truncate
        .with_start(start_time)
    )
    return clip


def build_background(change_points, total_duration):
    """Build background segments from per-side flag videos, tinted per side.

    left   → LEFT_FLAG_VIDEO  + blue tint
    right  → RIGHT_FLAG_VIDEO + red tint
    anchor → SECTION_VIDEOS["anchor"] + grey tint (no flag)

    Falls back to SECTION_VIDEOS for any side whose flag file is not found.

    FIX — compositor start timing:
    Both `base` and `overlay` receive .with_start(start_time) BEFORE being
    passed to CompositeVideoClip.  The composite itself is NOT given an
    additional .with_start() call — doing so would double-shift the clips
    and produce black frames between segments.
    """
    flag_video_map = {
        "left":  config.LEFT_FLAG_VIDEO,
        "right": config.RIGHT_FLAG_VIDEO,
    }

    segments = []
    for i, (start_time, label) in enumerate(change_points):
        duration = (
            change_points[i + 1][0] - start_time
            if i + 1 < len(change_points)
            else total_duration - start_time
        )

        # Safety: never produce a zero- or negative-duration segment
        if duration <= 0:
            print(f"  WARNING: skipping zero-duration background segment at t={start_time:.2f}s ({label})")
            continue

        # Resolve flag path for this side — anchor uses SECTION_VIDEOS
        flag_path = flag_video_map.get(label)
        use_flag  = flag_path is not None and Path(flag_path).exists()

        if flag_path is not None and not use_flag and label in ("left", "right"):
            print(f"  WARNING: flag video not found for '{label}': {flag_path}")
            print("           Falling back to SECTION_VIDEOS.")

        if use_flag:
            base = _load_looped_video(flag_path, duration, start_time)

            tint_cfg = config.FLAG_TINTS.get(label, config.FLAG_TINTS["anchor"])
            overlay  = (
                ColorClip(size=(1280, 720), color=tint_cfg["color"])
                .with_opacity(tint_cfg["opacity"])
                .with_duration(duration)
                .with_start(start_time)         # set on child, NOT on composite
            )

            # Both children already carry start_time — do NOT call .with_start()
            # on the CompositeVideoClip or MoviePy will double-shift them.
            segment = CompositeVideoClip([base, overlay], size=(1280, 720))

        else:
            video_file = config.SECTION_VIDEOS.get(label, config.SECTION_VIDEOS["anchor"])
            segment = _load_looped_video(video_file, duration, start_time)

        segments.append(segment)

    return segments


# ---------------------------------------------------------------------------
# Overlay generators
# ---------------------------------------------------------------------------

def add_side_label(clips, label_text, t_start):
    s = config.SIDE_LABEL_STYLE
    bg, txt = make_text_clip_with_bg(
        text=label_text,
        font_size=s["font_size"],
        color=s["color"],
        duration=s["duration"],
        position=s["position"],
    )
    clips.append(bg.with_start(t_start))
    clips.append(txt.with_start(t_start))


def add_proposition_overlay(clips, proposition, t_start):
    """Anchor intro: show the debate proposition as a lower-third style overlay."""
    s = config.PROPOSITION_STYLE
    bg, txt = make_text_clip_with_bg(
        text=f'"{proposition}"',
        font_size=s["font_size"],
        color=s["color"],
        duration=s["duration"],
        position=("center", 580),   # lower third
    )
    clips.append(bg.with_start(t_start + 2.0))   # 2s after anchor starts speaking
    clips.append(txt.with_start(t_start + 2.0))


def add_framing_card(clips, proposition, t_start):
    """Silent visual card between opener and responder showing the proposition."""
    duration = config.FRAMING_CARD_DURATION

    panel = (
        ColorClip(size=(1280, 720), color=(20, 20, 30))
        .with_duration(duration)
        .with_start(t_start)
    )
    clips.append(panel)

    header = make_text_clip(
        text="THE PROPOSITION",
        font_size=36,
        color="gray",
        duration=duration,
        position=("center", 380),
    ).with_start(t_start)
    clips.append(header)

    body = make_text_clip(
        text=f'"{proposition}"',
        font_size=config.FRAMING_CARD_STYLE["font_size"],
        color=config.FRAMING_CARD_STYLE["color"],
        duration=duration,
        position=("center", 460),
    ).with_start(t_start)
    clips.append(body)

    # Left/right colour bars at bottom edge — 720p positions
    left_bar = (
        ColorClip(size=(638, 6), color=config.LEFT_COLOR)
        .with_duration(duration)
        .with_start(t_start)
        .with_position((0, 712))
    )
    right_bar = (
        ColorClip(size=(638, 6), color=config.RIGHT_COLOR)
        .with_duration(duration)
        .with_start(t_start)
        .with_position((642, 712))
    )
    clips.append(left_bar)
    clips.append(right_bar)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    week = Path(config.WEEK_FOLDER)

    with open(config.DEBATE_JSON_FILE, "r") as f:
        data = json.load(f)

    proposition    = data.get("proposition", "")
    opener_side    = data.get("opener_side",    config.DEBATE_OPENER)
    responder_side = data.get("responder_side", "right" if opener_side == "left" else "left")
    debate         = data["debate"]

    print(f"\nBuilding debate video")
    print(f"Proposition: {proposition}")
    print(f"Opener: {opener_side}  |  Responder: {responder_side}")
    print(f"Week folder: {config.WEEK_FOLDER}\n")

    # --- Stitch audio ---
    print("Stitching audio clips...")
    audio, start_times = stitch_audio()
    total_duration = audio.duration
    print(f"  Total duration: {total_duration:.1f}s\n")

    clips         = []
    change_points = [(0.0, "anchor")]

    # --- Anchor intro ---
    t_intro = start_times.get("00_anchor_intro", config.VIDEO_INTRO_SILENCE)
    add_proposition_overlay(clips, proposition, t_intro)

    # --- Opener ---
    t_opener = start_times.get("01_opener")
    if t_opener is not None:
        change_points.append((t_opener, opener_side))
        opener_label = debate["opener_argument"].get("label", f"{opener_side.capitalize()} Perspective")
        add_side_label(clips, opener_label.upper(), t_opener)

    # --- Framing card (silent beat before responder) ---
    t_card = start_times.get("__framing_card__")
    if t_card is not None:
        change_points.append((t_card, "anchor"))
        add_framing_card(clips, proposition, t_card)

    # --- Responder ---
    t_responder = start_times.get("02_responder")
    if t_responder is not None:
        change_points.append((t_responder, responder_side))
        responder_label = debate["responder_turn"].get("label", f"{responder_side.capitalize()} Perspective")
        add_side_label(clips, responder_label.upper(), t_responder)

    # --- Opener rebuttal ---
    t_rebuttal = start_times.get("03_opener_rebuttal")
    if t_rebuttal is not None:
        change_points.append((t_rebuttal, opener_side))
        add_side_label(clips, f"{opener_side.upper()} REBUTTAL", t_rebuttal)

    # --- Anchor outro ---
    t_outro = start_times.get("04_anchor_outro")
    if t_outro is not None:
        change_points.append((t_outro, "anchor"))

    change_points.sort(key=lambda x: x[0])

    # --- Background video ---
    print("Building background segments...")
    for t, label in change_points:
        print(f"  t={t:.1f}s  →  {label}")
    background_clips = build_background(change_points, total_duration)

    all_clips = background_clips + clips

    # --- Composite and write ---
    print("\nCompositing final video...")
    final = CompositeVideoClip(all_clips, size=(1280, 720))
    final = final.with_audio(audio)
    final.write_videofile(config.OUTPUT_VIDEO, fps=24, audio_codec=config.AUDIO_CODEC)
    print(f"\nDone! Saved to {config.OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()

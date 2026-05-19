"""
build_video.py — NewsCrew compositor

Reads a shot_plan.json produced by plan_shots.py (or hand-authored for testing)
and composites the final episode MP4 from:

    Layer 1  virtual set background image (SET_BACKGROUND_IMAGE)
    Layer 2  B-roll clip  — either wall-screen size or full-frame
    Layer 3  anchor clip(s) — A solo, B solo, or both (wide two-shot)
    Layer 4  PiP anchor insert — small anchor box over full-frame B-roll
    Layer 5  lower-third overlay — headline + source slug

Shot modes (set in each shot plan segment):
    "wide"      Both anchors visible behind desk, B-roll on wall screen
    "solo_a"    Anchor A cropped/enlarged, B dimmed, B-roll on wall screen
    "solo_b"    Anchor B cropped/enlarged, A dimmed, B-roll on wall screen
    "broll"     B-roll fills frame; PiP anchor box in corner

Usage:
    python build_video.py                          # uses SHOT_PLAN_JSON from config
    python build_video.py --plan path/to/plan.json
    python build_video.py --dry-run                # print segment table, no render

Shot plan JSON schema:
    {
      "episode": "050926_Episode",
      "segments": [
        {
          "segment_id":       "unique string matching anchor_jobs.json key",
          "shot_mode":        "wide" | "solo_a" | "solo_b" | "broll",
          "anchor_id":        "Annie" | "Vesperi" | ... (speaking anchor),
          "anchor_clip":      "path/to/anchor_clips/segment_id.mp4",
          "broll_clip":       "path/to/broll/clip.mp4" | null,
          "lower_third_headline": "Story headline text" | null,
          "lower_third_source":   "Source Name" | null,
          "transition_in":    "cut" | "crossfade",   // default "cut"
          "transition_out":   "cut" | "crossfade"    // default "cut"
        },
        ...
      ]
    }

Notes:
    - Segments without an anchor_clip are skipped with a warning (not yet rendered).
    - Segments without a broll_clip fall back to the ambient background loop.
    - The desk mask is painted into SET_BACKGROUND_IMAGE — anchor clips are cropped
      at ANCHOR_CROP_BOTTOM pixels from the bottom to simulate sitting behind the desk.
    - All geometry constants live in config.py under "# Video / compositor".
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    ColorClip,
    CompositeVideoClip,
    CompositeAudioClip,
    TextClip,
    concatenate_videoclips,
    concatenate_audioclips,
)
from moviepy.video.fx import Resize, FadeIn, FadeOut, CrossFadeIn, CrossFadeOut, Crop
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, AudioLoop

from config import (
    EPISODE_DIR,
    ANCHOR_JOBS_JSON,
    OUTPUT_VIDEO,
    VIDEO_RESOLUTION,
    VIDEO_FPS,
    ANCHORS,
    SET_BACKGROUND_IMAGE,
    ANCHOR_A_FRAME,
    ANCHOR_B_FRAME,
    ANCHOR_A_SOLOFRAME,
    ANCHOR_B_SOLOFRAME,
    ANCHOR_CROP_BOTTOM_DEFAULT,
    SOLO_A_LOWER_THIRD_FRAME,
    SOLO_B_LOWER_THIRD_FRAME,
    WALL_SCREEN_FRAME,
    PIP_ANCHOR_ID,
    LOWER_THIRD_FRAME,
    LOWER_THIRD_BG_COLOR,
    LOWER_THIRD_HEADLINE_COLOR,
    LOWER_THIRD_SOURCE_COLOR,
    LOWER_THIRD_FONT,
    LOWER_THIRD_HEADLINE_SIZE,
    LOWER_THIRD_SOURCE_SIZE,
    CROSSFADE_DURATION,
    SHOT_PLAN_JSON,
    PROJECT_ROOT,
    MUSIC_PATH,
    INTRO_AUDIO_CLIP,
    CLOSE_AUDIO_CLIP,
    INTRO_MUSIC_LEAD,
    MUSIC_BED_VOLUME,
    MUSIC_FULL_VOLUME,
    CLOSE_WIDE_HOLD,
    CLOSE_CREDITS_DURATION,
)

W, H = VIDEO_RESOLUTION
ANCHOR_LOOKUP = {a["id"]: a for a in ANCHORS}


def _anchor_crop(anchor_id: str) -> int:
    """Return crop_bottom for an anchor from its schema entry, with fallback."""
    anchor = ANCHOR_LOOKUP.get(anchor_id)
    if anchor:
        return anchor.get("crop_bottom", ANCHOR_CROP_BOTTOM_DEFAULT)
    return ANCHOR_CROP_BOTTOM_DEFAULT

# HeyGen clip canvas dimensions — used for placeholder aspect-ratio estimation
CONTENT_W = 708
CONTENT_H = 896

# File extensions treated as still images rather than video clips
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _frame_to_pos(frame: tuple) -> tuple:
    """Return (x, y) position from frame tuple (works for both 3- and 4-value frames)."""
    return (frame[0], frame[1])


def _frame_size(frame: tuple) -> tuple:
    """Return (w, h) from (x, y, w, h) frame tuple. Only valid for fixed-size frames."""
    return (frame[2], frame[3])


# ── Clip loaders ───────────────────────────────────────────────────────────────

def load_anchor_clip(clip_path: str | Path, target_duration: float | None = None) -> VideoFileClip:
    """
    Load an anchor MP4, strip audio (HeyGen clips carry voice audio),
    and optionally trim/extend to target_duration.
    """
    clip = VideoFileClip(str(clip_path))
    if target_duration is not None and clip.duration > target_duration:
        clip = clip.with_end(target_duration)
    return clip


def load_broll_clip(clip_path: str | Path, duration: float) -> VideoFileClip | ImageClip:
    """
    Load a B-roll asset and fit it to exactly duration seconds.

    Still images (.jpg, .jpeg, .png, .webp) are loaded as ImageClip and held
    for the full duration — this is the expected output of fetch_visuals.py.

    Video files are muted, then looped or trimmed to duration.
    """
    p = Path(clip_path)
    if p.suffix.lower() in IMAGE_EXTENSIONS:
        return ImageClip(str(p)).with_duration(duration)

    # Video path
    clip = VideoFileClip(str(p)).with_volume_scaled(0)
    if clip.duration < duration:
        from moviepy.video.fx import Loop
        clip = clip.with_effects([Loop(duration=duration)])
    else:
        clip = clip.with_end(duration)
    return clip


def make_fallback_broll(duration: float, size: tuple) -> ColorClip:
    """Solid dark slate fallback when no B-roll clip is available."""
    return ColorClip(size=size, color=[18, 22, 30], duration=duration)


# ── Anchor clip compositing ────────────────────────────────────────────────────

# Green screen color used in HeyGen rendering — must match what was set in HeyGen
CHROMA_KEY_COLOR = np.array([0, 255, 0], dtype=np.float32)   # #00FF00
CHROMA_TOLERANCE = 170   # increase if green fringe remains, decrease if spill bleeds in


def remove_green_screen(clip: VideoFileClip) -> VideoFileClip:
    """
    Replace green screen pixels with transparency using a per-frame numpy mask.
    Uses MoviePy 2.x image_transform API.
    """
    def chroma_key_frame(frame):
        """Transform a single RGB frame into RGBA with green keyed out."""
        f = frame.astype(np.float32)
        diff  = np.linalg.norm(f - CHROMA_KEY_COLOR, axis=2)
        alpha = np.where(diff < CHROMA_TOLERANCE, 0, 255).astype(np.uint8)
        return np.dstack([frame, alpha])

    return clip.image_transform(chroma_key_frame)


def detect_content_box(clip: VideoFileClip) -> tuple:
    """
    Sample the middle frame and return (x1, y1, x2, y2) bounding box
    of non-green content. Used to crop transparent padding after keying
    so that position (fx, fy) places the top of the visible person,
    not the top of the original clip canvas.
    """
    frame = clip.get_frame(clip.duration / 2).astype(np.float32)
    rgb   = frame[:, :, :3]   # drop alpha channel if present
    diff  = np.linalg.norm(rgb - CHROMA_KEY_COLOR, axis=2)
    mask  = diff >= CHROMA_TOLERANCE
    rows  = np.any(mask, axis=1)
    cols  = np.any(mask, axis=0)
    if not rows.any():
        return (0, 0, clip.size[0], clip.size[1])
    y1 = int(np.argmax(rows))
    y2 = int(len(rows) - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(len(cols) - np.argmax(cols[::-1]))
    margin = 6
    return (
        max(0, x1 - margin),
        max(0, y1 - margin),
        min(clip.size[0], x2 + margin),
        min(clip.size[1], y2 + margin),
    )


def _resize_and_crop_anchor(clip: VideoFileClip, frame: tuple, crop_bottom: int | None = None) -> VideoFileClip:
    """
    1. Remove green screen background
    2. Crop transparent padding so (fx, fy) aligns to top of visible person
    3. Resize to frame width, preserving aspect ratio
    4. Crop bottom to simulate desk occlusion.
       Uses crop_bottom if provided, otherwise ANCHOR_CROP_BOTTOM_DEFAULT.
    5. Position at frame (x, y)
    """
    fx, fy, fw = frame
    effective_crop = crop_bottom if crop_bottom is not None else ANCHOR_CROP_BOTTOM_DEFAULT

    # Step 1 — remove green screen
    clip = remove_green_screen(clip)

    # Step 2 — crop transparent padding
    x1, y1, x2, y2 = detect_content_box(clip)
    clip = clip.with_effects([Crop(x1=x1, y1=y1, x2=x2, y2=y2)])

    # Step 3 — scale to frame width, aspect ratio preserved
    clip = clip.with_effects([Resize(width=fw)])

    # Step 4 — crop bottom for desk occlusion
    if effective_crop > 0:
        clip_h = int(clip.size[1])
        crop_h = max(1, clip_h - effective_crop)
        clip = clip.with_effects([Crop(y1=0, y2=crop_h)])

    # Step 5 — place at frame position
    return clip.with_position((fx, fy))


def _dim_anchor(clip: VideoFileClip) -> VideoFileClip:
    """Reduce opacity for the non-speaking anchor in solo shots."""
    return clip.with_opacity(0.35)


def _find_standin_clip(inactive_anchor_id: str, all_segments: list) -> str | None:
    """
    Scan all_segments for any clip that belongs to inactive_anchor_id.
    Returns the first valid clip path found, or None.

    Looks up the seat for inactive_anchor_id in ANCHOR_LOOKUP to confirm
    we're pulling from the right anchor, not just any available clip.
    """
    for seg in all_segments:
        if seg.get("anchor_id") == inactive_anchor_id:
            p = seg.get("anchor_clip")
            if p and Path(p).exists():
                return p
    return None


def _make_standin(
    frame: tuple,
    duration: float,
    clip_path: str | None,
    dim: bool = True,
    crop_bottom: int | None = None,
    anchor_id: str | None = None,
) -> VideoFileClip | ColorClip:
    """
    Build the frozen stand-in for the inactive anchor seat.

    Priority:
      1. Rest image — assets/rest_frames/<avatar_id>.jpg (chroma keyed)
      2. Frozen first frame extracted from clip_path (chroma keyed)
      3. Dark placeholder ColorClip
    """
    fw = frame[2]
    effective_crop = crop_bottom if crop_bottom is not None else ANCHOR_CROP_BOTTOM_DEFAULT

    def _key_and_crop(still_rgb):
        """Chroma key + padding crop on a numpy H×W×3 array. Returns H×W×4 RGBA."""
        f     = still_rgb.astype(np.float32)
        diff  = np.linalg.norm(f - CHROMA_KEY_COLOR, axis=2)
        alpha = np.where(diff < CHROMA_TOLERANCE, 0, 255).astype(np.uint8)
        rgba  = np.dstack([still_rgb, alpha])
        mask  = diff >= CHROMA_TOLERANCE
        rows  = np.any(mask, axis=1)
        cols  = np.any(mask, axis=0)
        if rows.any():
            margin = 6
            y1 = max(0, int(np.argmax(rows)) - margin)
            y2 = min(rgba.shape[0], int(rgba.shape[0] - np.argmax(rows[::-1])) + margin)
            x1 = max(0, int(np.argmax(cols)) - margin)
            x2 = min(rgba.shape[1], int(rgba.shape[1] - np.argmax(cols[::-1])) + margin)
            rgba = rgba[y1:y2, x1:x2]
        return rgba

    def _finish(rgba):
        """Resize, crop bottom, position, and optionally dim."""
        still = (
            ImageClip(rgba, is_mask=False)
            .with_duration(duration)
            .with_effects([Resize(width=fw)])
        )
        if effective_crop > 0:
            h     = int(still.size[1])
            crop_h = max(1, h - effective_crop)
            still  = still.with_effects([Crop(y1=0, y2=crop_h)])
        still = still.with_position(_frame_to_pos(frame))
        return _dim_anchor(still) if dim else still

    # ── Priority 1: rest image keyed to avatar_id ──────────────────────────────
    if anchor_id:
        anchor = ANCHOR_LOOKUP.get(anchor_id)
        if anchor:
            avatar_id = anchor.get("avatar_id", "")
            rest_path = PROJECT_ROOT / "assets" / "rest_frames" / f"{avatar_id}.jpg"
            if rest_path.exists():
                try:
                    from PIL import Image as _PILImage
                    still_rgb = np.array(_PILImage.open(str(rest_path)).convert("RGB"))
                    return _finish(_key_and_crop(still_rgb))
                except Exception as e:
                    print(f"  WARNING: rest image load failed for {anchor_id}: {e}")

    # ── Priority 2: frozen first frame from clip ───────────────────────────────
    if clip_path and Path(clip_path).exists():
        try:
            raw = load_anchor_clip(clip_path, target_duration=None)
            still_rgb = raw.get_frame(0)
            raw.close()
            return _finish(_key_and_crop(still_rgb))
        except Exception as e:
            print(f"  WARNING: frozen frame extraction failed: {e}")

    # ── Priority 3: dark placeholder ──────────────────────────────────────────
    placeholder_h = int(fw * (CONTENT_H / max(CONTENT_W, 1)))
    return ColorClip(
        size=(fw, placeholder_h),
        color=[20, 22, 28],
        duration=duration,
    ).with_position(_frame_to_pos(frame))


def build_anchor_layers(
    shot_mode: str,
    anchor_id: str,
    anchor_clip_path: str | Path,
    duration: float,
    all_segments: list | None = None,
) -> list:
    """
    Return a list of positioned anchor VideoFileClip layers for this segment.

    wide    → A at ANCHOR_A_FRAME, B at ANCHOR_B_FRAME (both full opacity)
              NOTE: wide mode uses the same clip at both positions until
              dual-clip wide shots are supported.

    solo_a  → A at ANCHOR_A_FRAME full opacity
               B seat: frozen first frame of the seat-b anchor's own clip (dimmed),
               looked up from all_segments. Falls back to dark placeholder.

    solo_b  → B at ANCHOR_B_FRAME full opacity
               A seat: frozen first frame of the seat-a anchor's own clip (dimmed),
               looked up from all_segments. Falls back to dark placeholder.

    Parameters
    ----------
    all_segments : list, optional
        Full list of segment dicts from the shot plan. Used to locate a clip
        for the inactive anchor's stand-in. Pass None to skip (placeholder used).
    """
    # Only load the live clip for modes that actually need it
    clip = None
    if shot_mode not in ("wide", "broll"):
        clip = load_anchor_clip(anchor_clip_path, target_duration=duration)

    if shot_mode == "wide":
        seat_a_id = next((a["id"] for a in ANCHORS if a.get("seat") == "a"), None)
        seat_b_id = next((a["id"] for a in ANCHORS if a.get("seat") == "b"), None)
        standin_a_path = _find_standin_clip(seat_a_id, all_segments or []) if seat_a_id else None
        standin_b_path = _find_standin_clip(seat_b_id, all_segments or []) if seat_b_id else None
        clip_a = _make_standin(ANCHOR_A_FRAME, duration, standin_a_path,
                               dim=False, crop_bottom=_anchor_crop(seat_a_id), anchor_id=seat_a_id)
        clip_b = _make_standin(ANCHOR_B_FRAME, duration, standin_b_path,
                               dim=False, crop_bottom=_anchor_crop(seat_b_id), anchor_id=seat_b_id)
        return [clip_a, clip_b]

    elif shot_mode == "solo_a":
        clip_a = _resize_and_crop_anchor(clip, ANCHOR_A_FRAME, crop_bottom=_anchor_crop(anchor_id))
        return [clip_a]

    elif shot_mode == "solo_b":
        clip_b = _resize_and_crop_anchor(clip, ANCHOR_B_FRAME, crop_bottom=_anchor_crop(anchor_id))
        return [clip_b]

    elif shot_mode == "broll":
        return []

    else:
        raise ValueError(f"Unknown shot_mode: {shot_mode!r}")


# ── Wall screen / B-roll layer ─────────────────────────────────────────────────

# Grid layout: 3 columns × 2 rows across WALL_SCREEN_FRAME
WALL_GRID_COLS = 3
WALL_GRID_ROWS = 2
# Active media cell: lower-center (col=1, row=1, zero-indexed)
WALL_ACTIVE_COL = 1
WALL_ACTIVE_ROW = 1


def build_wall_screen(
    broll_clip_path: str | Path | None,
    duration: float,
    default_image_path: str | Path | None = None,
) -> CompositeVideoClip:
    """
    Composite the wall screen area.

    The default image (logo/static) fills the entire WALL_SCREEN_FRAME as a
    background. When a b-roll asset is available, the lower-center cell of a
    3×2 grid is composited on top — the rest of the default image shows through
    unchanged, exactly like the inactive anchor stand-in approach.

    If no default image is available, a dark ColorClip is used as the base.
    """
    wx, wy, ww, wh = WALL_SCREEN_FRAME
    gap = 2

    cell_w = (ww - gap * (WALL_GRID_COLS - 1)) // WALL_GRID_COLS
    cell_h = (wh - gap * (WALL_GRID_ROWS - 1)) // WALL_GRID_ROWS

    # Layer 1 — default image covers the full wall area
    if default_image_path and Path(default_image_path).exists():
        try:
            base = (
                ImageClip(str(default_image_path))
                .with_duration(duration)
                .with_effects([Resize((ww, wh))])
                .with_position((0, 0))
            )
        except Exception as e:
            print(f"  WARNING: wall screen default image failed to load: {e}")
            base = ColorClip(size=(ww, wh), color=[18, 22, 30], duration=duration).with_position((0, 0))
    else:
        base = ColorClip(size=(ww, wh), color=[18, 22, 30], duration=duration).with_position((0, 0))

    layers = [base]

    # Layer 2 — active media cell composited on top when b-roll is available
    if broll_clip_path and Path(broll_clip_path).exists():
        try:
            cx = WALL_ACTIVE_COL * (cell_w + gap)
            cy = WALL_ACTIVE_ROW * (cell_h + gap)
            active_clip = (
                load_broll_clip(broll_clip_path, duration)
                .with_effects([Resize((cell_w, cell_h))])
                .with_position((cx, cy))
            )
            layers.append(active_clip)
        except Exception as e:
            print(f"  WARNING: wall screen active media failed to load: {e}")

    wall = CompositeVideoClip(layers, size=(ww, wh)).with_duration(duration)
    return wall.with_position((wx, wy))


def build_broll_fullscreen(
    broll_clip_path: str | Path | None,
    duration: float,
) -> VideoFileClip | ColorClip:
    """Full-frame B-roll for 'broll' shot mode. Loops if shorter than duration."""
    if broll_clip_path and Path(broll_clip_path).exists():
        clip = load_broll_clip(broll_clip_path, duration)
        return clip.with_effects([Resize((W, H))]).with_position((0, 0))
    else:
        return make_fallback_broll(duration, (W, H)).with_position((0, 0))


# ── PiP anchor layer (broll mode only) ────────────────────────────────────────

def build_pip_layer(
    anchor_clip_path: str | Path,
    duration: float,
) -> VideoFileClip:
    """
    Small anchor insert for broll shot mode.
    Positioned at PIP_FRAME, with a thin border via Margin effect.
    """
    from moviepy.video.fx import Margin

    clip = load_anchor_clip(anchor_clip_path, target_duration=duration)
    fw, fh = _frame_size(PIP_FRAME)
    clip = clip.with_effects([Resize((fw, fh))])
    # Thin 2px border rendered as a margin with background color
    clip = clip.with_effects([Margin(margin_size=2, color=[200, 200, 200])])
    return clip.with_position(_frame_to_pos(PIP_FRAME))


# ── Lower-third overlay ────────────────────────────────────────────────────────

def build_lower_third(
    headline: str | None,
    source: str | None,
    duration: float,
    frame: tuple | None = None,
) -> CompositeVideoClip | None:
    """
    Returns a CompositeVideoClip of the lower-third bar + text, or None if
    both headline and source are absent.

    frame: (x, y, w, h) — defaults to LOWER_THIRD_FRAME. Pass
    SOLO_A_LOWER_THIRD_FRAME or SOLO_B_LOWER_THIRD_FRAME for solo shots.

    Layout (relative to frame):
        [  HEADLINE TEXT                         SOURCE  ]
    """
    if not headline and not source:
        return None

    lx, ly, lw, lh = frame if frame is not None else LOWER_THIRD_FRAME

    # Scale font sizes proportionally to frame height so solo lower thirds
    # (which are shorter than the full-width bar) render legible text.
    ref_h = LOWER_THIRD_FRAME[3]   # reference height — full-width bar
    scale = lh / ref_h
    headline_size = max(10, int(LOWER_THIRD_HEADLINE_SIZE * scale))
    source_size   = max(8,  int(LOWER_THIRD_SOURCE_SIZE   * scale))

    # Background bar
    bg = ColorClip(size=(lw, lh), color=LOWER_THIRD_BG_COLOR, duration=duration)
    layers = [bg]

    # Headline
    if headline:
        try:
            hl = TextClip(
                font=LOWER_THIRD_FONT,
                text=headline,
                font_size=headline_size,
                color=LOWER_THIRD_HEADLINE_COLOR,
                bg_color=None,
                transparent=True,
                duration=duration,
            ).with_position((16, (lh - headline_size) // 2))
            layers.append(hl)
        except Exception as e:
            print(f"  WARNING: lower-third headline render failed: {e}")

    # Source slug (right-aligned)
    if source:
        try:
            src = TextClip(
                font=LOWER_THIRD_FONT,
                text=source.upper(),
                font_size=source_size,
                color=LOWER_THIRD_SOURCE_COLOR,
                bg_color=None,
                transparent=True,
                duration=duration,
            ).with_position((lw - 200, (lh - source_size) // 2))
            layers.append(src)
        except Exception as e:
            print(f"  WARNING: lower-third source render failed: {e}")

    lt = CompositeVideoClip(layers, size=(lw, lh)).with_position((lx, ly))
    return lt.with_effects([FadeIn(0.15), FadeOut(0.15)])


# ── Background ─────────────────────────────────────────────────────────────────

def load_background(duration: float) -> ImageClip | ColorClip:
    """Load the virtual set background image, or fall back to dark color."""
    bg_path = Path(SET_BACKGROUND_IMAGE)
    if bg_path.exists():
        return ImageClip(str(bg_path)).with_duration(duration).with_effects([Resize((W, H))])
    else:
        print(f"  WARNING: SET_BACKGROUND_IMAGE not found at {bg_path} — using color fallback")
        return ColorClip(size=(W, H), color=[12, 14, 20], duration=duration)


# ── Single segment compositor ──────────────────────────────────────────────────

def composite_segment(seg: dict, all_segments: list | None = None, nameplate_layers: list | None = None) -> CompositeVideoClip | None:
    """
    Build one CompositeVideoClip for a single shot plan segment.
    Returns None if the anchor clip is missing (segment not yet rendered).

    nameplate_layers: optional list of clips to composite over the full canvas
    BEFORE the solo viewfinder crop is applied — so they scale correctly with it.
    """
    sid = seg["segment_id"]
    shot_mode = seg.get("shot_mode", "solo_a")
    anchor_clip_path = seg.get("anchor_clip")

    # Guard: anchor clip must exist for all shot modes
    if not anchor_clip_path or not Path(anchor_clip_path).exists():
        print(f"  SKIP {sid}: anchor clip not found at {anchor_clip_path!r}")
        return None

    anchor_clip_probe = VideoFileClip(str(anchor_clip_path))
    duration = anchor_clip_probe.duration
    anchor_clip_probe.close()

    broll_path = seg.get("broll_clip")
    headline = seg.get("lower_third_headline")
    source = seg.get("lower_third_source")

    print(f"  compositing [{shot_mode:6s}] {sid}  ({duration:.1f}s)")

    # Layer 1 — background
    bg = load_background(duration)

    # Layer 2 — B-roll / wall screen
    wall_default = PROJECT_ROOT / "assets" / "wall_default.jpg"
    if shot_mode == "broll":
        broll = build_broll_fullscreen(broll_path, duration)
    else:
        broll = build_wall_screen(broll_path, duration, default_image_path=wall_default)

    # Layer 3 — anchor(s)
    anchor_layers = build_anchor_layers(shot_mode, seg.get("anchor_id", ""), anchor_clip_path, duration, all_segments=all_segments)

    # Layer 4 — PiP (broll mode only)
    # pip_layers = []
    # if shot_mode == "broll" and anchor_clip_path:
    #     pip_layers = [build_pip_layer(anchor_clip_path, duration)]

    # Layer 5 — lower third
    if shot_mode == "solo_a":
        lt_frame = SOLO_A_LOWER_THIRD_FRAME
    elif shot_mode == "solo_b":
        lt_frame = SOLO_B_LOWER_THIRD_FRAME
    else:
        lt_frame = None   # defaults to LOWER_THIRD_FRAME
    lt = build_lower_third(headline, source, duration, frame=lt_frame)
    lt_layers = [lt] if lt else []

    all_layers = [bg, broll] + anchor_layers + lt_layers + (nameplate_layers or [])
    comp = CompositeVideoClip(all_layers, size=(W, H)).with_duration(duration)

    # ── Audio injection ────────────────────────────────────────────────────────
    # wide and bumper segments carry voice audio from the HeyGen clip.
    # Solo segments already have audio from load_anchor_clip.
    # Regular wide shots (section openers) have no clip so condition safely skips.
    if shot_mode in ("wide", "bumper", "broll"):
        clip_p = str(anchor_clip_path or "")
        if clip_p and Path(clip_p).exists():
            try:
                vc = VideoFileClip(clip_p)
                if vc.audio is not None:
                    comp = comp.with_audio(vc.audio.with_duration(duration))
                # Note: intentionally not closing vc here — closing invalidates
                # the audio reader which is still referenced by the composite.
            except Exception as e:
                print(f"  WARNING: audio injection failed for {shot_mode} segment: {e}")

    # ── Solo viewfinder crop ───────────────────────────────────────────────────
    # Crop a sub-rectangle of the full canvas and scale up to fill output frame.
    # Using image_transform on the composite is the reliable MoviePy 2.x approach —
    # with_effects([Crop, Resize]) on a CompositeVideoClip is not always honoured.
    if shot_mode in ("solo_a", "solo_b"):
        sf = ANCHOR_A_SOLOFRAME if shot_mode == "solo_a" else ANCHOR_B_SOLOFRAME
        sx, sy, sw, sh = sf

        def _crop_and_scale(frame):
            """Crop solo window from full canvas frame and scale to output resolution."""
            cropped = frame[sy:sy+sh, sx:sx+sw]          # H×W×3 numpy slice
            from PIL import Image as _Image
            pil = _Image.fromarray(cropped)
            pil = pil.resize((W, H), _Image.LANCZOS)
            return np.array(pil)

        comp = comp.image_transform(_crop_and_scale)

    return comp


# ── Transition handling ────────────────────────────────────────────────────────

def apply_transitions(clips_meta: list[tuple]) -> list:
    """
    clips_meta: list of (CompositeVideoClip, transition_in, transition_out)

    Applies crossfade effects at segment boundaries.
    Returns a flat list of clips ready for concatenate_videoclips.
    """
    out = []
    for i, (clip, t_in, t_out) in enumerate(clips_meta):
        is_first = i == 0
        is_last = i == len(clips_meta) - 1

        if not is_first and t_in == "crossfade":
            clip = clip.with_effects([CrossFadeIn(CROSSFADE_DURATION)])
        if not is_last and t_out == "crossfade":
            clip = clip.with_effects([CrossFadeOut(CROSSFADE_DURATION)])

        out.append(clip)
    return out


# ── Shot plan loading ──────────────────────────────────────────────────────────

def load_shot_plan(plan_path: Path) -> dict:
    if not plan_path.exists():
        print(f"ERROR: shot plan not found: {plan_path}")
        sys.exit(1)
    return json.loads(plan_path.read_text())


def resolve_clip_paths(plan: dict) -> dict:
    """
    If anchor_clip paths in the plan are relative, resolve them against EPISODE_DIR.
    Also back-fills anchor_clip from anchor_jobs.json if anchor_clip is null.
    """
    jobs = {}
    if ANCHOR_JOBS_JSON.exists():
        jobs = json.loads(ANCHOR_JOBS_JSON.read_text())

    for seg in plan["segments"]:
        sid = seg["segment_id"]

        # Back-fill from anchor_jobs.json
        if not seg.get("anchor_clip") and sid in jobs:
            job = jobs[sid]
            if job.get("clip_path"):
                seg["anchor_clip"] = job["clip_path"]

        # Resolve relative paths against PROJECT_ROOT
        for key in ("anchor_clip", "broll_clip"):
            if seg.get(key):
                p = Path(seg[key])
                if not p.is_absolute():
                    seg[key] = str(PROJECT_ROOT / p)

    return plan


# ── Dry-run table ──────────────────────────────────────────────────────────────

def print_dry_run(plan: dict) -> None:
    segs = plan["segments"]
    print(f"\nShot plan: {plan.get('episode', '?')}  ({len(segs)} segments)\n")
    print(f"  {'#':<3} {'segment_id':<45} {'mode':<8} {'anchor':<10} {'anchor_clip':<6} {'broll':<6}")
    print(f"  {'-'*3} {'-'*45} {'-'*8} {'-'*10} {'-'*6} {'-'*6}")
    for i, seg in enumerate(segs, 1):
        has_anchor = "YES" if seg.get("anchor_clip") and Path(seg["anchor_clip"]).exists() else "---"
        has_broll  = "YES" if seg.get("broll_clip")  and Path(seg["broll_clip"]).exists()  else "---"
        print(
            f"  {i:<3} {seg['segment_id'][:45]:<45} "
            f"{seg.get('shot_mode','?'):<8} "
            f"{seg.get('anchor_id','?'):<10} "
            f"{has_anchor:<6} "
            f"{has_broll:<6}"
        )
    missing_anchor = sum(
        1 for s in segs
        if not s.get("anchor_clip") or not Path(s["anchor_clip"]).exists()
    )
    if missing_anchor:
        print(f"\n  {missing_anchor} segment(s) missing anchor clips — will be skipped at render time.")
    print()


# ── Audio helpers ──────────────────────────────────────────────────────────────

def _load_music(duration: float, volume: float) -> AudioFileClip | None:
    """Load opening music trimmed/looped to duration at given volume. Returns None if missing."""
    if not MUSIC_PATH.exists():
        print(f"  WARNING: music not found at {MUSIC_PATH}")
        return None
    music = AudioFileClip(str(MUSIC_PATH))
    if music.duration < duration:
        music = music.with_effects([AudioLoop(duration=duration)])
    else:
        music = music.with_end(duration)
    return music.with_effects([AudioFadeIn(0.1)]).with_volume_scaled(volume)


def _load_voice(clip_path: Path) -> AudioFileClip | None:
    """Load voice audio from an MP4 or audio file. Returns None if missing."""
    if not clip_path.exists():
        print(f"  INFO: voice clip not found at {clip_path} — skipping")
        return None
    if clip_path.suffix.lower() in (".mp4", ".mov"):
        vc = VideoFileClip(str(clip_path))
        return vc.audio
    return AudioFileClip(str(clip_path))


# ── Intro clip ─────────────────────────────────────────────────────────────────

def build_intro_clip() -> CompositeVideoClip:
    """
    Opening sequence:
      - Wall default image fills full screen
      - Music plays at full volume for INTRO_MUSIC_LEAD seconds
      - Intro voice begins; music ducks to MUSIC_BED_VOLUME under voice
      - Ends after voice; first wide segment follows immediately
    """
    wall_default = PROJECT_ROOT / "assets" / "wall_default.jpg"
    voice = _load_voice(INTRO_AUDIO_CLIP)
    voice_duration = voice.duration if voice else 4.0
    total_duration = INTRO_MUSIC_LEAD + voice_duration

    if wall_default.exists():
        video = (ImageClip(str(wall_default))
                 .with_duration(total_duration)
                 .with_effects([Resize((W, H))]))
    else:
        video = ColorClip(size=(W, H), color=[18, 22, 30], duration=total_duration)

    audio_layers = []
    music_full = _load_music(INTRO_MUSIC_LEAD, MUSIC_FULL_VOLUME)
    music_bed  = _load_music(voice_duration, MUSIC_BED_VOLUME)
    if music_full:
        audio_layers.append(music_full)
    if music_bed:
        audio_layers.append(music_bed.with_start(INTRO_MUSIC_LEAD))
    if voice:
        audio_layers.append(voice.with_start(INTRO_MUSIC_LEAD))

    if audio_layers:
        video = video.with_audio(CompositeAudioClip(audio_layers))

    print(f"  intro clip: {total_duration:.1f}s")
    return video.with_duration(total_duration)


# ── Anchor nameplate ───────────────────────────────────────────────────────────

def build_anchor_nameplate(anchor_id: str, duration: float = 3.0) -> CompositeVideoClip | None:
    """Navy bar with anchor name — shown at the start of each anchor's first story."""
    anchor = ANCHOR_LOOKUP.get(anchor_id)
    if not anchor:
        return None

    display_name = anchor_id   # use actual name, not label
    lx, ly, lw, lh = LOWER_THIRD_FRAME

    bg = ColorClip(size=(lw, lh), color=LOWER_THIRD_BG_COLOR, duration=duration)
    layers = [bg]
    try:
        name_clip = TextClip(
            font=LOWER_THIRD_FONT,
            text=display_name,
            font_size=LOWER_THIRD_HEADLINE_SIZE,
            color=LOWER_THIRD_HEADLINE_COLOR,
            bg_color=None,
            transparent=True,
            duration=duration,
        ).with_position((lw // 2 - 100, (lh - LOWER_THIRD_HEADLINE_SIZE) // 2))
        layers.append(name_clip)
    except Exception as e:
        print(f"  WARNING: nameplate render failed for {anchor_id}: {e}")

    plate = CompositeVideoClip(layers, size=(lw, lh)).with_position((lx, ly))
    return plate.with_effects([FadeIn(0.3), FadeOut(0.3)])


# ── Between-story pause ────────────────────────────────────────────────────────

def build_between_pause(
    outgoing_comp: CompositeVideoClip,
    incoming_comp: CompositeVideoClip,
    hold: float = 0.5,
) -> CompositeVideoClip:
    """Hold last frame of outgoing for `hold`s, then first frame of incoming for `hold`s."""
    last_frame  = outgoing_comp.get_frame(outgoing_comp.duration - 1 / VIDEO_FPS)
    first_frame = incoming_comp.get_frame(0)
    out_hold = ImageClip(last_frame).with_duration(hold)
    in_hold  = ImageClip(first_frame).with_duration(hold)
    return concatenate_videoclips([out_hold, in_hold], method="compose")


# ── Close clip ─────────────────────────────────────────────────────────────────

def build_close_clip(plan: dict) -> CompositeVideoClip:
    """
    Closing sequence:
      - Wide set fades to black (CLOSE_WIDE_HOLD seconds)
      - Credit screen with source publication names (CLOSE_CREDITS_DURATION seconds)
      - Close voice + music return over the whole sequence
    """
    sources = []
    for seg in plan.get("segments", []):
        src = seg.get("lower_third_source")
        if src and src not in sources:
            sources.append(src)

    wide_hold  = CLOSE_WIDE_HOLD
    credit_dur = CLOSE_CREDITS_DURATION

    # Wide set fading to black
    wide_bg = load_background(wide_hold).with_opacity(0.5)
    black_w = ColorClip(size=(W, H), color=[0, 0, 0], duration=wide_hold)
    wide    = (CompositeVideoClip([black_w, wide_bg], size=(W, H))
               .with_duration(wide_hold)
               .with_effects([FadeOut(wide_hold)]))

    # Credit screen
    black_c = ColorClip(size=(W, H), color=[0, 0, 0], duration=credit_dur)
    credit_layers = [black_c]

    try:
        header = TextClip(
            font=LOWER_THIRD_FONT, text="Sources",
            font_size=36, color="white",
            bg_color=None, transparent=True, duration=credit_dur,
        ).with_position(("center", 300))
        credit_layers.append(header)
    except Exception as e:
        print(f"  WARNING: credit header render failed: {e}")

    for i, src in enumerate(sources):
        try:
            src_clip = TextClip(
                font=LOWER_THIRD_FONT, text=src,
                font_size=28, color="#AABBEE",
                bg_color=None, transparent=True, duration=credit_dur,
            ).with_position(("center", 370 + i * 48))
            credit_layers.append(src_clip)
        except Exception as e:
            print(f"  WARNING: credit source render failed ({src}): {e}")

    credits = (CompositeVideoClip(credit_layers, size=(W, H))
               .with_duration(credit_dur)
               .with_effects([FadeIn(1.0)]))

    video = concatenate_videoclips([wide, credits], method="compose")
    total_duration = wide_hold + credit_dur

    # Audio: close voice + music
    audio_layers = []
    music = _load_music(total_duration, MUSIC_FULL_VOLUME)
    voice = _load_voice(CLOSE_AUDIO_CLIP)
    if music:
        audio_layers.append(music.with_effects([AudioFadeIn(1.0)]))
    if voice:
        audio_layers.append(voice)
    if audio_layers:
        video = video.with_audio(CompositeAudioClip(audio_layers))

    print(f"  close clip: {total_duration:.1f}s  ({len(sources)} sources)")
    return video.with_duration(total_duration)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NewsCrew compositor")
    parser.add_argument("--plan",    type=Path, default=SHOT_PLAN_JSON, help="Path to shot_plan.json")
    parser.add_argument("--out",     type=Path, default=OUTPUT_VIDEO,   help="Output MP4 path")
    parser.add_argument("--dry-run", action="store_true",               help="Print segment table, no render")
    parser.add_argument("--preset",  default="medium",                  help="ffmpeg preset (ultrafast..veryslow)")
    args = parser.parse_args()

    plan = load_shot_plan(args.plan)
    plan = resolve_clip_paths(plan)

    if args.dry_run:
        print_dry_run(plan)
        return

    print(f"\nBuilding episode: {plan.get('episode', '?')}")
    print(f"  {len(plan['segments'])} segments in shot plan")
    print(f"  output → {args.out}\n")

    # ── 1. Assemble final clip list ────────────────────────────────────────────
    print("\n  Assembling episode sequence...")
    final_clips = []
    seen_anchors: set[str] = set()

    # Intro
    print("  building intro...")
    final_clips.append(build_intro_clip())

    # Stories with nameplates and between-story pauses
    story_count = 0
    for seg in plan["segments"]:
        anchor_id = seg.get("anchor_id", "")

        # Build nameplate for first appearance of each anchor — solo shots only
        nameplate_layers = None
        shot_mode = seg.get("shot_mode", "")
        if shot_mode in ("solo_a", "solo_b") and anchor_id and anchor_id not in seen_anchors:
            seen_anchors.add(anchor_id)
            nameplate = build_anchor_nameplate(anchor_id, duration=3.0)
            if nameplate:
                nameplate_layers = [nameplate]

        comp = composite_segment(seg, all_segments=plan["segments"], nameplate_layers=nameplate_layers)
        if comp is None:
            continue

        final_clips.append(comp)
        story_count += 1

    if story_count == 0:
        print("ERROR: no compositable segments found. Run anchor_renderer.py first.")
        sys.exit(1)

    # Close
    print("  building close...")
    final_clips.append(build_close_clip(plan))

    # ── 3. Concatenate and write ───────────────────────────────────────────────
    print(f"\n  {len(final_clips)} clips total. Concatenating...")

    # Ensure every clip has an audio track — silent if none — so MoviePy's
    # CompositeAudioClip doesn't hit a None reader during write.
    from moviepy.audio.AudioClip import AudioClip as _AudioClip
    def _ensure_audio(clip):
        if clip.audio is None:
            silence = _AudioClip(
                frame_function=lambda t: [0, 0],
                duration=clip.duration,
                fps=44100,
            )
            return clip.with_audio(silence)
        return clip

    final_clips = [_ensure_audio(c) for c in final_clips]
    episode = concatenate_videoclips(final_clips, method="compose")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Writing {args.out} ...")
    episode.write_videofile(
        str(args.out),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        preset=args.preset,
        threads=4,
        logger="bar",
    )
    print(f"\nDone. Episode saved to: {args.out}")


if __name__ == "__main__":
    main()

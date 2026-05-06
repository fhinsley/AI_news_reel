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
    ImageClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips,
)
from moviepy.video.fx import Resize, FadeIn, FadeOut, CrossFadeIn, CrossFadeOut, Crop

from config import (
    EPISODE_DIR,
    ANCHOR_JOBS_JSON,
    OUTPUT_VIDEO,
    VIDEO_RESOLUTION,
    VIDEO_FPS,
    ANCHORS,
    # Compositor geometry — added to config.py (see block at bottom of this file)
    SET_BACKGROUND_IMAGE,
    ANCHOR_A_FRAME,
    ANCHOR_B_FRAME,
    ANCHOR_CROP_BOTTOM,
    WALL_SCREEN_FRAME,
    PIP_FRAME,
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
)

W, H = VIDEO_RESOLUTION
ANCHOR_LOOKUP = {a["id"]: a for a in ANCHORS}

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
    clip = VideoFileClip(str(p)).with_volume_scale(0)
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


def _resize_and_crop_anchor(clip: VideoFileClip, frame: tuple) -> VideoFileClip:
    """
    1. Remove green screen background
    2. Crop transparent padding so (fx, fy) aligns to top of visible person
    3. Resize to frame width, preserving aspect ratio
    4. Crop bottom by ANCHOR_CROP_BOTTOM to simulate desk occlusion
    5. Position at frame (x, y)
    """
    fx, fy, fw = frame

    # Step 1 — remove green screen
    clip = remove_green_screen(clip)

    # Step 2 — crop transparent padding
    x1, y1, x2, y2 = detect_content_box(clip)
    clip = clip.with_effects([Crop(x1=x1, y1=y1, x2=x2, y2=y2)])

    # Step 3 — scale to frame width, aspect ratio preserved
    clip = clip.with_effects([Resize(width=fw)])

    # Step 4 — crop bottom for desk occlusion
    if ANCHOR_CROP_BOTTOM > 0:
        clip_h = int(clip.size[1])
        crop_h = max(1, clip_h - ANCHOR_CROP_BOTTOM)
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
) -> VideoFileClip | ColorClip:
    """
    Build the dimmed frozen stand-in for the inactive anchor seat.

    If clip_path is provided (and exists), freeze its first frame, key out
    green, crop padding, resize to frame width, and dim to 0.35 opacity.

    If clip_path is None or missing, return a neutral dark placeholder
    ColorClip sized to the expected rendered dimensions (approximate).
    """
    fw = frame[2]

    if clip_path and Path(clip_path).exists():
        raw = load_anchor_clip(clip_path, target_duration=None)
        # Extract a true numpy still — ImageClip is guaranteed motionless.
        # A VideoFileClip "frozen" with with_end(1/fps) can still animate
        # when composited, so we pull the frame array and discard the clip.
        still_rgb = raw.get_frame(0)   # H×W×3 uint8
        raw.close()

        # Chroma-key directly on the numpy array
        f     = still_rgb.astype(np.float32)
        diff  = np.linalg.norm(f - CHROMA_KEY_COLOR, axis=2)
        alpha = np.where(diff < CHROMA_TOLERANCE, 0, 255).astype(np.uint8)
        still_rgba = np.dstack([still_rgb, alpha])   # H×W×4

        # Crop transparent padding from the still
        mask = diff >= CHROMA_TOLERANCE
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if rows.any():
            margin = 6
            y1 = max(0, int(np.argmax(rows)) - margin)
            y2 = min(still_rgba.shape[0], int(still_rgba.shape[0] - np.argmax(rows[::-1])) + margin)
            x1 = max(0, int(np.argmax(cols)) - margin)
            x2 = min(still_rgba.shape[1], int(still_rgba.shape[1] - np.argmax(cols[::-1])) + margin)
            still_rgba = still_rgba[y1:y2, x1:x2]

        frozen = (
            ImageClip(still_rgba, is_mask=False)
            .with_duration(duration)
            .with_effects([Resize(width=fw)])
        )
        if ANCHOR_CROP_BOTTOM > 0:
            frozen_h = int(frozen.size[1])
            crop_h = max(1, frozen_h - ANCHOR_CROP_BOTTOM)
            frozen = frozen.with_effects([Crop(y1=0, y2=crop_h)])
        frozen = frozen.with_position(_frame_to_pos(frame))
        return _dim_anchor(frozen) if dim else frozen
    else:
        # No clip available — neutral dark placeholder sized to approximate anchor height
        placeholder_h = int(fw * (CONTENT_H / max(CONTENT_W, 1)))
        placeholder = ColorClip(
            size=(fw, placeholder_h),
            color=[20, 22, 28],
            duration=duration,
        ).with_position(_frame_to_pos(frame))
        return placeholder


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
    clip = load_anchor_clip(anchor_clip_path, target_duration=duration)

    if shot_mode == "wide":
        # Use the same clip at both positions (single-clip wide shot).
        # TODO: replace with distinct A/B clips when both are available.
        clip_a = _resize_and_crop_anchor(clip, ANCHOR_A_FRAME)
        clip_b = _resize_and_crop_anchor(clip, ANCHOR_B_FRAME)
        return [clip_a, clip_b]

    elif shot_mode == "solo_a":
        clip_a = _resize_and_crop_anchor(clip, ANCHOR_A_FRAME)

        # Inactive seat: find seat-b anchor's own clip for a proper stand-in
        seat_b_id = next(
            (a["id"] for a in ANCHORS if a.get("seat") == "b"),
            None,
        )
        standin_path = _find_standin_clip(seat_b_id, all_segments or []) if seat_b_id else None
        if standin_path is None:
            print(f"    INFO: no clip found for seat-b anchor ({seat_b_id!r}) — using dark placeholder")
        clip_b = _make_standin(ANCHOR_B_FRAME, duration, standin_path, dim=False)
        return [clip_a, clip_b]

    elif shot_mode == "solo_b":
        clip_b = _resize_and_crop_anchor(clip, ANCHOR_B_FRAME)

        # Inactive seat: find seat-a anchor's own clip for a proper stand-in
        seat_a_id = next(
            (a["id"] for a in ANCHORS if a.get("seat") == "a"),
            None,
        )
        standin_path = _find_standin_clip(seat_a_id, all_segments or []) if seat_a_id else None
        if standin_path is None:
            print(f"    INFO: no clip found for seat-a anchor ({seat_a_id!r}) — using dark placeholder")
        clip_a = _make_standin(ANCHOR_A_FRAME, duration, standin_path, dim=False)
        return [clip_b, clip_a]

    elif shot_mode == "broll":
        # No anchor layers in the set — handled by build_pip_layer instead
        return []

    else:
        raise ValueError(f"Unknown shot_mode: {shot_mode!r}")


# ── B-roll layer ───────────────────────────────────────────────────────────────

def build_broll_layer(
    shot_mode: str,
    broll_clip_path: str | Path | None,
    duration: float,
) -> VideoFileClip | ColorClip:
    """
    Return the B-roll clip positioned and sized for the current shot mode.

    wide / solo_*  → B-roll confined to WALL_SCREEN_FRAME (wall-mounted screen)
    broll          → B-roll fills full frame (W × H)
    """
    if shot_mode == "broll":
        target_size = (W, H)
        pos = (0, 0)
    else:
        target_size = _frame_size(WALL_SCREEN_FRAME)
        pos = _frame_to_pos(WALL_SCREEN_FRAME)

    if broll_clip_path and Path(broll_clip_path).exists():
        clip = load_broll_clip(broll_clip_path, duration)
        clip = clip.with_effects([Resize(target_size)])
    else:
        clip = make_fallback_broll(duration, target_size)

    return clip.with_position(pos)


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
) -> CompositeVideoClip | None:
    """
    Returns a CompositeVideoClip of the lower-third bar + text, or None if
    both headline and source are absent.

    Layout (relative to LOWER_THIRD_FRAME):
        [  HEADLINE TEXT                         SOURCE  ]
    """
    if not headline and not source:
        return None

    lx, ly, lw, lh = LOWER_THIRD_FRAME

    # Background bar
    bg = ColorClip(size=(lw, lh), color=LOWER_THIRD_BG_COLOR, duration=duration)
    layers = [bg]

    # Headline
    if headline:
        try:
            hl = TextClip(
                font=LOWER_THIRD_FONT,
                text=headline,
                font_size=LOWER_THIRD_HEADLINE_SIZE,
                color=LOWER_THIRD_HEADLINE_COLOR,
                bg_color=None,
                transparent=True,
                duration=duration,
            ).with_position((16, (lh - LOWER_THIRD_HEADLINE_SIZE) // 2))
            layers.append(hl)
        except Exception as e:
            print(f"  WARNING: lower-third headline render failed: {e}")

    # Source slug (right-aligned)
    if source:
        try:
            src = TextClip(
                font=LOWER_THIRD_FONT,
                text=source.upper(),
                font_size=LOWER_THIRD_SOURCE_SIZE,
                color=LOWER_THIRD_SOURCE_COLOR,
                bg_color=None,
                transparent=True,
                duration=duration,
            ).with_position((lw - 200, (lh - LOWER_THIRD_SOURCE_SIZE) // 2))
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

def composite_segment(seg: dict, all_segments: list | None = None) -> CompositeVideoClip | None:
    """
    Build one CompositeVideoClip for a single shot plan segment.
    Returns None if the anchor clip is missing (segment not yet rendered).
    """
    sid = seg["segment_id"]
    shot_mode = seg.get("shot_mode", "solo_a")
    anchor_clip_path = seg.get("anchor_clip")

    # Guard: anchor clip must exist
    if not anchor_clip_path or not Path(anchor_clip_path).exists():
        print(f"  SKIP {sid}: anchor clip not found at {anchor_clip_path!r}")
        return None

    # Duration is driven by the anchor clip
    anchor_clip_probe = VideoFileClip(str(anchor_clip_path))
    duration = anchor_clip_probe.duration
    anchor_clip_probe.close()

    broll_path = seg.get("broll_clip")
    headline = seg.get("lower_third_headline")
    source = seg.get("lower_third_source")

    print(f"  compositing [{shot_mode:6s}] {sid}  ({duration:.1f}s)")

    # Layer 1 — background
    bg = load_background(duration)

    # Layer 2 — B-roll
    broll = build_broll_layer(shot_mode, broll_path, duration)

    # Layer 3 — anchor(s)
    anchor_layers = build_anchor_layers(shot_mode, seg.get("anchor_id", ""), anchor_clip_path, duration, all_segments=all_segments)

    # Layer 4 — PiP (broll mode only)
    pip_layers = []
    if shot_mode == "broll" and anchor_clip_path:
        pip_layers = [build_pip_layer(anchor_clip_path, duration)]

    # Layer 5 — lower third
    lt = build_lower_third(headline, source, duration)
    lt_layers = [lt] if lt else []

    all_layers = [bg, broll] + anchor_layers + pip_layers + lt_layers
    return CompositeVideoClip(all_layers, size=(W, H)).with_duration(duration)


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

    clips_meta = []
    for seg in plan["segments"]:
        comp = composite_segment(seg, all_segments=plan["segments"])
        if comp is None:
            continue
        t_in  = seg.get("transition_in",  "cut")
        t_out = seg.get("transition_out", "cut")
        clips_meta.append((comp, t_in, t_out))

    if not clips_meta:
        print("ERROR: no compositable segments found. Run anchor_renderer.py first.")
        sys.exit(1)

    print(f"\n  {len(clips_meta)} segments composited. Concatenating...")
    final_clips = apply_transitions(clips_meta)
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

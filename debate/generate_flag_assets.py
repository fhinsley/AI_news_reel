#!/usr/bin/env python3
"""generate_flag_assets.py
Generates procedural waving American flag background videos for the
Two-Sides debate pipeline.

Produces four files in stock_videos/:
  flag_left.mp4    — flag waves left-to-right, blue tint  (left debater)
  flag_right.mp4   — flag waves right-to-left, red tint   (right debater)
  flag_anchor.mp4  — gentle wave, neutral grey tint        (anchor)
  flag_card.mp4    — very slow wave, dark neutral           (framing card)

Run once from project root to generate assets:
  python debate/generate_flag_assets.py

The flag is rendered mathematically using numpy — no external image assets
needed. Stripe colors and star field are approximated in RGB arrays.
Wave direction encodes speaker side subliminally: left debater's flag
billows toward the right (as if wind from the left), right debater's
flag billows toward the left.
"""

import os
import sys
from pathlib import Path

import numpy as np
from moviepy import VideoClip

# ---------------------------------------------------------------------------
# Resolve paths — works when run from project root or from debate/
# ---------------------------------------------------------------------------

THIS_FILE   = Path(__file__).resolve()
SCRIPT_DIR  = THIS_FILE.parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR  = PROJECT_ROOT / "stock_videos"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Video parameters
# ---------------------------------------------------------------------------

WIDTH    = 1920
HEIGHT   = 1080
FPS      = 24
DURATION = 4.0    # seconds — short loop, looped by build_video.py via vfx.Loop

# ---------------------------------------------------------------------------
# Flag geometry
# ---------------------------------------------------------------------------

# US flag proportions: 19:10 ratio, we fill the frame with some breathing room
FLAG_W = int(WIDTH  * 0.90)
FLAG_H = int(HEIGHT * 0.85)
FLAG_X = (WIDTH  - FLAG_W) // 2
FLAG_Y = (HEIGHT - FLAG_H) // 2

N_STRIPES  = 13
STRIPE_H   = FLAG_H // N_STRIPES

# Canton (blue field) covers top 7 stripes, left 40% of flag width
CANTON_H = STRIPE_H * 7
CANTON_W = int(FLAG_W * 0.40)

# ---------------------------------------------------------------------------
# US flag colors (RGB)
# ---------------------------------------------------------------------------

RED_STRIPE   = np.array([178,  34,  52], dtype=np.float32)
WHITE_STRIPE = np.array([255, 255, 255], dtype=np.float32)
CANTON_BLUE  = np.array([ 60,  59, 110], dtype=np.float32)
STAR_WHITE   = np.array([255, 255, 255], dtype=np.float32)

# ---------------------------------------------------------------------------
# Build the flat (undeformed) flag as a float32 RGB array
# ---------------------------------------------------------------------------

def build_flat_flag() -> np.ndarray:
    """Returns H x W x 3 float32 array of the flag in its flat state."""
    flag = np.zeros((FLAG_H, FLAG_W, 3), dtype=np.float32)

    # Stripes — alternating red/white, top stripe is red
    for i in range(N_STRIPES):
        y0 = i * STRIPE_H
        y1 = y0 + STRIPE_H if i < N_STRIPES - 1 else FLAG_H
        color = RED_STRIPE if i % 2 == 0 else WHITE_STRIPE
        flag[y0:y1, :] = color

    # Canton blue field
    flag[:CANTON_H, :CANTON_W] = CANTON_BLUE

    # Stars — 5x6 and 4x5 alternating rows = 50 stars, simplified as white dots
    # Row layout: 6 columns / 5 columns alternating across 9 rows
    star_rows    = 9
    star_cols_a  = 6   # even rows
    star_cols_b  = 5   # odd rows
    star_r       = max(3, FLAG_H // 120)   # radius scales with resolution

    margin_x = CANTON_W // (star_cols_a * 2 + 1)
    margin_y = CANTON_H // (star_rows  * 2 + 1)

    for row in range(star_rows):
        cols    = star_cols_a if row % 2 == 0 else star_cols_b
        x_start = margin_x if row % 2 == 0 else margin_x + margin_x
        cy      = margin_y + row * (margin_y * 2)
        for col in range(cols):
            cx = x_start + col * (margin_x * 2)
            # Draw filled circle — mask scoped to canton dimensions only
            yy, xx = np.ogrid[:CANTON_H, :CANTON_W]
            mask = (xx - cx)**2 + (yy - cy)**2 <= star_r**2
            flag[:CANTON_H, :CANTON_W][mask] = STAR_WHITE

    return flag


# Pre-build the flat flag once — it's the same for all variants
FLAT_FLAG = build_flat_flag()

# ---------------------------------------------------------------------------
# Wave deformation
# ---------------------------------------------------------------------------

def deform_flag(flat: np.ndarray, t: float,
                amplitude: float, wavelength: float,
                omega: float) -> np.ndarray:
    """Apply sine-wave deformation to flag strips.

    Each vertical column x is shifted vertically by:
        dy(x, t) = A * sin(2π * x/λ + ω*t)

    amplitude  : max pixel displacement (vertical)
    wavelength : pixels per full wave cycle
    omega      : angular velocity (rad/s); sign controls wind direction
                 positive → wave travels left-to-right (wind from left)
                 negative → wave travels right-to-left (wind from right)
    """
    h, w, _ = flat.shape
    out = np.zeros_like(flat)

    # Also taper amplitude: left edge is fixed (attached to pole), right is free
    taper = np.linspace(0.0, 1.0, w) ** 1.5   # non-linear: more flutter at free end

    x_coords = np.arange(w)
    dy = (amplitude * taper * np.sin(2 * np.pi * x_coords / wavelength + omega * t)).astype(int)

    for x in range(w):
        shift = dy[x]
        src_rows = np.arange(h)
        dst_rows = src_rows + shift

        valid = (dst_rows >= 0) & (dst_rows < h)
        out[dst_rows[valid], x] = flat[src_rows[valid], x]

    return out


# ---------------------------------------------------------------------------
# Tint overlay
# ---------------------------------------------------------------------------

def apply_tint(frame: np.ndarray, tint_rgb: tuple, opacity: float) -> np.ndarray:
    """Blend a solid color over the frame at the given opacity."""
    tint = np.array(tint_rgb, dtype=np.float32)
    return np.clip(frame * (1 - opacity) + tint * opacity, 0, 255)


# ---------------------------------------------------------------------------
# Full frame compositor
# ---------------------------------------------------------------------------

def make_frame_fn(amplitude: float, wavelength: float, omega: float,
                  tint_rgb: tuple, tint_opacity: float,
                  bg_color: tuple = (15, 20, 40)):
    """Returns a frame-making function for MoviePy VideoClip."""

    bg = np.full((HEIGHT, WIDTH, 3), bg_color, dtype=np.float32)

    def make_frame(t: float) -> np.ndarray:
        frame = bg.copy()

        # Deform flag
        deformed = deform_flag(FLAT_FLAG, t, amplitude, wavelength, omega)

        # Apply tint to flag only
        tinted = apply_tint(deformed, tint_rgb, tint_opacity)

        # Composite flag onto background
        frame[FLAG_Y:FLAG_Y + FLAG_H, FLAG_X:FLAG_X + FLAG_W] = tinted

        return frame.astype(np.uint8)

    return make_frame


# ---------------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------------

ASSETS = [
    {
        "filename":     "flag_left.mp4",
        "description":  "Left debater — blue tint, wind from left",
        "amplitude":    38.0,
        "wavelength":   FLAG_W * 0.6,
        "omega":        2.8,          # positive → wave travels right (wind from left)
        "tint_rgb":     (30, 80, 200),
        "tint_opacity": 0.28,
        "bg_color":     (8, 15, 35),
    },
    {
        "filename":     "flag_right.mp4",
        "description":  "Right debater — red tint, wind from right",
        "amplitude":    38.0,
        "wavelength":   FLAG_W * 0.6,
        "omega":        -2.8,         # negative → wave travels left (wind from right)
        "tint_rgb":     (200, 40, 40),
        "tint_opacity": 0.28,
        "bg_color":     (35, 8, 8),
    },
    {
        "filename":     "flag_anchor.mp4",
        "description":  "Anchor — neutral grey tint, gentle wave",
        "amplitude":    22.0,
        "wavelength":   FLAG_W * 0.7,
        "omega":        1.8,
        "tint_rgb":     (160, 160, 170),
        "tint_opacity": 0.18,
        "bg_color":     (15, 20, 40),
    },
    {
        "filename":     "flag_card.mp4",
        "description":  "Framing card — dark, very slow wave",
        "amplitude":    14.0,
        "wavelength":   FLAG_W * 0.8,
        "omega":        1.0,
        "tint_rgb":     (20, 20, 30),
        "tint_opacity": 0.55,
        "bg_color":     (10, 10, 20),
    },
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Generating flag assets → {OUTPUT_DIR}\n")

    for asset in ASSETS:
        out_path = OUTPUT_DIR / asset["filename"]
        print(f"  {asset['filename']}  ({asset['description']})")

        frame_fn = make_frame_fn(
            amplitude    = asset["amplitude"],
            wavelength   = asset["wavelength"],
            omega        = asset["omega"],
            tint_rgb     = asset["tint_rgb"],
            tint_opacity = asset["tint_opacity"],
            bg_color     = asset["bg_color"],
        )

        clip = VideoClip(frame_function=frame_fn, duration=DURATION)
        clip.write_videofile(
            str(out_path),
            fps=FPS,
            codec="libx264",
            audio=False,
            logger=None,
        )
        print(f"    → {out_path}")

    print(f"\nDone. Update SECTION_VIDEOS in debate/config.py:")
    print('    "anchor": project_path("stock_videos", "flag_anchor.mp4"),')
    print('    "left":   project_path("stock_videos", "flag_left.mp4"),')
    print('    "right":  project_path("stock_videos", "flag_right.mp4"),')
    print()
    print("And for the framing card in build_video.py, replace the solid")
    print('ColorClip panel with VideoFileClip("stock_videos/flag_card.mp4")')
    print("looped to FRAMING_CARD_DURATION.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

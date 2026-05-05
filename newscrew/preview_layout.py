"""
Renders a layout preview image showing all compositor geometry frames
drawn over the set background image. Use this to calibrate config.py
constants before doing a full render.

Each frame is drawn as a labeled colored rectangle:
    - ANCHOR_A_FRAME      green  — left seat anchor position
    - ANCHOR_B_FRAME      cyan   — right seat anchor position
    - ANCHOR_CROP_BOTTOM  red    — crop line across each anchor frame
    - WALL_SCREEN_FRAME   yellow — b-roll wall screen
    - PIP_FRAME           orange — picture-in-picture insert
    - LOWER_THIRD_FRAME   blue   — lower third bar

Output saved to: assets/layout_preview.jpg
Open it in Preview or any image viewer to inspect.

Usage:
    python preview_layout.py
    python preview_layout.py --out my_preview.jpg
"""

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise RuntimeError("Pillow is required: pip install Pillow --break-system-packages")

from config import (
    PROJECT_ROOT,
    SET_BACKGROUND_IMAGE,
    VIDEO_RESOLUTION,
    ANCHOR_A_FRAME,
    ANCHOR_B_FRAME,
    ANCHOR_CROP_BOTTOM,
    WALL_SCREEN_FRAME,
    PIP_FRAME,
    LOWER_THIRD_FRAME,
)

DEFAULT_OUT = PROJECT_ROOT / "assets" / "layout_preview.jpg"

# ── Actual anchor content dimensions from HeyGen clip ─────────────────────────
# Run the bounding box diagnostic to get these values, then set them here.
# The preview will draw anchor rectangles at the true rendered size (fw × content_h)
# rather than the raw ANCHOR_*_FRAME (x,y,w,h) which only controls position + width.
# content_w, content_h: pixel dimensions of the person in the HeyGen clip (post-key)
CONTENT_W = 708
CONTENT_H = 896
CONTENT_ASPECT = CONTENT_H / CONTENT_W   # ~1.265 — portrait clip

def anchor_rendered_size(frame_w: int) -> tuple:
    """Return (w, h) of anchor as it will actually appear after resize.
    Anchor frames are (x, y, w) — h is derived from clip aspect ratio.
    """
    return (frame_w, int(frame_w * CONTENT_ASPECT))

# ── Frame definitions ──────────────────────────────────────────────────────────
FRAMES = [
    (WALL_SCREEN_FRAME,   "#FFE600", "WALL_SCREEN_FRAME"),
    (PIP_FRAME,           "#FF8800", "PIP_FRAME"),
    (LOWER_THIRD_FRAME,   "#4488FF", "LOWER_THIRD_FRAME"),
]


def draw_frame(draw, frame, color, label, font):
    x, y, w, h = frame
    # Filled rectangle at low opacity via outline only — use rectangle + fill with alpha
    draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
    # Label in top-left corner of frame
    draw.text((x + 6, y + 4), label, fill=color, font=font)


def draw_crop_line(draw, frame, crop_bottom, color="#FF3333"):
    """Draw the ANCHOR_CROP_BOTTOM line across an anchor frame."""
    x, y, w, h = frame
    crop_y = y + h - crop_bottom
    draw.line([(x, crop_y), (x + w, crop_y)], fill=color, width=2)
    draw.text((x + 6, crop_y + 4), f"CROP_BOTTOM ({crop_bottom}px)", fill=color)


def main():
    parser = argparse.ArgumentParser(description="Preview compositor layout")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    bg_path = Path(SET_BACKGROUND_IMAGE)
    if not bg_path.exists():
        raise FileNotFoundError(f"Background image not found: {bg_path}")

    img = Image.open(bg_path).convert("RGB")

    # Resize to VIDEO_RESOLUTION if needed
    if img.size != VIDEO_RESOLUTION:
        print(f"  Resizing background from {img.size} to {VIDEO_RESOLUTION}")
        img = img.resize(VIDEO_RESOLUTION, Image.LANCZOS)

    # Semi-transparent overlay layer
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to load a font — fall back to default if not available
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    # Draw wall screen, pip, lower third first (behind anchors)
    for (frame, color, label) in FRAMES:
        x, y, w, h = frame
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        draw.rectangle([x, y, x + w, y + h], fill=(r, g, b, 40), outline=(r, g, b, 220), width=3)
        draw.text((x + 6, y + 4), label, fill=(r, g, b, 255), font=font)

    # Draw anchor frames at actual rendered size (post-key, post-resize) — on top
    for frame, color, label in [
        (ANCHOR_A_FRAME, "#00FF44", "ANCHOR_A"),
        (ANCHOR_B_FRAME, "#00FFFF", "ANCHOR_B"),
    ]:
        x, y, fw = frame
        rw, rh = anchor_rendered_size(fw)
        # Subtract ANCHOR_CROP_BOTTOM from rendered height
        rh_cropped = max(1, rh - ANCHOR_CROP_BOTTOM)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        draw.rectangle([x, y, x + rw, y + rh_cropped],
                       fill=(r, g, b, 40), outline=(r, g, b, 220), width=3)
        draw.text((x + 6, y + 4), f"{label} ({rw}×{rh_cropped}px)", fill=(r, g, b, 255), font=font)
        # Crop line
        crop_y = y + rh_cropped
        draw.line([(x, crop_y), (x + rw, crop_y)], fill=(255, 60, 60, 255), width=2)
        draw.text((x + 6, crop_y + 4), f"desk crop", fill=(255, 60, 60, 255), font=font_small)

    # Draw pixel rulers along top and left edges
    draw_rulers(draw, VIDEO_RESOLUTION, font_small)

    # Composite overlay onto background
    img_rgba = img.convert("RGBA")
    composited = Image.alpha_composite(img_rgba, overlay)
    result = composited.convert("RGB")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(args.out), quality=92)
    print(f"Layout preview saved to: {args.out}")
    print(f"\nFrame values from config.py:")
    print(f"  ANCHOR_A_FRAME     = {ANCHOR_A_FRAME}")
    print(f"  ANCHOR_B_FRAME     = {ANCHOR_B_FRAME}")
    print(f"  ANCHOR_CROP_BOTTOM = {ANCHOR_CROP_BOTTOM}")
    print(f"  WALL_SCREEN_FRAME  = {WALL_SCREEN_FRAME}")
    print(f"  PIP_FRAME          = {PIP_FRAME}")
    print(f"  LOWER_THIRD_FRAME  = {LOWER_THIRD_FRAME}")


def draw_rulers(draw, resolution, font, interval=100):
    """Draw tick marks every 100px along top and left edges."""
    w, h = resolution
    tick_color = (200, 200, 200, 160)

    # Top ruler — horizontal ticks
    for x in range(0, w, interval):
        draw.line([(x, 0), (x, 16)], fill=tick_color, width=1)
        if x > 0:
            draw.text((x + 2, 0), str(x), fill=tick_color, font=font)

    # Left ruler — vertical ticks
    for y in range(0, h, interval):
        draw.line([(0, y), (16, y)], fill=tick_color, width=1)
        if y > 0:
            draw.text((0, y + 2), str(y), fill=tick_color, font=font)


if __name__ == "__main__":
    main()

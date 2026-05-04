"""
Fetches b-roll still images for segments in shot_plan.json where
shot_mode == "broll" and broll_clip is null.

Strategy (in order):
  1. Pexels — searches using broll_search_term from stories.json
  2. DALL-E 3 — generates an image if Pexels returns nothing usable

Downloaded images are saved to BROLL_DIR as JPEGs and the broll_clip
path is written back into shot_plan.json in-place.

Usage:
    python fetch_visuals.py              # fetch all missing broll clips
    python fetch_visuals.py --dry-run    # print what would be fetched, no API calls
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import requests

from config import (
    STORIES_JSON,
    SHOT_PLAN_JSON,
    BROLL_DIR,
    PEXELS_API_KEY,
    OPENAI_API_KEY,
    BROLL_STRATEGY,
)

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
DALLE_URL         = "https://api.openai.com/v1/images/generations"

# Pexels: landscape orientation, largest available size
PEXELS_ORIENTATION = "landscape"
PEXELS_SIZE        = "large"
PEXELS_PER_PAGE    = 5   # fetch top N, use the first one


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_story_index(stories: dict) -> dict[str, dict]:
    """
    Build a flat lookup from segment_id → story dict.
    Segment IDs are constructed the same way plan_shots.py and
    anchor_renderer.py build them: "{section}__{title[:40]}".
    Section intros have no story record and are excluded.
    """
    index = {}
    for section_data in stories["sections"]:
        section_name = section_data["section"]
        for story in section_data.get("stories", []):
            title  = story.get("title", "")
            seg_id = f"{section_name}__{title[:40]}"
            index[seg_id] = story
    return index


def broll_segments(plan: dict) -> list[dict]:
    """Return segments that need a b-roll image fetched."""
    return [
        seg for seg in plan["segments"]
        if seg.get("shot_mode") == "broll" and not seg.get("broll_clip")
    ]


# ── Pexels ─────────────────────────────────────────────────────────────────────

def fetch_pexels(query: str) -> str | None:
    """
    Search Pexels for a still image matching query.
    Returns the URL of the best result, or None if nothing usable.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    params  = {
        "query":       query,
        "orientation": PEXELS_ORIENTATION,
        "size":        PEXELS_SIZE,
        "per_page":    PEXELS_PER_PAGE,
    }
    try:
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        # Prefer "large2x" (1880 × 1253) → "large" → "original"
        src = photos[0]["src"]
        return src.get("large2x") or src.get("large") or src.get("original")
    except requests.RequestException as exc:
        print(f"    Pexels request failed: {exc}")
        return None


# ── DALL-E 3 fallback ──────────────────────────────────────────────────────────

def fetch_dalle(query: str) -> str | None:
    """
    Generate a photorealistic still image via DALL-E 3.
    Returns a URL to the generated image, or None on failure.
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":   "dall-e-3",
        "prompt":  (
            f"Photorealistic news broadcast b-roll image: {query}. "
            "Wide shot, neutral lighting, no text or overlays."
        ),
        "n":       1,
        "size":    "1792x1024",   # closest DALL-E 3 size to 16:9
        "quality": "standard",
        "response_format": "url",
    }
    try:
        resp = requests.post(DALLE_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["data"][0]["url"]
    except requests.RequestException as exc:
        print(f"    DALL-E request failed: {exc}")
        return None


# ── Download ───────────────────────────────────────────────────────────────────

def download_image(url: str, dest: Path) -> bool:
    """Download an image from url to dest. Returns True on success."""
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except requests.RequestException as exc:
        print(f"    Download failed: {exc}")
        return False


# ── Per-segment fetch ──────────────────────────────────────────────────────────

def fetch_for_segment(seg: dict, story: dict | None, dry_run: bool) -> str | None:
    """
    Attempt to fetch a b-roll image for one segment.
    Returns the local file path string on success, None on failure.
    """
    seg_id = seg["segment_id"]

    # Derive search term: prefer story's broll_search_term, fall back to headline
    if story and story.get("broll_search_term"):
        query = story["broll_search_term"]
        source = "broll_search_term"
    else:
        query = seg.get("lower_third_headline", seg_id)
        source = "lower_third_headline (fallback)"

    print(f"  [{seg_id}]")
    print(f"    query ({source}): {query!r}")

    if dry_run:
        print("    [dry-run] skipping API calls")
        return None

    dest_stem = seg_id.replace(" ", "_").replace("/", "-")
    image_url = None
    used_strategy = None

    for strategy in BROLL_STRATEGY:
        if strategy == "pexels":
            image_url = fetch_pexels(query)
            if image_url:
                used_strategy = "pexels"
                break
            print("    Pexels: no results, trying next strategy...")

        elif strategy == "dalle":
            image_url = fetch_dalle(query)
            if image_url:
                used_strategy = "dalle"
                break
            print("    DALL-E: generation failed, no further fallback.")

    if not image_url:
        print(f"    ✗ No image found for segment.")
        return None

    dest = BROLL_DIR / f"{dest_stem}.jpg"
    success = download_image(image_url, dest)
    if success:
        print(f"    ✓ Saved ({used_strategy}): {dest.name}")
        return str(dest)
    return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch b-roll images for shot_plan.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making any API calls.",
    )
    args = parser.parse_args()

    plan    = load_json(SHOT_PLAN_JSON)
    stories = load_json(STORIES_JSON)

    story_index = build_story_index(stories)
    targets     = broll_segments(plan)

    if not targets:
        print("No broll segments with missing clips found in shot_plan.json.")
        return 0

    print(f"Found {len(targets)} broll segment(s) to fetch.\n")

    filled  = 0
    skipped = 0

    for seg in targets:
        seg_id = seg["segment_id"]
        story  = story_index.get(seg_id)

        if not story and not seg.get("lower_third_headline"):
            print(f"  [{seg_id}] — no story or headline found, skipping.")
            skipped += 1
            continue

        clip_path = fetch_for_segment(seg, story, dry_run=args.dry_run)

        if clip_path:
            # Write back into the plan in-place
            seg["broll_clip"] = clip_path
            filled += 1

    if not args.dry_run and filled > 0:
        save_json(SHOT_PLAN_JSON, plan)
        print(f"\nshot_plan.json updated — {filled} broll_clip path(s) filled.")
    elif args.dry_run:
        print(f"\n[dry-run] Would have attempted {len(targets)} fetch(es).")
    else:
        print(f"\nNo clips were successfully fetched.")

    if skipped:
        print(f"{skipped} segment(s) skipped (no query source available).")

    return 0 if (filled == len(targets) - skipped) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Trim story bodies in stories.json to a target character length.

Reads stories.json, trims each body to the first sentence boundary
at or after TARGET_MIN characters, and writes shortstories.json.

Algorithm: inverted pyramid — the most newsworthy content leads,
so trimming from the end is a principled cut.

Pipeline position: run after script_generator.py, before newsreel_tts.py.
"""

import json
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

TARGET_MIN = 580   # trim to first sentence end at or after this character count
INPUT_FILE  = config.ANTHROPIC_JSON_FILE    # stories.json
OUTPUT_FILE = config.ANTHROPIC_SHORT_JSON_FILE   # shortstories.json


# ---------------------------------------------------------------------------
# Trim logic
# ---------------------------------------------------------------------------

def trim_body(body: str, target_min: int = TARGET_MIN) -> str:
    """Trim body to the first sentence boundary at or after target_min chars.

    If the body is already at or under target_min, return it unchanged.
    If no sentence boundary is found after target_min, return the full body.
    """
    if len(body) <= target_min:
        return body

    # Find the first period at or after target_min
    pos = body.find(".", target_min)
    if pos == -1:
        # No period found after target — return full body rather than truncate mid-sentence
        return body

    # Include the period, strip trailing whitespace
    return body[: pos + 1].strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found. Run script_generator.py first.")
        return 1

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_before = 0
    total_after  = 0

    for section in data.get("sections", []):
        section_name = section.get("section", "unnamed")
        for story in section.get("stories", []):
            body = story.get("body", "")
            trimmed = trim_body(body)
            story["body"] = trimmed
            total_before += len(body)
            total_after  += len(trimmed)
            saved = len(body) - len(trimmed)
            if saved > 0:
                print(f"  [{section_name}] {story['title'][:50]} — {len(body)} → {len(trimmed)} chars (-{saved})")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nTotal characters: {total_before:,} → {total_after:,} "
          f"({total_before - total_after:,} saved, "
          f"{100*(total_before-total_after)//total_before}% reduction)")
    print(f"Written to: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

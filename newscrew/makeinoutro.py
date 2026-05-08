#!/usr/bin/env python3
"""
makeinoutro.py — Generate intro and outro MP3 clips for the current episode
using ElevenLabs TTS.

Output files:
    episodes/<EPISODE_DIR>/intro.mp3
    episodes/<EPISODE_DIR>/close.mp3

These paths are read by build_video.py via INTRO_AUDIO_CLIP / CLOSE_AUDIO_CLIP
in config.py. Run this script once per episode (or whenever the intro/outro
copy changes) before running build_video.py.

Usage:
    python makeinoutro.py
"""

import base64
import json
from pathlib import Path

from elevenlabs.client import ElevenLabs
import config

# ── ElevenLabs client ──────────────────────────────────────────────────────────
client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)


# ── Date helpers ───────────────────────────────────────────────────────────────

def spoken_day(day_of_month: int) -> str:
    ordinals = {
        1:"first", 2:"second", 3:"third", 4:"fourth", 5:"fifth",
        6:"sixth", 7:"seventh", 8:"eighth", 9:"ninth", 10:"tenth",
        11:"eleventh", 12:"twelfth", 13:"thirteenth", 14:"fourteenth",
        15:"fifteenth", 16:"sixteenth", 17:"seventeenth", 18:"eighteenth",
        19:"nineteenth", 20:"twentieth", 21:"twenty-first", 22:"twenty-second",
        23:"twenty-third", 24:"twenty-fourth", 25:"twenty-fifth",
        26:"twenty-sixth", 27:"twenty-seventh", 28:"twenty-eighth",
        29:"twenty-ninth", 30:"thirtieth", 31:"thirty-first",
    }
    return ordinals[day_of_month]


def spoken_year(yyyy: int) -> str:
    tens_words = {
        0:"", 1:"ten", 2:"twenty", 3:"thirty", 4:"forty", 5:"fifty",
        6:"sixty", 7:"seventy", 8:"eighty", 9:"ninety"
    }
    ones_words = {
        0:"", 1:"one", 2:"two", 3:"three", 4:"four", 5:"five",
        6:"six", 7:"seven", 8:"eight", 9:"nine", 10:"ten",
        11:"eleven", 12:"twelve", 13:"thirteen", 14:"fourteen",
        15:"fifteen", 16:"sixteen", 17:"seventeen", 18:"eighteen",
        19:"nineteen"
    }
    century   = yyyy // 100
    remainder = yyyy % 100
    century_spoken = tens_words[century // 10]
    if century % 10:
        century_spoken += f" {ones_words[century % 10]}"
    century_spoken = century_spoken.strip()
    if remainder == 0:
        return f"{century_spoken} hundred"
    elif remainder < 20:
        return f"{century_spoken} {ones_words[remainder]}"
    else:
        tens = remainder // 10
        ones = remainder % 10
        remainder_spoken = tens_words[tens]
        if ones:
            remainder_spoken += f"-{ones_words[ones]}"
        return f"{century_spoken} {remainder_spoken}"


def spoken_date(dt) -> str:
    return f"{dt.strftime('%B')} {spoken_day(dt.day)}"


# ── Date range from config (stays in sync with episode) ───────────────────────
_end        = config.END_DATE
_start      = config.START_DATE
_date_range = f"{spoken_date(_start)} through {spoken_date(_end)}, {spoken_year(_end.year)}"

# ── Resolve on-air anchor names from config ────────────────────────────────────
_seat_a = next((a["id"] for a in config.ANCHORS if a.get("seat") == "a"), "Saskia")
_seat_b = next((a["id"] for a in config.ANCHORS if a.get("seat") == "b"), "Albert")

# ── Copy ───────────────────────────────────────────────────────────────────────
INTRO = (
    "Welcome to our weekly AI News Update "
    f"for the week of {_date_range}. "
    "We bring stories on the latest tech releases, directions in AI architecture, "
    "applications of AI for productivity, and the impact of AI on the world. "
    f"Let's go to our hosts, {_seat_a} and {_seat_b}."
)

OUTRO = (
    "That is your weekly summary of the news in artificial intelligence. "
    "Thank you for listening. We'll see you next week."
)


# ── Render function ────────────────────────────────────────────────────────────

def render_clip(text: str, voice_id: str, out_path: Path) -> None:
    """Call ElevenLabs, save MP3 + timestamps."""
    timestamp_path = out_path.with_name(out_path.stem + "_timestamps.json")

    print(f"  Rendering {out_path.name} ...")
    print(f"    Text: {text[:80]}{'...' if len(text) > 80 else ''}")

    response = client.text_to_speech.convert_with_timestamps(
        text=text,
        voice_id=voice_id,
        model_id=config.EL_MODEL_ID,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "wb") as f:
        f.write(base64.b64decode(response.audio_base_64))

    alignment_data = {
        "characters":                      response.alignment.characters,
        "character_start_times_seconds":   response.alignment.character_start_times_seconds,
        "character_end_times_seconds":     response.alignment.character_end_times_seconds,
    }
    with open(timestamp_path, "w") as f:
        json.dump(alignment_data, f, indent=2)

    print(f"    Saved: {out_path}")
    print(f"    Timestamps: {timestamp_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\nGenerating intro/outro for episode: {config.EPISODE_DIR.name}")
    print(f"  Date range: {_date_range}")
    print(f"  Hosts: {_seat_a} and {_seat_b}\n")

    render_clip(INTRO, config.VOICE_MAIN, config.INTRO_AUDIO_CLIP)
    render_clip(OUTRO, config.VOICE_MAIN, config.CLOSE_AUDIO_CLIP)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

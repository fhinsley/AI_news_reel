#!/usr/bin/env python3

import base64
import json
from pathlib import Path
from elevenlabs.client import ElevenLabs
import config

PAUSE = '<break time="1s" />'

# ---------------------------------------------------------------------------
# ElevenLabs client
# ---------------------------------------------------------------------------
client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

def spoken_day(day_of_month: int) -> str:
    """Convert a day of month to spoken ordinal form.
    e.g. 1 -> 'first', 30 -> 'thirtieth'
    """
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
    """Convert a year to fully spoken form.
    e.g. 2026 -> 'twenty twenty-six'
    """
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
    """Convert a date to fully spoken form.
    e.g. datetime(2026, 3, 30) -> 'March thirtieth'
    """
    return f"{dt.strftime('%B')} {spoken_day(dt.day)}"

from datetime import datetime, timedelta
_end   = datetime.today() - timedelta(days=1)
_start = _end - timedelta(days=7)
_date_range = f"{spoken_date(_start)} through {spoken_date(_end)}, {spoken_year(_end.year)}"


# ---------------------------------------------------------------------------
# Placeholder anchor copy — replace with real text when ready
# ---------------------------------------------------------------------------
INTRO = (
    "Welcome to the AI Newsreel "
    f"for the week of {_date_range}. "
    "this week, we have news about the latest tech releases, directions in AI architecture, applications of AI for productivity, and the impact of AI on the world. "
    "Let's get started."
)

OUTRO = (
    "That is your weekly summary of the news in artificial intelligence. "
    "Thank you for listening. We'll see you next week."
)

def render_clip(text: str, voice_id: str, out_stem: str) -> None:
    """Call ElevenLabs, save audio + timestamps, print confirmation."""
    audio_path     = Path(config.WEEK_FOLDER) / f"{out_stem}.mp3"
    timestamp_path = Path(config.WEEK_FOLDER) / f"{out_stem}_timestamps.json"

    print(f"  Rendering {out_stem} ...")

    response = client.text_to_speech.convert_with_timestamps(
        text=text,
        voice_id=voice_id,
        model_id=config.EL_MODEL_ID,
    )

    # Audio
    with open(audio_path, "wb") as f:
        f.write(base64.b64decode(response.audio_base_64))

    # Timestamps
    alignment_data = {
        "characters":                      response.alignment.characters,
        "character_start_times_seconds":   response.alignment.character_start_times_seconds,
        "character_end_times_seconds":     response.alignment.character_end_times_seconds,
    }
    with open(timestamp_path, "w") as f:
        json.dump(alignment_data, f, indent=2)

    print(f"    Audio:      {audio_path}")
    print(f"    Timestamps: {timestamp_path}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:

    # --- 00 Intro ---
    #render_clip(INTRO, config.EL_VOICE_MAIN, "00_intro")

    print(INTRO)

    # render_clip(OUTRO, config.EL_VOICE_MAIN, "99_outro")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

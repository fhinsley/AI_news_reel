#!/usr/bin/env python3
"""Multi-voice TTS generation for the AI Newsreel.

Reads stories.json and produces one audio clip + one timestamp file
per segment, sequentially numbered for correct assembly order:

    00_intro
    01_section1
    02_section2
    03_section3
    04_section4
    99_outro
"""

import base64
import json
from pathlib import Path

from elevenlabs.client import ElevenLabs

import config

# ---------------------------------------------------------------------------
# ElevenLabs client
# ---------------------------------------------------------------------------

client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

# ---------------------------------------------------------------------------
# Placeholder anchor copy — replace with real text when ready
# ---------------------------------------------------------------------------

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

_date_range = f"{spoken_date(config.START_DATE)} through {spoken_date(config.END_DATE)}, {spoken_year(config.END_DATE.year)}"

INTRO = (
    "Welcome to the AI Newsreel "
    f"for the week of {_date_range}. "
    "This week, we have news about the latest tech releases, directions in AI architecture, applications of AI for productivity, and the impact of AI on the world. "
    "Let's get started."
)

OUTRO = (
    "That is your weekly summary of the news in artificial intelligence. "
    "Thank you for listening. We'll see you next week."
)

# ---------------------------------------------------------------------------
# Map sections to their correspondent voices in broadcast order
# ---------------------------------------------------------------------------

SECTION_VOICES = [
    ("Core Tech Releases",            config.EL_VOICE_KIM), 
    ("Directions in AI Architecture", config.EL_VOICE_RYAN),
    ("AI For Productivity",           config.EL_VOICE_MARCOS),
    ("World Impact",                  config.EL_VOICE_CLARA),
]
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_sentence_case(text: str) -> str:
    """Convert a title to sentence case for natural spoken delivery.
    e.g. 'Meta Debuts Muse Spark' -> 'Meta debuts Muse Spark'
    Proper nouns will be lowercased — ElevenLabs reads this more naturally
    than Title Case, which causes stilted word-by-word prosody.
    """
    if not text:
        return text
    return text[0].upper() + text[1:].lower()


def build_section_text(section_name: str, stories: list) -> str:
    """Assemble spoken text for one correspondent's clip.

    Uses SSML break tags for reliable 1-second pauses between:
      - section name and first story title
      - story title and story body
      - stories
    Periods ensure the voice drops naturally before each pause.
    Story titles are converted to sentence case for natural prosody.
    """
    PAUSE = '<break time="1s" />'

    def ensure_period(text: str) -> str:
        text = text.strip()
        if text and text[-1] not in ".!?":
            text += "."
        return text

    parts = []

    # Section name first, period so voice drops before pause
    parts.append(ensure_period(section_name))

    for story in stories:
        title = to_sentence_case(story.get("title", "").strip())
        body  = story.get("body",  "").strip()
        # Title in sentence case with period, break, then body with period
        parts.append(f"{ensure_period(title)} {PAUSE} {ensure_period(body)}")

    # 1s break between section name and stories, and between stories
    return f" {PAUSE} ".join(parts)

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
    stories_file = config.ANTHROPIC_SHORT_JSON_FILE

    if not stories_file.exists():
        print(f"ERROR: {stories_file} not found.")
        print("Run script_generator.py first.")
        return 1

    with open(stories_file, "r") as f:
        data = json.load(f)

    # Index sections by name for easy lookup
    sections_by_name = {
        s["section"]: s["stories"]
        for s in data.get("sections", [])
    }

    print(f"\nGenerating audio for week of: {data.get('week_of', 'unknown')}")
    print(f"Output folder: {config.WEEK_FOLDER}\n")

    # --- 00 Intro ---
    render_clip(INTRO, config.EL_VOICE_MAIN, "00_intro")

    # --- 01-04 Section correspondents ---
    for seq, (section_name, voice_id) in enumerate(SECTION_VOICES, start=1):
        stories = sections_by_name.get(section_name)
        if not stories:
            print(f"  WARNING: No stories found for section '{section_name}' — skipping.")
            continue
        text     = build_section_text(section_name, stories)
        out_stem = f"0{seq}_{section_name.lower().replace(' ', '_').replace('/', '_')}"
        render_clip(text, voice_id, out_stem)

    # --- 99 Outro ---
    render_clip(OUTRO, config.EL_VOICE_MAIN, "99_outro")

    print("\nAll clips rendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Multi-voice TTS generation for the AI Newsreel.

Reads stories.json and produces one audio clip + one timestamp file
per segment, sequentially numbered for correct assembly order:

    00_clancy_intro
    01_isabella_section1
    02_burt_section2
    03_kim_section3
    04_mia_section4
    99_clancy_outro
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

CLANCY_INTRO = (
    "Welcome to the AI Newsreel. "
    "I'm Clancy, and this is your weekly summary of the news in AI "
    f"for the week of {config.OPENING_TITLE.split('Week of')[-1].strip()}. "
    "This week we have stories on Core Tech Releases, "
    "Directions in AI Architecture, "
    "AI For Productivity, "
    "and World Impact. "
    "Let's get started."
)

CLANCY_OUTRO = (
    "That is your weekly summary of the news in artificial intelligence. "
    "I'm Clancy. We'll see you next week."
)

# ---------------------------------------------------------------------------
# Map sections to their correspondent voices in broadcast order
# ---------------------------------------------------------------------------

SECTION_VOICES = [
    ("Core Tech Releases",            config.EL_VOICE_SECTION1), 
    ("Directions in AI Architecture", config.EL_VOICE_SECTION2),
    ("AI For Productivity",           config.EL_VOICE_SECTION3),
    ("World Impact",                  config.EL_VOICE_SECTION4),
]
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_section_text(section_name: str, stories: list) -> str:
    """Assemble spoken text for one correspondent's clip.

    Uses SSML break tags for reliable 1-second pauses between:
      - section name and first story title
      - story title and story body
      - stories
    Periods ensure the voice drops naturally before each pause.
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
        title = story.get("title", "").strip()
        body  = story.get("body",  "").strip()
        # Title with period, break, then body with period
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
    stories_file = config.ANTHROPIC_JSON_FILE

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

    # --- 00 Clancy intro ---
    render_clip(CLANCY_INTRO, config.EL_VOICE_MAIN, "00_clancy_intro")

    # --- 01-04 Section correspondents ---
    for seq, (section_name, voice_id) in enumerate(SECTION_VOICES, start=1):
        stories = sections_by_name.get(section_name)
        if not stories:
            print(f"  WARNING: No stories found for section '{section_name}' — skipping.")
            continue
        text     = build_section_text(section_name, stories)
        out_stem = f"0{seq}_{section_name.lower().replace(' ', '_').replace('/', '_')}"
        render_clip(text, voice_id, out_stem)

    # --- 99 Clancy outro ---
    render_clip(CLANCY_OUTRO, config.EL_VOICE_MAIN, "99_clancy_outro")

    print("\nAll clips rendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

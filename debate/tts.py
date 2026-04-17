#!/usr/bin/env python3
"""Multi-voice TTS generation for the Two-Sides debate pipeline.

Structural mirror of scripts/newsreel_tts.py.

Reads story.json and produces one audio clip + one timestamp file
per segment, numbered to match DEBATE_CLIP_MANIFEST:

    00_anchor_intro
    01_opener
    02_responder        (rebuttal + argument concatenated with a pause between)
    03_opener_rebuttal
    04_anchor_outro
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
# Voice map
# ---------------------------------------------------------------------------

VOICE_MAP = {
    "anchor": config.EL_VOICE_ANCHOR,
    "left":   config.EL_VOICE_LEFT,
    "right":  config.EL_VOICE_RIGHT,
}

# SSML pause between rebuttal and argument halves of the responder's turn —
# same break-tag pattern as newsreel_tts.py build_section_text()
REBUTTAL_ARGUMENT_PAUSE = '<break time="1s" />'

# ---------------------------------------------------------------------------
# Resilient key resolution for responder_turn fields
#
# Claude occasionally returns these fields under alternate key names despite
# the prompt specifying the canonical names.  The canonical name is always
# first in each list; alternates are tried in order.  A warning is printed
# whenever a non-canonical key is used so the prompt can be tightened.
# ---------------------------------------------------------------------------

_RESPONDER_KEY_CANDIDATES = {
    "rebuttal": [
        "rebuttal",
        "rebuttal_argument",
        "counter_argument",
        "response",
        "counter",
        "rebuttal_text",
    ],
    "argument": [
        "argument",
        "affirmative_argument",
        "own_argument",
        "case",
        "closing_argument",
        "position",
        "argument_text",
    ],
}


def _resolve_responder_key(d: dict, field: str) -> str:
    """Return the string value for a responder_turn field regardless of key name.

    Tries the canonical name first, then known alternates.
    Raises KeyError with a diagnostic message listing the actual keys present
    if nothing matches — so the failure is immediately actionable.
    """
    for candidate in _RESPONDER_KEY_CANDIDATES[field]:
        if candidate in d:
            canonical = _RESPONDER_KEY_CANDIDATES[field][0]
            if candidate != canonical:
                print(
                    f"  WARNING: responder_turn field '{field}' found under "
                    f"non-canonical key '{candidate}' instead of '{canonical}'. "
                    f"Tighten the system prompt to prevent this drift."
                )
            return d[candidate]
    raise KeyError(
        f"responder_turn is missing the '{field}' field. "
        f"Actual keys present: {list(d.keys())}. "
        f"Checked candidates: {_RESPONDER_KEY_CANDIDATES[field]}"
    )


# ---------------------------------------------------------------------------
# Segment assembly
# ---------------------------------------------------------------------------

def build_segments(data: dict) -> list[dict]:
    """Return ordered list of segments to synthesize.

    Each dict: {stem, text, voice_key, label}
    Order matches DEBATE_CLIP_MANIFEST exactly.

    The responder's rebuttal and argument are joined with an SSML pause
    so they render as one continuous audio clip with a natural beat between.
    """
    debate         = data["debate"]
    opener_side    = data["opener_side"]
    responder_side = data["responder_side"]

    responder_turn = debate["responder_turn"]
    responder_text = (
        _resolve_responder_key(responder_turn, "rebuttal").rstrip()
        + " "
        + REBUTTAL_ARGUMENT_PAUSE
        + " "
        + _resolve_responder_key(responder_turn, "argument").lstrip()
    )

    return [
        {
            "stem":      "00_anchor_intro",
            "text":      debate["anchor_intro"]["script"],
            "voice_key": "anchor",
            "label":     "Anchor intro",
        },
        {
            "stem":      "01_opener",
            "text":      debate["opener_argument"]["script"],
            "voice_key": opener_side,
            "label":     f"Opener ({opener_side})",
        },
        {
            "stem":      "02_responder",
            "text":      responder_text,
            "voice_key": responder_side,
            "label":     f"Responder ({responder_side}) — rebuttal + argument",
        },
        {
            "stem":      "03_opener_rebuttal",
            "text":      debate["opener_rebuttal"]["script"],
            "voice_key": opener_side,
            "label":     f"Opener rebuttal ({opener_side})",
        },
        {
            "stem":      "04_anchor_outro",
            "text":      debate["anchor_outro"]["script"],
            "voice_key": "anchor",
            "label":     "Anchor outro",
        },
    ]


# ---------------------------------------------------------------------------
# Render — identical to newsreel_tts.py render_clip()
# ---------------------------------------------------------------------------

def render_clip(text: str, voice_id: str, out_stem: str) -> None:
    """Call ElevenLabs, save audio + timestamps, print confirmation."""
    audio_path     = Path(config.WEEK_FOLDER) / f"{out_stem}.mp3"
    timestamp_path = Path(config.WEEK_FOLDER) / f"{out_stem}_timestamps.json"

    print(f"  Rendering {out_stem} ...")

    response = client.text_to_speech.convert_with_timestamps(
        text     = text,
        voice_id = voice_id,
        model_id = config.EL_MODEL_ID,
    )

    with open(audio_path, "wb") as f:
        f.write(base64.b64decode(response.audio_base_64))

    alignment_data = {
        "characters":                    response.alignment.characters,
        "character_start_times_seconds": response.alignment.character_start_times_seconds,
        "character_end_times_seconds":   response.alignment.character_end_times_seconds,
    }
    with open(timestamp_path, "w") as f:
        json.dump(alignment_data, f, indent=2)

    print(f"    Audio:      {audio_path}")
    print(f"    Timestamps: {timestamp_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not config.DEBATE_JSON_FILE.exists():
        print(f"ERROR: {config.DEBATE_JSON_FILE} not found.")
        print("Run script_generator.py first.")
        return 1

    with open(config.DEBATE_JSON_FILE, "r") as f:
        data = json.load(f)

    segments = build_segments(data)

    print(f"\nGenerating audio for: {data.get('proposition', 'unknown proposition')}")
    print(f"Output folder: {config.WEEK_FOLDER}\n")

    failures = []
    for seg in segments:
        print(f"\n[{seg['label']}]")
        voice_id = VOICE_MAP.get(seg["voice_key"])
        if not voice_id:
            print(f"  ERROR: No voice configured for key '{seg['voice_key']}'")
            failures.append(seg["stem"])
            continue
        try:
            render_clip(seg["text"], voice_id, seg["stem"])
        except Exception as exc:
            print(f"  ERROR rendering {seg['stem']}: {exc}")
            failures.append(seg["stem"])

    if failures:
        print(f"\n✗ {len(failures)} segment(s) failed: {failures}")
        return 1

    print("\nAll clips rendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

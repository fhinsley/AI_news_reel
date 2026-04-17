"""config.py
Configuration for the Two-Sides debate pipeline.
Structural mirror of scripts/config.py.
"""

import os
import json
import random
from pathlib import Path
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Paths — same anchor pattern as config.py
# ---------------------------------------------------------------------------

SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

def project_path(*parts):
    return str(PROJECT_ROOT.joinpath(*parts))

# ---------------------------------------------------------------------------
# Date / folder — reuses the same weekly-folder convention
# ---------------------------------------------------------------------------

END_DATE   = datetime.today() - timedelta(days=1)
START_DATE = END_DATE - timedelta(days=6)

WEEK_FOLDER_NAME = END_DATE.strftime("%m%d%y_debate")
WEEK_FOLDER      = project_path(WEEK_FOLDER_NAME)

# ---------------------------------------------------------------------------
# API keys — same env-var pattern, same RuntimeError guard
# ---------------------------------------------------------------------------

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set.")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

ANTHROPIC_MODEL      = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 16000      # increased — debate format is longer than news format

DEBATE_JSON_FILE = Path(project_path(WEEK_FOLDER_NAME, "story.json"))

# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------

EL_MODEL_ID = "eleven_multilingual_v2"

# Two-Sides voices.
# Current assignments reuse newsreel voices for quick testing.
# Swap for voices with more rhetorical character once you've settled on tone.
EL_VOICE_ANCHOR = "FLpz0UhC9a7CIfUSBo6S"   # Clancy — neutral anchor
EL_VOICE_LEFT   = "O7LV5fxosQChiBE7l6Wz"   # Kim    — left debater
EL_VOICE_RIGHT  = "ya031zGCAxyRGrvB3or9"   # Ryan   — right debater

# ---------------------------------------------------------------------------
# News sources passed into the Claude prompt
# ---------------------------------------------------------------------------

LEFT_SOURCES  = ["CNN", "MSNBC", "NPR", "The Atlantic", "Washington Post"]
RIGHT_SOURCES = ["Fox News", "New York Post", "Wall Street Journal", "Breitbart", "The Federalist"]

# ---------------------------------------------------------------------------
# Debate structure parameters
# ---------------------------------------------------------------------------

# Who opens the debate: "left" or "right".
#
# IMPORTANT: This is resolved in priority order:
#   1. story.json (if it already exists for this week) — keeps all pipeline
#      stages in sync when re-running tts.py or build_video.py independently.
#   2. Random choice — used only on a fresh script_generator.py run.
#
# This prevents the bug where a second import of config.py calls random.choice
# again and produces a different side than what story.json records, causing
# wrong flag videos and mismatched voice assignments.

def _resolve_opener_side() -> str:
    """Read opener_side from story.json if it exists; otherwise pick randomly."""
    story_file = Path(project_path(WEEK_FOLDER_NAME, "story.json"))
    if story_file.exists():
        try:
            with open(story_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            side = d.get("opener_side", "").strip().lower()
            if side in ("left", "right"):
                return side
        except Exception:
            pass  # Malformed JSON — fall through to random
    return random.choice(["left", "right"])

DEBATE_OPENER = _resolve_opener_side()


# Word count targets per segment — tune to control pacing and API cost.
# (min, max) tuples. Tighter windows = shorter segments = fewer tokens.
OPENER_WORDS           = (160, 200)   # opening argument
REBUTTAL_WORDS         = (80,  120)   # rebuttal portion of the responder's combined turn
ARGUMENT_WORDS         = (140, 180)   # affirmative argument portion of responder's turn
CLOSING_REBUTTAL_WORDS = (60,  100)   # opener's closing rebuttal to responder's argument
ANCHOR_INTRO_WORDS     = (50,   70)
ANCHOR_OUTRO_WORDS     = (30,   50)

# ---------------------------------------------------------------------------
# Rebuttal strategy weights
#
# Controls how each debater handles the opponent's accusations.
# Passed directly into the prompt as instructions to Claude.
# Must sum to 1.0.
#
#   full_denial_weight     — flat rejection: the accusation is wrong, here's why
#   concede_pivot_weight   — accept the fact, contest its meaning or importance
#   genuine_concede_weight — grant the point entirely, move past it
#
# High concede_pivot  → sophisticated, Socratic, credibility-building tone
# High full_denial    → combative, talk-radio, fire-and-brimstone tone
# High genuine_concede → unusually magnanimous; use sparingly for realism
# ---------------------------------------------------------------------------

REBUTTAL_STRATEGY = {
    "full_denial_weight":       0.35,
    "concede_pivot_weight":     0.45,
    "genuine_concede_weight":   0.20,
}

# Validate at import time so misconfiguration fails loudly
_weight_sum = sum(REBUTTAL_STRATEGY.values())
if abs(_weight_sum - 1.0) > 0.001:
    raise ValueError(
        f"REBUTTAL_STRATEGY weights must sum to 1.0 — currently {_weight_sum:.3f}"
    )

# ---------------------------------------------------------------------------
# Video manifest — 5-segment debate structure
# Opener/responder roles assigned dynamically from DEBATE_OPENER above.
# ---------------------------------------------------------------------------

_CLOSER = "right" if DEBATE_OPENER == "left" else "left"

DEBATE_CLIP_MANIFEST = [
    ("00_anchor_intro",    "anchor"),
    ("01_opener",          DEBATE_OPENER),
    ("02_responder",       _CLOSER),
    ("03_opener_rebuttal", DEBATE_OPENER),
    ("04_anchor_outro",    "anchor"),
]

# Silent visual beat inserted between opener and responder in the video
FRAMING_CARD_DURATION = 4.0   # seconds

# ---------------------------------------------------------------------------
# Video / overlay settings — mirrors config.py style dict shape
# ---------------------------------------------------------------------------

FONT             = "Arial"
BACKGROUND_COLOR = (15, 20, 40)

LEFT_COLOR   = (41, 121, 255)
RIGHT_COLOR  = (200, 50,  50)
ANCHOR_COLOR = (200, 200, 200)

SIDE_LABEL_STYLE   = {"font_size": 60, "color": "white",  "duration": 3, "position": "center"}
ANCHOR_STYLE       = {"font_size": 48, "color": "white",  "duration": 4, "position": "center"}
HEADLINE_STYLE     = {"font_size": 52, "color": "white",  "duration": 5, "position": "center"}
PROPOSITION_STYLE  = {"font_size": 44, "color": "yellow", "duration": 6, "position": "center"}
FRAMING_CARD_STYLE = {"font_size": 40, "color": "white",  "duration": FRAMING_CARD_DURATION, "position": "center"}

OVERLAY_BG_COLOR    = (0, 0, 0)
OVERLAY_BG_OPACITY  = 0.6
OVERLAY_BG_PADDING  = 20
OVERLAY_ANTICIPATION = 0.4

# ---------------------------------------------------------------------------
# Background stock videos
# ---------------------------------------------------------------------------

# Flag videos per side — tinted in build_video.py.
LEFT_FLAG_VIDEO  = project_path("stock_videos", "OldGloryL.mp4")
RIGHT_FLAG_VIDEO = project_path("stock_videos", "OldGloryR.mp4")

# Tint colors and opacities per side — RGB tuple + opacity (0.0-1.0)
# Opacity around 0.25-0.35 gives a visible wash without obscuring the flag.
FLAG_TINTS = {
    "left":   {"color": (30,  80, 200), "opacity": 0.30},
    "right":  {"color": (200, 40,  40), "opacity": 0.30},
    "anchor": {"color": (80,  80,  90), "opacity": 0.18},
}

SECTION_VIDEOS = {
    "anchor": project_path("stock_videos", "whitehousedome.mp4"),
    "left":   LEFT_FLAG_VIDEO,
    "right":  RIGHT_FLAG_VIDEO,
}

# ---------------------------------------------------------------------------
# Audio timing
# ---------------------------------------------------------------------------

VIDEO_INTRO_SILENCE      = 2.0
VIDEO_INTER_CLIP_SILENCE = 1.0

AUDIO_CODEC = "aac"

# ---------------------------------------------------------------------------
# SRT caption settings — mirrors config.py
# ---------------------------------------------------------------------------

SRT_TARGET_WORDS = 6      # aim for this many words per caption line
SRT_MAX_DURATION = 3.0    # never let a caption run longer than this (seconds)
SRT_MIN_DURATION = 0.5    # never shorter than this

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

OUTPUT_VIDEO = project_path(WEEK_FOLDER_NAME, "Debate.mp4")

# ---------------------------------------------------------------------------
# Topic history — prevents repeated topics across runs
# ---------------------------------------------------------------------------

# Stored at project root so it persists across all weekly folders and runs.
TOPIC_HISTORY_FILE = PROJECT_ROOT / "debate_topic_history.json"

# How many days back to look when excluding recent topics.
# At 2-3 runs/day this covers ~42-63 debates — plenty of breathing room.
TOPIC_EXCLUSION_DAYS = 14

# Hard cap on stored entries — keeps the file from growing forever.
# Entries older than TOPIC_EXCLUSION_DAYS are pruned automatically each run.
TOPIC_HISTORY_MAX = 200

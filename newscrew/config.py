import os
from pathlib import Path
from datetime import date, timedelta

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
WEEKLY_ROOT  = PROJECT_ROOT / "episodes"


# TODO: automate episode directory creation based on current date, and move completed episode folders to an archive directory
END_DATE     = date(2026, 5, 4)   # update each week
EPISODE_DIR  = WEEKLY_ROOT / END_DATE.strftime("%m%d%y_Episode")

STORIES_JSON      = EPISODE_DIR / "stories.json"
ANCHOR_JOBS_JSON  = EPISODE_DIR / "anchor_jobs.json"   # HeyGen job tracking
BROLL_DIR         = EPISODE_DIR / "broll"
ANCHOR_CLIPS_DIR  = EPISODE_DIR / "anchor_clips"
OUTPUT_VIDEO      = EPISODE_DIR / "News.mp4"

#GET API KEY FROM ENVIRONMENT VARIABLES
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set. Please configure your API key securely.")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set. Please configure your API key securely.")

HEYGEN_API_BASE = "https://api.heygen.com"
HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY")
if not HEYGEN_API_KEY:
    raise RuntimeError("HEYGEN_API_KEY environment variable is not set. Please configure your API key securely.")

# Anchor definitions — add/swap avatars here without touching pipeline code.
# "seat" determines on-screen position and shot mode:
#   "a" → left seat  → solo_a → ANCHOR_A_FRAME
#   "b" → right seat → solo_b → ANCHOR_B_FRAME
#   omit seat (or set None) for bench anchors not currently on air.
# ANCHOR_LEAD and story alternation are driven by id and seat, not list order.
ANCHORS = [
    {
        "id":        "Annie",
        "seat":      None,
        "avatar_id": "Annie_expressive_public",
        "voice_id":  "e1ccd6ecac8e4c15819ad143efdd4ce2",
        "label":     "Anchor A",
    },
    {
        "id":        "Vesperi",
        "seat":      None,
        "avatar_id": "621884a0add3422cb3e26474fb1d9e7b",
        "voice_id":  "b2c1c902ef1d45108c03e18bff601efe",
        "label":     "Anchor B",
    },
    {
        "id":        "Daphne",
        "seat":      "b",
        "avatar_id": "Daphne_public_4",
        "voice_id":  "812d4eea4a8442a382dcaf2dbaddbd93",
        "label":     "Anchor C",
    },
    {
        "id":        "Gabrielle",
        "seat":      None,
        "avatar_id": "bbb7020a766f429e811c1b23fcecf987",
        "voice_id":  "ca320fd62b784352af74d06a16a6ef3d",
        "label":     "Anchor D",
    },
    {
        "id":        "Saskia",
        "seat":      "a",
        "avatar_id": "Saskia_public_5",
        "voice_id":  "a4a6df6d4fc248829f72edde5529defa",
        "label":     "Anchor E",
    },
    {
        "id":        "Darlene",
        "seat":      None,
        "avatar_id": "6ab4b4c705d14773bb0cb7c1dda31db0",
        "voice_id":  "d6a657274b184772ac28a6146f729d3a",
        "label":     "Anchor F",
    },
]


# Section order must match stories.json section keys
SECTIONS = [
    "Core Tech Releases",
    "Directions in AI Architecture",
    "AI For Productivity",
    "World Impact",
]

# Anchor assignment: stories alternate A/B globally across all sections.
# ANCHOR_LEAD is the anchor that reads the intro and outro.
ANCHOR_LEAD = "Annie"

# ── Video / compositor ─────────────────────────────────────────────────────────
VIDEO_RESOLUTION = (1920, 1080)
VIDEO_FPS        = 30
SET_BACKGROUND_IMAGE = str(PROJECT_ROOT / "assets" / "set_background.jpg")

# Anchor frame positions: (x, y, w, h) in pixels
# Anchor A sits left-of-center; Anchor B sits right-of-center.
ANCHOR_A_FRAME = (120,  200, 620, 720)   # left seat
ANCHOR_B_FRAME = (1180, 200, 620, 720)   # right seat

# Pixels cropped from bottom of anchor clip to simulate desk occlusion.
# Increase if the desk cuts higher into the anchor's torso.
ANCHOR_CROP_BOTTOM = 160

# Wall-mounted B-roll screen (center-back of set)
WALL_SCREEN_FRAME = (660, 60, 600, 340)   # (x, y, w, h)

# PiP anchor insert used in "broll" shot mode
PIP_FRAME    = (40, 820, 340, 192)        # bottom-left corner
PIP_ANCHOR_ID = next(a["id"] for a in ANCHORS if a.get("seat") == "a")  # seat-a anchor in PiP

# Lower-third bar
LOWER_THIRD_FRAME          = (0, 900, 1920, 100)
LOWER_THIRD_BG_COLOR       = [10, 30, 80]          # deep navy
LOWER_THIRD_HEADLINE_COLOR = "white"
LOWER_THIRD_SOURCE_COLOR   = "#AABBEE"
LOWER_THIRD_FONT           = "Arial"               # must be installed on OS
LOWER_THIRD_HEADLINE_SIZE  = 36
LOWER_THIRD_SOURCE_SIZE    = 24

# Crossfade duration in seconds (used when transition = "crossfade")
CROSSFADE_DURATION = 0.4

# Shot plan path for the current episode
SHOT_PLAN_JSON = EPISODE_DIR / "shot_plan.json"

# ── B-roll sourcing ────────────────────────────────────────────────────────────
PEXELS_API_KEY  = os.environ.get("PEXELS_API_KEY")
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY")   # DALL-E fallback
BROLL_STRATEGY  = ["pexels", "dalle"]  # order of preference

# ── Anthropic / script generation ─────────────────────────────────────────────
ANTHROPIC_MODEL      = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096

# Story body character targets — used by script_generator.py for validation
# and injected into the prompt template as [TEXT MIN] / [TEXT MAX].
STORY_LEN_MIN  = 660
STORY_LEN_MAX  = 1100

STORY_TEXT_MIN = STORY_LEN_MIN   # alias used in prompt injection
STORY_TEXT_MAX = STORY_LEN_MAX   # alias used in prompt injection

# Approximate word-count equivalents injected as [COPY MIN] / [COPY MAX]
STORY_COPY_MIN = 60
STORY_COPY_MAX = 90

# ── Story history — prevents repeated topics across weekly runs ────────────────
# Stored at project root so it persists across all episodes.
STORY_HISTORY_FILE   = PROJECT_ROOT / "newsreel_story_history.json"
STORY_EXCLUSION_DAYS = 21   # suppress stories covered in the last 3 weeks
STORY_HISTORY_MAX    = 25   # cap total entries kept in the history file

# Date range injected into the prompt — derived from END_DATE in config
START_DATE = END_DATE - timedelta(days=6)


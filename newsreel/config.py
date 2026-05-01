import os
from pathlib import Path
from datetime import datetime, timedelta

# Location of this config file is the anchor for all relative paths in the project
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

def project_path(*parts):
    return str(PROJECT_ROOT.joinpath(*parts))

END_DATE = datetime.today() - timedelta(days=1)
# END_DATE = datetime.today()
START_DATE = END_DATE - timedelta(days=6)

OPENING_TITLE = f"AI Newsreel Week of {START_DATE.strftime('%B %d')} through {END_DATE.strftime('%B %d, %Y')}"

WEEK_FOLDER_NAME = END_DATE.strftime("%m%d%y_Newsreel")
WEEK_FOLDER = project_path(WEEK_FOLDER_NAME)
WEEK_PHRASE = "This week:"

#Weekly Rundown Settings
RUNDOWN_STYLE = {"font_size": 36, "color": "white"}
RUNDOWN_HEADER = "This Week"
RUNDOWN_HEADER_STYLE = {"font_size": 48, "color": "white"}
RUNDOWN_Y_START = 200  # vertical position of header
RUNDOWN_LINE_HEIGHT = 50  # pixels between lines
RUNDOWN_END_PHRASE = "Here is what happened"

OVERLAY_ANTICIPATION = 0.4  # seconds before timestamp to show overlay
OVERLAY_BG_COLOR = (0, 0, 0)
OVERLAY_BG_OPACITY = 0.6
OVERLAY_BG_PADDING = 20

# Overlay Page Settings
BACKGROUND_COLOR = (15, 20, 40)  # dark navy
FONT = "Arial"

# Opening title card
OPENING_STYLE = {"font_size": 80, "color": "white", "duration": 5, "position": "center"}

# Text overlay styles
SECTION_STYLE = {"font_size": 72, "color": "white", "duration": 4,"position": "center"}


# Lower third chyron — story title + source attribution
# Displayed as a broadcast-style lower third during each story
LOWER_THIRD_TITLE_STYLE  = {"font_size": 28, "color": "white"}
LOWER_THIRD_SOURCE_STYLE = {"font_size": 20, "color": "#aaddff"}  # light blue subtext
LOWER_THIRD_BG_COLOR     = (0, 30, 80)      # dark navy bar
LOWER_THIRD_BG_OPACITY   = 0.80
LOWER_THIRD_Y            = 880              # vertical position (pixels from top, 1080p)
LOWER_THIRD_DURATION     = 35.0             # seconds to display

#GET API KEY FROM ENVIRONMENT VARIABLES
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set. Please configure your API key securely.")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set. Please configure your API key securely.")

ANTHROPIC_GENPROMPT_FILE = project_path(WEEK_FOLDER_NAME, "anthropicPrompt.txt")
ANTHROPIC_RESPONSE_FILE = project_path(WEEK_FOLDER_NAME, "anthropicResponse.txt")

ANTHROPIC_JSON_FILE = Path(project_path(WEEK_FOLDER_NAME, "stories.json"))
ANTHROPIC_SHORT_JSON_FILE = Path(project_path(WEEK_FOLDER_NAME, "shortstories.json"))

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Story topic history — prevents repeated stories across weekly runs
# ---------------------------------------------------------------------------

STORY_HISTORY_FILE    = Path(PROJECT_ROOT) / "newsreel_story_history.json"
STORY_EXCLUSION_DAYS  = 21   # 3 weeks — matches your "last 3 weeks" problem
STORY_HISTORY_MAX     = 200

STORY_LEN_MIN       = 660
STORY_LEN_MAX       = 1100

STORY_TEXT_MIN = 350
STORY_TEXT_MAX = 550

STORY_COPY_MIN = 60
STORY_COPY_MAX = 90

SECTION_VIDEOS = {
    "intro":                            project_path("stock_videos", "bookend.mov"),
    "Core Tech Releases":               project_path("stock_videos", "coretech.mp4"),
    "Directions in AI Architecture":    project_path("stock_videos", "AIdirections.mp4"),
    "AI For Productivity":              project_path("stock_videos", "AIproductivity.mp4"),
    "World Impact":                     project_path("stock_videos", "worldimpact.mp4"),
    "outro":                            project_path("stock_videos", "bookend.mov"),
}

OUTRO_PHRASE = "That is your weekly summary"

SOURCE_PHRASE = "Sources this week:"

BG_VIDEOS = [
    project_path("stock_videos", "vecteezy_03.mp4"),
    project_path("stock_videos", "vecteezy_06.mp4"),
    project_path("stock_videos", "vecteezy_04.mp4"),
    project_path("stock_videos", "vecteezy_14.mov"),
    project_path("stock_videos", "vecteezy_15.mp4"),
    project_path("stock_videos", "vecteezy_16.mov"),
    project_path("stock_videos", "vecteezy_17.mov"),
    project_path("stock_videos", "vecteezy_18.mov"),
    project_path("stock_videos", "vecteezy_19.mov"),
    project_path("stock_videos", "vecteezy_20.mov"),
    project_path("stock_videos", "vecteezy_22.mov"),
    project_path("stock_videos", "vecteezy_23.mov"),
    project_path("stock_videos", "vecteezy_24.mov"),
]

VIDEO_CLIP_MANIFEST = [
    ("00_intro",                        "intro"),
    ("01_core_tech_releases",           "Core Tech Releases"),
    ("02_directions_in_ai_architecture","Directions in AI Architecture"),
    ("03_ai_for_productivity",          "AI For Productivity"),
    ("04_world_impact",                 "World Impact"),
    ("99_outro",                        "outro"),
]

VOICE_VOLUME_BOOST = {
    "01_core_tech_releases":            1.2,
    "02_directions_in_ai_architecture": 3,
    "03_ai_for_productivity":           1.2,
    "04_world_impact":                  3,
}

VIDEO_INTRO_SILENCE     = 5.0   # seconds — pushed back to allow sting to breathe
VIDEO_INTER_CLIP_SILENCE = 1.0  # seconds

SRT_TARGET_WORDS = 10         # aim for this many words per caption line
SRT_MAX_DURATION = 5.0        # never let a caption run longer than this (seconds)
SRT_MIN_DURATION = 0.5        # never shorter than this
SRT_OUTPUT_FILE = Path(project_path(WEEK_FOLDER_NAME, "Captions.srt"))

# This model handles SSML properly.  
EL_MODEL_ID = "eleven_multilingual_v2"

# Currently used voices. MAIN is used for intro and outro:

EL_VOICE_CLANCY = "FLpz0UhC9a7CIfUSBo6S"    # Clancy (MAIN)
EL_VOICE_MAIN   = EL_VOICE_CLANCY           # alias used by newsreel_tts.py
EL_VOICE_SECTION1 = "tMXujoAjiboschVOhAnk"  # (Section 1)
EL_VOICE_SECTION2 = "ya031zGCAxyRGrvB3or9"  # (Section 2)
EL_VOICE_SECTION3 = "tMXujoAjiboschVOhAnk"  # (Section 3)
EL_VOICE_SECTION4 = "ya031zGCAxyRGrvB3or9"  # (Section 4)

OTHER_VOICES = {
    "Kim": "O7LV5fxosQChiBE7l6Wz",
    "Marcos": "MjDkeH2x9hCiWKXZtUPc",
}

# Test voices
EL_VOICE_TEST_MAIN = "FLpz0UhC9a7CIfUSBo6S"  # Clancy
EL_VOICE_TEST_SECTION1 = "tMXujoAjiboschVOhAnk"  # Clara
EL_VOICE_TEST_SECTION2 = "QIhD5ivPGEoYZQDocuHI"  # Adam
EL_VOICE_TEST_SECTION3 = "qBDvhofpxp92JgXJxDjB"  # Lily Wolff
EL_VOICE_TEST_SECTION4 = "MjDkeH2x9hCiWKXZtUPc"  # Marcos

AUDIO_OFFSET = 2  # seconds of video before audio starts
AUDIO_CODEC = "aac"

# ---------------------------------------------------------------------------
# Audio time-stretch — applied by stretch_audio.py after TTS generation.
# 1.0 = no change. 1.15 = 15% faster. Max recommended: 1.3
# Intro and outro are left at 1.0 — Clancy's pacing works well as is.
# ---------------------------------------------------------------------------

AUDIO_SPEED_FACTORS = {
    "00_intro":                         1.0,
    "01_core_tech_releases":            1.15,
    "02_directions_in_ai_architecture": 1.15,
    "03_ai_for_productivity":           1.15,
    "04_world_impact":                  1.15,
    "99_outro":                         1.0,
}

# ---------------------------------------------------------------------------
# ElevenLabs voice speed — applied at generation time, no pitch distortion.
# 1.0 = normal. Range roughly 0.7 to 1.2. Per-stem, keyed same as manifest.
# Intro/outro left at 1.0 — Clancy's pacing is fine as is.
# ---------------------------------------------------------------------------

EL_VOICE_SPEED = {
    "00_intro":                         1.0,
    "01_core_tech_releases":            1.15,
    "02_directions_in_ai_architecture": 1.15,
    "03_ai_for_productivity":           1.15,
    "04_world_impact":                  1.15,
    "99_outro":                         1.0,
}

# ElevenLabs voice stability and similarity per stem.
# stability:        0.0–1.0. Higher = more consistent energy over long clips.
#                   Raise for voices that fade or drift (especially long sections).
# similarity_boost: 0.0–1.0. Higher = closer to reference voice character.
EL_VOICE_SETTINGS = {
    "00_intro":                         {"stability": 0.70, "similarity_boost": 0.75},
    "01_core_tech_releases":            {"stability": 0.50, "similarity_boost": 0.75},
    "02_directions_in_ai_architecture": {"stability": 0.50, "similarity_boost": 0.75},
    "03_ai_for_productivity":           {"stability": 0.50, "similarity_boost": 0.75},
    "04_world_impact":                  {"stability": 0.50, "similarity_boost": 0.75},
    "99_outro":                         {"stability": 0.70, "similarity_boost": 0.75},
}

# ---------------------------------------------------------------------------
# TTS pronunciation lexicon — spoken text only, never display text or captions.
# Entries are applied longest-key-first to prevent shorter keys clobbering longer ones.
# ---------------------------------------------------------------------------

TTS_SUBSTITUTIONS = {
    "AI":      "A I",
    "AMD":     "A M D",
    "capex":  "cap ex",
    "Epoch":   "E pok",
    "LLM":     "L L M",
    "METR":    "Meter",
    "pct":     "percent",
}




# ---------------------------------------------------------------------------
# Music bed
# ---------------------------------------------------------------------------

MUSIC_STING_FILE = project_path("music", "news", "breaking-news2.mp3")

MUSIC_STING_VOLUME   = 1.0   # full volume for the intro sting
MUSIC_STING_DURATION = 11.0   # trim sting to this many seconds
MUSIC_STING_FADE_OUT = 2.0   # fade out over last N seconds of sting
MUSIC_BED_VOLUME     = 0.5 # low ambient bed under narration
MUSIC_OUTRO_VOLUME   = 0.2 # low ambient bed under narration

MUSIC_SEGMENTS = {
    "01_core_tech_releases":            { "file": project_path("music", "news", "section1.mp3"), "volume": 0.50  },
    "02_directions_in_ai_architecture": { "file": project_path("music", "news", "section2.mp3"), "volume": 0.03 },
    "03_ai_for_productivity":           { "file": project_path("music", "news", "section3.mp3"), "volume": 0.10 },
    "04_world_impact":                  { "file": project_path("music", "news", "section4.mp3"), "volume": 0.10 },
}

#Output File
OUTPUT_VIDEO = project_path(WEEK_FOLDER_NAME, "News.mp4")

AUDIO_SPEED_FACTOR = 0.9
EL_FIXED_FILE = project_path(WEEK_FOLDER_NAME, "News_fixed.mp3")
EL_SLOW_FILE = project_path(WEEK_FOLDER_NAME, "News_slow.mp3")

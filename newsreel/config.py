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

# Story overlay phase behavior
STORY_STYLE1 = {"font_size": 52, "color": "yellow", "duration": 4, "position": "center"}
STORY_STYLE2 = {"font_size": 32, "color": "yellow", "duration": 5, "position": ("right", 950)}

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

#Build Video config
SECTION_HEADERS = [
    "Core Tech Releases",
    "Directions in AI Architecture",
    "AI For Productivity",
    "World Impact",
]

SECTION_VIDEOS = {
    "intro":                            project_path("stock_videos", "bookend.mp4"),
    "Core Tech Releases":               project_path("stock_videos", "windydesertriver.mp4"),
    "Directions in AI Architecture":    project_path("stock_videos", "narrowmtnpath.mp4"),
    "AI For Productivity":              project_path("stock_videos", "cityroadbay.mp4"),
    "World Impact":                     project_path("stock_videos", "grandcanyonriver.mp4"),
    "outro":                            project_path("stock_videos", "bookend.mp4"),
}

OUTRO_PHRASE = "That is your weekly summary"

SOURCE_PHRASE = "Sources this week:"

BG_VIDEOS = [
    project_path("stock_videos", "vecteezy_02.mp4"),
    project_path("stock_videos", "vecteezy_03.mp4"),
    project_path("stock_videos", "vecteezy_05.mp4"),
    project_path("stock_videos", "vecteezy_06.mp4"),
    project_path("stock_videos", "vecteezy_04.mp4"),
    project_path("stock_videos", "vecteezy_09.mp4"),
    project_path("stock_videos", "diskdrives.mp4"),
    project_path("stock_videos", "vecteezy_10.mp4"),
    project_path("stock_videos", "vecteezy_12.mp4"),
    project_path("stock_videos", "vecteezy_13.mov"),
    project_path("stock_videos", "vecteezy_14.mov"),
    project_path("stock_videos", "vecteezy_15.mp4"),
    project_path("stock_videos", "vecteezy_16.mov"),
    project_path("stock_videos", "vecteezy_17.mov"),
    project_path("stock_videos", "vecteezy_18.mov"),
    project_path("stock_videos", "vecteezy_19.mov"),
    project_path("stock_videos", "vecteezy_20.mov"),
    project_path("stock_videos", "vecteezy_21.mov"),
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
    "01_core_tech_releases":            1.4,   # Kim
    "02_directions_in_ai_architecture": 1.6,   # Ryan
    "03_ai_for_productivity":           1.2,   # Marcos
    "04_world_impact":                  1.2,   # Clara
}

VIDEO_INTRO_SILENCE     = 5.0   # seconds — pushed back to allow sting to breathe
VIDEO_INTER_CLIP_SILENCE = 1.0  # seconds

SRT_TARGET_WORDS = 6          # aim for this many words per caption line
SRT_MAX_DURATION = 3.0        # never let a caption run longer than this (seconds)
SRT_MIN_DURATION = 0.5        # never shorter than this
SRT_OUTPUT_FILE = Path(project_path(WEEK_FOLDER_NAME, "Captions.srt"))

# This model handles SSML properly.  
EL_MODEL_ID = "eleven_multilingual_v2"

# Currently used voices. MAIN is used for intro and outro:

EL_VOICE_CLANCY = "FLpz0UhC9a7CIfUSBo6S"    # Clancy (MAIN)
EL_VOICE_MAIN   = EL_VOICE_CLANCY               # alias used by newsreel_tts.py
EL_VOICE_KIM = "O7LV5fxosQChiBE7l6Wz"       # Kim (Section 1)
EL_VOICE_RYAN = "ya031zGCAxyRGrvB3or9"      # Ryan (Section 2)
EL_VOICE_MARCOS = "MjDkeH2x9hCiWKXZtUPc"    # Marcos (Section 3)
EL_VOICE_CLARA = "tMXujoAjiboschVOhAnk"     # Clara (Section 4)

# Test voices
EL_VOICE_TEST_MAIN = "FLpz0UhC9a7CIfUSBo6S"  # Clancy
EL_VOICE_TEST_SECTION1 = "tMXujoAjiboschVOhAnk"  # Clara
EL_VOICE_TEST_SECTION2 = "QIhD5ivPGEoYZQDocuHI"  # Adam
EL_VOICE_TEST_SECTION3 = "qBDvhofpxp92JgXJxDjB"  # Lily Wolff
EL_VOICE_TEST_SECTION4 = "MjDkeH2x9hCiWKXZtUPc"  # Marcos

AUDIO_OFFSET = 2  # seconds of video before audio starts
AUDIO_CODEC = "aac"

# ---------------------------------------------------------------------------
# Music bed
# ---------------------------------------------------------------------------

MUSIC_STING_FILE = project_path("music", "news", "breaking-news.mp3")
MUSIC_BED_FILE   = project_path("music", "news", "independence-day.mp3")

MUSIC_STING_VOLUME   = 1.0   # full volume for the intro sting
MUSIC_STING_DURATION = 6.0   # trim sting to this many seconds
MUSIC_STING_FADE_OUT = 2.0   # fade out over last N seconds of sting
MUSIC_BED_VOLUME     = 0.06  # low ambient bed under narration

#Input/Output Files
EL_INPUT_FILE = project_path(WEEK_FOLDER_NAME, "News.txt")
EL_OUTPUT_FILE = project_path(WEEK_FOLDER_NAME, "News.mp3")
EL_DELAY_FILE = project_path(WEEK_FOLDER_NAME, "News_delayed.mp3")
TIMESTAMP_FILE = project_path(WEEK_FOLDER_NAME, "NewsTimeStamps.json")
OUTPUT_VIDEO = project_path(WEEK_FOLDER_NAME, "News.mp4")

AUDIO_SPEED_FACTOR = 0.9
EL_FIXED_FILE = project_path(WEEK_FOLDER_NAME, "News_fixed.mp3")
EL_SLOW_FILE = project_path(WEEK_FOLDER_NAME, "News_slow.mp3")

import os
from pathlib import Path

from datetime import datetime, timedelta


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def project_path(*parts):
    return str(PROJECT_ROOT.joinpath(*parts))

end_date = datetime.today() - timedelta(days=1)  # Use yesterday as the end date to ensure we have a full week of news
start_date = end_date - timedelta(days=7)

OPENING_TITLE = f"AI Newsreel Week of {start_date.strftime('%b %d')} - {end_date.strftime('%b %d  %Y')}"
WEEK_FOLDER_NAME = end_date.strftime("%m%d%y")
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

#GET API KEY FROM ENVIRONMENT VARIABLES
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set. Please configure your API key securely.")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set. Please configure your API key securely.")

ANTHROPIC_GENPROMPT_FILE = project_path(WEEK_FOLDER_NAME, "anthropicPrompt.txt")
ANTHROPIC_RESPONSE_FILE = project_path(WEEK_FOLDER_NAME, "anthropicResponse.txt")
ANTHROPIC_OUTPUT_FILE = Path(project_path(WEEK_FOLDER_NAME, "shortstories.json"))

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
    "intro": project_path("stock_videos", "bookend.mp4"),
    "Core Tech Releases": project_path("stock_videos", "windydesertriver.mp4"),
    "Directions in AI Architecture": project_path("stock_videos", "narrowmtnpath.mp4"),

    "AI For Productivity": project_path("stock_videos", "cityroadbay.mp4"),
    "World Impact": project_path("stock_videos", "grandcanyonriver.mp4"),

    "outro": project_path("stock_videos", "bookend.mp4"),
}

OUTRO_PHRASE = "That is your weekly summary"

SOURCE_PHRASE = "Sources this week:"

BG_VIDEOS = [
    project_path("stock_videos", "bluehardwarechip.mp4"),
    project_path("stock_videos", "yellowgreenwavy.mp4"),
    project_path("stock_videos", "world_impact.mp4"),
    project_path("stock_videos", "grasssunset.mp4"),
    project_path("stock_videos", "productivity.mp4"),
    project_path("stock_videos", "diskdrives.mp4"),
    project_path("stock_videos", "releases.mp4"),
    project_path("stock_videos", "goldhardwarechip.mp4"),
    project_path("stock_videos", "directions.mp4"),
]

# This model handles SSML properly.  
EL_MODEL_ID = "eleven_multilingual_v2"

# Provider-specific voice identifier used by the text-to-speech service.
# To change the voice, replace this with another valid voice ID from the provider's console.
EL_VOICE_MAIN = "FLpz0UhC9a7CIfUSBo6S"  # Clancy
EL_VOICE_SECTION1 = "ZthjuvLPty3kTMaNKVKb"  # Peter
EL_VOICE_SECTION2 = "ClH95FbjM9JXsdORDh0z"  # Mary
EL_VOICE_SECTION3 = "O7LV5fxosQChiBE7l6Wz"  # Kim
EL_VOICE_SECTION4 = "ya031zGCAxyRGrvB3or9"  # Ryan

AUDIO_OFFSET = 2  # seconds of video before audio starts
AUDIO_CODEC = "aac"

#Input/Output Files
EL_INPUT_FILE = project_path(WEEK_FOLDER_NAME, "News.txt")
EL_OUTPUT_FILE = project_path(WEEK_FOLDER_NAME, "News.mp3")
EL_DELAY_FILE = project_path(WEEK_FOLDER_NAME, "News_delayed.mp3")
TIMESTAMP_FILE = project_path(WEEK_FOLDER_NAME, "NewsTimeStamps.json")
OUTPUT_VIDEO = project_path(WEEK_FOLDER_NAME, "News.mp4")

AUDIO_SPEED_FACTOR = 0.9
EL_FIXED_FILE = project_path(WEEK_FOLDER_NAME, "News_fixed.mp3")
EL_SLOW_FILE = project_path(WEEK_FOLDER_NAME, "News_slow.mp3")

import os

from datetime import datetime
_today = datetime.now()
OPENING_TITLE = f"AI Newsreel | Week of {_today.strftime('%B %d, %Y')}"
WEEK = "040126"


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
STORY_STYLE2 = {"font_size": 32, "color": "yellow", "duration": 5, "position": ("center", 950)}

#GET API KEY FROM ENVIRONMENT VARIABLES
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set. Please configure your API key securely.")

#Build Video config
SECTION_HEADERS = [
    "Core Tech Releases",
    "Directions in AI Architecture",
    "AI For Productivity",
    "World Impact",
]

SECTION_VIDEOS = {
    "intro": "stock_videos/bookend.mp4",
    "Core Tech Releases": "stock_videos/releases.mp4",
    "Directions in AI Architecture": "stock_videos/directions.mp4",
    "AI For Productivity": "stock_videos/productivity.mp4",
    "World Impact": "stock_videos/world_impact.mp4",
    "outro": "stock_videos/bookend.mp4",
}

OUTRO_PHRASE = "That is your weekly summary"

BG_VIDEOS = [

    "stock_videos/video6_20Sec.mp4",
    "stock_videos/newvid1.mp4",
    "stock_videos/newvid3.mp4",
    "stock_videos/newvid4.mp4",
    "stock_videos/video7_10Sec.mp4",
    "stock_videos/newvid5.mp4",
    "stock_videos/newvid6.mp4",
    "stock_videos/video12_9Sec.mp4",
    "stock_videos/newvid7.mp4",
    "stock_videos/video8_10Sec.mp4",
]

# This model handles SSML properly.  
EL_MODEL_ID = "eleven_multilingual_v2"

# Provider-specific voice identifier used by the text-to-speech service.
# To change the voice, replace this with another valid voice ID from the provider's console.
EL_VOICE_NAME = "FLpz0UhC9a7CIfUSBo6S"  # Clancy

AUDIO_OFFSET = 2  # seconds of video before audio starts
AUDIO_CODEC = "aac"

#Input/Output Files
EL_INPUT_FILE = f"{WEEK}/News.txt"
EL_OUTPUT_FILE = f"{WEEK}/News.mp3"
EL_DELAY_FILE = f"{WEEK}/News_delayed.mp3"
TIMESTAMP_FILE = f"{WEEK}/NewsTimeStamps.json"
OUTPUT_VIDEO = f"{WEEK}/News.mp4"

AUDIO_SPEED_FACTOR = 0.9
EL_FIXED_FILE = f"{WEEK}/News_fixed.mp3"
EL_SLOW_FILE = f"{WEEK}/News_slow.mp3"


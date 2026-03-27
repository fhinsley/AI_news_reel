import os

from datetime import datetime
_today = datetime.now()
OPENING_TITLE = f"AI Newsreel | Week of {_today.strftime('%B %d, %Y')}"
WEEK = "032726"

OVERLAY_ANTICIPATION = 0.4  # seconds before timestamp to show overlay

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

BG_VIDEOS = [
    "stock_videos/video1_7sec.mp4",
    "stock_videos/video2_40Sec.mp4",
    "stock_videos/video3_10Sec.mp4",
    "stock_videos/video4_17Sec.mp4",
    "stock_videos/video5_8Sec.mp4",
    "stock_videos/video6_20Sec.mp4",
    "stock_videos/video7_10Sec.mp4",
    "stock_videos/video8_10Sec.mp4",
    "stock_videos/video9_10Sec.mp4",
    "stock_videos/video10_13Sec.mp4",
    "stock_videos/video11_14Sec.mp4",
    "stock_videos/video12_9Sec.mp4",
    "stock_videos/video13_14Sec.mp4",
    "stock_videos/video14_10Sec.mp4",
]

BG_CLIP_DURATION = 30  # seconds to show each clip before moving to next

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
ARTIFACT_FILTER = ""  # fill in each week with artifact silence ranges


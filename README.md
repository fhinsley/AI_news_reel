# ElevenLabsScript

Automated weekly AI newsreel pipeline.

This project takes a weekly script, generates ElevenLabs narration with timestamps, post-processes audio for artifacts and pacing, and renders a final video with background footage and timed text overlays.

## What It Does

- Reads weekly script text from a date-based folder (for example, `040226/News.txt`)
- Generates narration and timestamp alignment using ElevenLabs
- Silences `<break .../>` artifact regions in speech timing
- Slows and delays narration to align with overlays
- Builds a full newsreel video with section/story overlays and sources
- Writes output media back to the same weekly folder

## Project Layout

- `run_newsreel.py`: one-command pipeline runner
- `requirements.txt`: Python dependencies for the core pipeline
- `scripts/newsreel_tts.py`: TTS generation + timestamp export
- `scripts/silence_artifacts.py`: break-tag artifact detection + FFmpeg filter builder
- `scripts/build_video.py`: video assembly and overlay timing
- `scripts/config.py`: all runtime configuration (paths, style, voice, section rules)
- `stock_videos/`: background clips used for sections and transitions
- `MMDDYY/`: weekly input/output folders (script, timestamps, audio, final video)

## Requirements

- Python 3.10+
- FFmpeg installed and available in `PATH`
- ElevenLabs API key in environment variable `ELEVENLABS_API_KEY`

Python packages used by the scripts:

- `moviepy`
- `elevenlabs`
- `spacy` (used by optional entity extraction script)

Install from dependency file:

```bash
python -m pip install -r requirements.txt
```

Manual install example:

```bash
python -m pip install moviepy elevenlabs spacy
```

If you use `extract_entities.py`, also install the model:

```bash
python -m spacy download en_core_web_sm
```

## Setup

1. Set your ElevenLabs key:

```bash
export ELEVENLABS_API_KEY="your_key_here"
```

2. Ensure the current week folder exists and contains `News.txt`.

The active folder name is derived in `scripts/config.py` from date logic:

- `end_date = today - 2 days`
- `start_date = end_date - 7 days`
- week folder format: `MMDDYY`

## Run The Pipeline

From project root:

```bash
python run_newsreel.py
```

This executes:

1. `scripts/newsreel_tts.py`
2. `scripts/build_video.py`

## Output Files

Generated in the active weekly folder:

- `News.mp3`
- `News_fixed.mp3`
- `News_slow.mp3`
- `News_delayed.mp3`
- `NewsTimeStamps.json`
- `News.mp4`

## Configuration Notes

Main knobs live in `scripts/config.py`:

- Voice/model: `EL_VOICE_NAME`, `EL_MODEL_ID`
- Timing: `AUDIO_SPEED_FACTOR`, `AUDIO_OFFSET`, `OVERLAY_ANTICIPATION`
- Overlay style: `OPENING_STYLE`, `SECTION_STYLE`, `STORY_STYLE1`, `STORY_STYLE2`
- Rundown layout: `RUNDOWN_HEADER_STYLE`, `RUNDOWN_LINE_HEIGHT`, etc.
- Section-video mapping: `SECTION_VIDEOS`

All media/script paths are resolved from the project root, so running from root is stable after moving scripts into `scripts/`.

## Troubleshooting

- `ELEVENLABS_API_KEY environment variable is not set`:
  - Export the key in your shell before running.
- `ffmpeg: command not found`:
  - Install FFmpeg and confirm `ffmpeg -version` works.
- Missing weekly script:
  - Confirm active date folder contains `News.txt`.
- Missing stock video file:
  - Check filenames listed in `SECTION_VIDEOS` and `BG_VIDEOS`.

## Optional Scripts

- `scripts/test_tts_before_11labs.py`: prints resolved config paths for quick path sanity checks
- `scripts/viewscript.py`: prints processed script text after break-tag/newline cleanup
- `scripts/extract_entities.py`: named-entity extraction helper
- `scripts/video_test.py`: minimal MoviePy write test

# ElevenLabsScript

Automated weekly AI newsreel pipeline.

This project uses Claude (Anthropic) to generate a weekly AI news script, trims it for broadcast length, generates multi-voice narration with timestamps via ElevenLabs, assembles a final video with background footage and timed text overlays, and publishes it to YouTube with closed captions.

## What It Does

1. **Generates the script** — Sends a prompt to Claude with web search enabled; Claude fetches current AI news and returns structured JSON stories organized into four sections
2. **Trims stories** — Reduces each story body to a target length at a natural sentence boundary
3. **Generates narration** — Produces six audio clips (intro, four section correspondents, outro) with per-character timestamp alignment via ElevenLabs
4. **Silences artifacts** — Detects brief noise/click artifacts at SSML break-tag boundaries in each clip and uses FFmpeg to zero out those regions in-place
5. **Assembles video** — Builds the full newsreel with section-specific background footage, overlay text timed to speech, and a sources list
6. **Generates captions** — Produces a standard SRT file (`Captions.srt`) from the ElevenLabs character-level timestamps for closed captioning
7. **Generates transcript** — Produces a formatted PDF (`Transcript.pdf`) with all stories organized by section, plus a clickable sources list at the end
8. **Uploads to YouTube** — Authenticates via OAuth, uploads `News.mp4` with metadata and tags, attaches the SRT caption track, adds the video to the newsreel playlist, and opens the published video in the browser

## Project Layout

```
run_newsreel.py             one-command pipeline runner
requirements.txt            Python dependencies
markdown/
  Weekly_Newsreel_Prompt.md  Claude prompt template (date placeholders interpolated at runtime)
scripts/
  config.py                 all runtime configuration (paths, dates, voices, styles)
  script_generator.py       step 1 — calls Claude API to generate stories.json
  trim_stories.py           step 2 — trims stories.json → shortstories.json
  newsreel_tts.py           step 3 — multi-voice TTS + timestamp export
  build_video.py            step 4 — video assembly with overlays
  generate_srt.py           step 5 — builds Captions.srt from character-level timestamps
  generate_transcript.py    step 6 — builds Transcript.pdf from shortstories.json
  upload_youtube.py         step 7 — OAuth upload of video + captions to YouTube
  silence_artifacts.py      step 4 — silences TTS artifact regions in-place via FFmpeg
  watchnews.py              utility — opens the latest published newsreel in the browser
  makeinoutro.py            standalone test for intro/outro wording
  test_tts_before_11labs.py prints resolved config paths for sanity checks
  viewscript.py             prints processed script text after cleanup
  extract_entities.py       named-entity extraction helper
  video_test.py             minimal MoviePy write test
stock_videos/               background clips for sections and transitions
MMDDYY/                     weekly output folder (auto-created, named by end date)
```

## Requirements

- Python 3.10+
- FFmpeg installed and available in `PATH`
- ElevenLabs API key in environment variable `ELEVENLABS_API_KEY`
- Anthropic API key in environment variable `ANTHROPIC_API_KEY`
- Google Cloud OAuth credentials for YouTube upload (see Setup below)

Python packages:

```bash
python -m pip install -r requirements.txt
```

Core packages: `moviepy`, `elevenlabs`, `anthropic`, `reportlab`, `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

## Setup

1. Set your API keys:

```bash
export ELEVENLABS_API_KEY="your_elevenlabs_key"
export ANTHROPIC_API_KEY="your_anthropic_key"
```

2. Confirm `markdown/Weekly_Newsreel_Prompt.md` exists — it is the script template.

3. For YouTube upload, download OAuth 2.0 credentials from Google Cloud Console (with YouTube Data API v3 enabled) and save the file as `scripts/client_secrets.json`. On the first run, a browser window will open for authorization; the token is saved to `scripts/youtube_token.pickle` so subsequent runs are fully headless.

The active week folder is derived from the current date in `scripts/config.py`:

- `END_DATE = today - 1 day`
- `START_DATE = END_DATE - 7 days`
- Folder name format: `MMDDYY` (based on `END_DATE`)

The folder is created automatically when the pipeline runs.

## Run the Pipeline

From project root:

```bash
python run_newsreel.py
```

This runs all steps in sequence:

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `script_generator.py` | `markdown/Weekly_Newsreel_Prompt.md` | `MMDDYY/stories.json` |
| 2 | `trim_stories.py` | `MMDDYY/stories.json` | `MMDDYY/shortstories.json` |
| 3 | `newsreel_tts.py` | `MMDDYY/shortstories.json` | `MMDDYY/00_intro.mp3`, `01_*.mp3` … `99_outro.mp3` + timestamp JSONs |
| 4 | `silence_artifacts.py` | clip mp3s + timestamp JSONs | mp3s cleaned in-place |
| 5 | `build_video.py` | clips + timestamps | `MMDDYY/News.mp4` |
| 6 | `generate_srt.py` | timestamp JSONs | `MMDDYY/Captions.srt` |
| 7 | `generate_transcript.py` | `MMDDYY/shortstories.json` | `MMDDYY/Transcript.pdf` |
| 8 | `upload_youtube.py` | `News.mp4` + `Captions.srt` | published YouTube video (browser opens) |

## Voices

The newsreel uses five ElevenLabs voices:

| Role | Voice | Config constant |
|------|-------|----------------|
| Intro / Outro | Clancy | `EL_VOICE_MAIN` |
| Core Tech Releases | Kim | `EL_VOICE_KIM` |
| Directions in AI Architecture | Ryan | `EL_VOICE_RYAN` |
| AI For Productivity | Marcos | `EL_VOICE_MARCOS` |
| World Impact | Clara | `EL_VOICE_CLARA` |

## Sections

Each week covers four fixed sections:

1. Core Tech Releases
2. Directions in AI Architecture
3. AI For Productivity
4. World Impact

## Configuration Notes

All knobs live in `scripts/config.py`:

- **Dates**: `END_DATE`, `START_DATE` (auto-computed; adjust offset as needed)
- **Voices/model**: `EL_VOICE_*`, `EL_MODEL_ID`, `ANTHROPIC_MODEL`
- **Timing**: `AUDIO_SPEED_FACTOR`, `AUDIO_OFFSET`, `OVERLAY_ANTICIPATION`
- **Overlay style**: `OPENING_STYLE`, `SECTION_STYLE`, `STORY_STYLE1`, `STORY_STYLE2`
- **Rundown layout**: `RUNDOWN_HEADER_STYLE`, `RUNDOWN_LINE_HEIGHT`, etc.
- **Background videos**: `BG_VIDEOS` list, `SECTION_VIDEOS` dict

All media paths are resolved from the project root.

## Troubleshooting

- `ELEVENLABS_API_KEY environment variable is not set` — export the key before running
- `ANTHROPIC_API_KEY environment variable is not set` — export the key before running
- `ffmpeg: command not found` — install FFmpeg and confirm `ffmpeg -version` works
- `Prompt file not found` — confirm `markdown/Weekly_Newsreel_Prompt.md` exists
- `stories.json not found` — run `script_generator.py` (step 1) before later steps
- Missing stock video — check filenames in `SECTION_VIDEOS` and `BG_VIDEOS` in `config.py`
- `No module named 'reportlab'` — install with `pip install reportlab`
- `scripts/client_secrets.json not found` — download OAuth credentials from Google Cloud Console (YouTube Data API v3 must be enabled) and save as `scripts/client_secrets.json`
- `No module named 'googleapiclient'` — install with `pip install google-api-python-client google-auth-oauthlib`
- YouTube upload fails with quota error — YouTube Data API has a daily quota; each upload consumes ~1600 units against a 10,000 unit/day default

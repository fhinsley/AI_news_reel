# ElevenLabsScript

Two automated video pipelines: a weekly AI newsreel and a point-counterpoint political debate.

Both pipelines use Claude (Anthropic) to generate scripts from live web search, produce multi-voice narration via ElevenLabs, assemble a final video with background footage and timed text overlays, and publish to YouTube with closed captions.

---

## Requirements

- Python 3.10+
- FFmpeg installed and available in `PATH`
- ElevenLabs API key in environment variable `ELEVENLABS_API_KEY`
- Anthropic API key in environment variable `ANTHROPIC_API_KEY`
- Google Cloud OAuth credentials for YouTube upload

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

2. For YouTube upload, download OAuth 2.0 credentials from Google Cloud Console (with YouTube Data API v3 enabled) and save as `client_secrets.json` in the project root. On the first run a browser window opens for authorization; the token is saved to `youtube_token.pickle` so subsequent runs are fully headless.

---

## Newsreel Pipeline

Generates a weekly AI news video covering four thematic sections, narrated by five distinct voices.

### What It Does

1. **Generates the script** — Sends a prompt to Claude with web search enabled; Claude fetches current AI news and returns structured JSON stories organized into four sections
2. **Trims stories** — Reduces each story body to a target length at a natural sentence boundary
3. **Generates narration** — Produces six audio clips (intro, four section correspondents, outro) with per-character timestamp alignment via ElevenLabs
4. **Silences artifacts** — Detects brief noise/click artifacts at SSML break-tag boundaries and uses FFmpeg to zero out those regions in-place
5. **Assembles video** — Builds the full newsreel with section-specific background footage, overlay text timed to speech, and a sources list
6. **Generates captions** — Produces a standard SRT file (`Captions.srt`) from the ElevenLabs character-level timestamps
7. **Generates transcript** — Produces a formatted PDF (`Transcript.pdf`) with all stories organized by section, plus a clickable sources list
8. **Uploads to YouTube** — Authenticates via OAuth, uploads `News.mp4` with metadata and tags, attaches the SRT caption track, adds the video to the newsreel playlist, and opens the published video in the browser

### Run

```bash
python run_newsreel.py
```

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `newsreel/script_generator.py` | `markdown/Weekly_Newsreel_Prompt.md` | `MMDDYY/stories.json` |
| 2 | `newsreel/trim_stories.py` | `MMDDYY/stories.json` | `MMDDYY/shortstories.json` |
| 3 | `newsreel/newsreel_tts.py` | `MMDDYY/shortstories.json` | `MMDDYY/00_intro.mp3` … `99_outro.mp3` + timestamp JSONs |
| 4 | `newsreel/silence_artifacts.py` | clip mp3s + timestamp JSONs | mp3s cleaned in-place |
| 5 | `newsreel/build_video.py` | clips + timestamps | `MMDDYY/News.mp4` |
| 6 | `newsreel/generate_srt.py` | timestamp JSONs | `MMDDYY/Captions.srt` |
| 7 | `newsreel/generate_transcript.py` | `MMDDYY/shortstories.json` | `MMDDYY/Transcript.pdf` |
| 8 | `newsreel/upload_youtube.py` | `News.mp4` + `Captions.srt` | published YouTube video (browser opens) |

### Voices

| Role | Voice | Config constant |
|------|-------|----------------|
| Intro / Outro | Clancy | `EL_VOICE_MAIN` |
| Core Tech Releases | Kim | `EL_VOICE_KIM` |
| Directions in AI Architecture | Ryan | `EL_VOICE_RYAN` |
| AI For Productivity | Marcos | `EL_VOICE_MARCOS` |
| World Impact | Clara | `EL_VOICE_CLARA` |

### Sections

Each week covers four fixed sections:

1. Core Tech Releases
2. Directions in AI Architecture
3. AI For Productivity
4. World Impact

### Configuration

All knobs live in `newsreel/config.py`:

- **Dates**: `END_DATE`, `START_DATE` (auto-computed; adjust offset as needed)
- **Voices/model**: `EL_VOICE_*`, `EL_MODEL_ID`, `ANTHROPIC_MODEL`
- **Timing**: `AUDIO_SPEED_FACTOR`, `AUDIO_OFFSET`, `OVERLAY_ANTICIPATION`
- **Overlay style**: `OPENING_STYLE`, `SECTION_STYLE`, `STORY_STYLE1`, `STORY_STYLE2`
- **Rundown layout**: `RUNDOWN_HEADER_STYLE`, `RUNDOWN_LINE_HEIGHT`, etc.
- **Background videos**: `BG_VIDEOS` list, `SECTION_VIDEOS` dict

Output folder is `MMDDYY/` (named from `END_DATE`), created automatically on first run.

---

## Two-Sides Debate Pipeline

Generates a point-counterpoint debate video on a current news topic, with a left debater, a right debater, and a neutral anchor. The debate topic is selected automatically from this week's news, sourced from a balanced mix of left- and right-leaning outlets.

### What It Does

1. **Generates the script** — Claude searches left- and right-leaning sources, selects a debatable proposition, and writes a structured five-segment debate as JSON (`story.json`)
2. **Generates transcript** — Produces a formatted PDF (`DebateTranscriptMMDDYY.pdf`) of the full debate
3. **Generates narration** — Synthesizes three audio clips (anchor intro, opener argument + rebuttal, responder turn, opener closing rebuttal, anchor outro) via ElevenLabs with per-character timestamps
4. **Assembles video** — Builds the debate video with flag background footage tinted blue (left) or red (right), timed overlay text, and a framing card between speakers
5. **Generates captions** — Produces `Captions.srt` from the character-level timestamps
6. **Uploads to YouTube** — Uploads `Debate.mp4` with captions and opens the published video in the browser

### Run

```bash
python run_debate.py
```

Optional flags:

| Flag | Effect |
|------|--------|
| `--skip-script` | Reuse existing `story.json` (skip Claude call) |
| `--skip-tts` | Reuse existing audio files (skip ElevenLabs call) |
| `--skip-upload` | Local render only — skip YouTube upload |

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `debate/script_generator.py` | live web search via Claude | `MMDDYY_debate/story.json` |
| 2 | `debate/generate_transcript.py` | `story.json` | `MMDDYY_debate/DebateTranscriptMMDDYY.pdf` |
| 3 | `debate/tts.py` | `story.json` | `MMDDYY_debate/00–04.mp3` + timestamp JSONs |
| 4 | `debate/build_video.py` | clips + timestamps | `MMDDYY_debate/Debate.mp4` |
| 5 | `debate/generate_srt.py` | timestamp JSONs | `MMDDYY_debate/Captions.srt` |
| 6 | `debate/upload_youtube.py` | `Debate.mp4` + `Captions.srt` | published YouTube video (browser opens) |

### Debate Structure

Each debate has five segments:

| Segment | Speaker | Description |
|---------|---------|-------------|
| Anchor intro | Neutral anchor | Frames the proposition and introduces both sides |
| Opener argument | Opener (random side) | Affirmative case for the proposition |
| Responder turn | Responder | Rebuttal of opener's attacks, then own affirmative case against the proposition |
| Opener rebuttal | Opener | Responds to the responder's argument |
| Anchor outro | Neutral anchor | Summarizes the core disagreement |

Which side opens is chosen randomly each run and recorded in `story.json` so that re-running TTS or video steps without regenerating the script stays in sync.

### Voices

| Role | Voice | Config constant |
|------|-------|----------------|
| Anchor | Clancy | `EL_VOICE_ANCHOR` |
| Left debater | Kim | `EL_VOICE_LEFT` |
| Right debater | Ryan | `EL_VOICE_RIGHT` |

### Topic Selection

Claude searches the following sources each run:

- **Left-leaning**: CNN, MSNBC, NPR, The Atlantic, Washington Post
- **Right-leaning**: Fox News, New York Post, Wall Street Journal, Breitbart, The Federalist

A topic history file (`debate_topic_history.json`) tracks the last 14 days of debate topics so the same subject is not repeated. The history is pruned automatically; entries older than 14 days are dropped and the file is capped at 200 entries.

### Configuration

All knobs live in `debate/config.py`:

- **Voices/model**: `EL_VOICE_ANCHOR`, `EL_VOICE_LEFT`, `EL_VOICE_RIGHT`, `ANTHROPIC_MODEL`
- **Word count targets**: `OPENER_WORDS`, `REBUTTAL_WORDS`, `ARGUMENT_WORDS`, `CLOSING_REBUTTAL_WORDS`, `ANCHOR_INTRO_WORDS`, `ANCHOR_OUTRO_WORDS`
- **Rebuttal strategy**: `REBUTTAL_STRATEGY` dict — weights for full denial, concede-and-pivot, and genuine concession (must sum to 1.0)
- **Overlay style**: `SIDE_LABEL_STYLE`, `ANCHOR_STYLE`, `HEADLINE_STYLE`, `PROPOSITION_STYLE`
- **Background videos**: `LEFT_FLAG_VIDEO`, `RIGHT_FLAG_VIDEO`, `SECTION_VIDEOS`
- **Flag tints**: `FLAG_TINTS` — per-side RGB color and opacity for the flag wash
- **Topic history**: `TOPIC_EXCLUSION_DAYS`, `TOPIC_HISTORY_MAX`

Output folder is `MMDDYY_debate/` (named from `END_DATE`), created automatically on first run.

---

## Project Layout

```
run_newsreel.py             newsreel pipeline runner
run_debate.py               debate pipeline runner
requirements.txt            Python dependencies
newsreel/                   newsreel pipeline scripts
  config.py
  script_generator.py
  trim_stories.py
  newsreel_tts.py
  silence_artifacts.py
  build_video.py
  generate_srt.py
  generate_transcript.py
  upload_youtube.py
  watchnews.py
  makeinoutro.py
debate/                     debate pipeline scripts
  config.py
  script_generator.py
  tts.py
  build_video.py
  generate_srt.py
  generate_transcript.py
  upload_youtube.py
  flip_flag.py
  generate_flag_assets.py
utils/                      standalone utilities
  test_tts_before_11labs.py
  viewscript.py
  extract_entities.py
  video_test.py
markdown/
  Weekly_Newsreel_Prompt.md  newsreel prompt template
stock_videos/               background clips for both pipelines
MMDDYY/                     newsreel weekly output (auto-created)
MMDDYY_debate/              debate weekly output (auto-created)
```

---

## Troubleshooting

- `ELEVENLABS_API_KEY environment variable is not set` — export the key before running
- `ANTHROPIC_API_KEY environment variable is not set` — export the key before running
- `ffmpeg: command not found` — install FFmpeg and confirm `ffmpeg -version` works
- `Prompt file not found` — confirm `markdown/Weekly_Newsreel_Prompt.md` exists
- `stories.json not found` — run `newsreel/script_generator.py` (step 1) before later steps
- `story.json not found` — run `debate/script_generator.py` (step 1) before later steps
- `Claude returned responder_turn without the required key` — Claude used a non-canonical key name; delete `story.json` and rerun `script_generator.py`
- `REBUTTAL_STRATEGY weights must sum to 1.0` — check `debate/config.py` rebuttal weight values
- Missing stock video — check filenames in `SECTION_VIDEOS` and `BG_VIDEOS` in the relevant `config.py`
- `No module named 'reportlab'` — install with `pip install reportlab`
- `client_secrets.json not found` — download OAuth credentials from Google Cloud Console (YouTube Data API v3 must be enabled) and save as `client_secrets.json` in the project root
- `No module named 'googleapiclient'` — install with `pip install google-api-python-client google-auth-oauthlib`
- YouTube upload fails with quota error — YouTube Data API has a daily quota; each upload consumes ~1600 units against a 10,000 unit/day default

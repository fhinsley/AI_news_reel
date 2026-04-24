# ElevenLabsScript

Two automated video pipelines: a weekly AI newsreel and a point-counterpoint debate (news or sports).

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
4. **Optional speed-up pass** — `utils/stretch_audio.py` can time-stretch generated narration clips if you want faster delivery for specific sections
5. **Silences artifacts** — Detects brief noise/click artifacts at SSML break-tag boundaries and uses FFmpeg to zero out those regions in-place
6. **Assembles video** — Builds the full newsreel with section-specific background footage, overlay text timed to speech, broadcast-style lower-third chyrons with source attribution, a music sting and ambient bed, and a sources list
7. **Generates captions** — Produces a standard SRT file (`Captions.srt`) from the ElevenLabs character-level timestamps
8. **Generates transcript** — Produces a formatted PDF (`Transcript.pdf`) with all stories organized by section, plus a clickable sources list
9. **Uploads to YouTube (optional)** — Authenticates via OAuth, uploads `News.mp4` with metadata and tags, attaches the SRT caption track, adds the video to the newsreel playlist, and opens the published video in the browser

### Run

```bash
python run_newsreel.py
```

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `newsreel/script_generator.py` | `markdown/Weekly_Newsreel_Prompt.md` | `MMDDYY/stories.json` |
| 2 | `newsreel/newsreel_tts.py` | `MMDDYY/stories.json` | `MMDDYY/00_intro.mp3` … `99_outro.mp3` + timestamp JSONs |
| 3 | `utils/stretch_audio.py` (optional) | clip mp3s | time-stretched clip mp3s (in-place) |
| 4 | `newsreel/silence_artifacts.py` | clip mp3s + timestamp JSONs | mp3s cleaned in-place |
| 5 | `newsreel/build_video.py` | clips + timestamps | `MMDDYY/News.mp4` |
| 6 | `newsreel/generate_srt.py` | timestamp JSONs | `MMDDYY/Captions.srt` |
| 7 | `newsreel/generate_transcript.py` | `MMDDYY/stories.json` | `MMDDYY/Transcript.pdf` |
| 8 | `newsreel/upload_youtube.py` (optional) | `News.mp4` + `Captions.srt` | published YouTube video |

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
- **Overlay style**: `OPENING_STYLE`, `SECTION_STYLE`, `STORY_STYLE1`, `LOWER_THIRD_*`
- **Rundown layout**: `RUNDOWN_HEADER_STYLE`, `RUNDOWN_LINE_HEIGHT`, etc.
- **Background videos**: `BG_VIDEOS` list, `SECTION_VIDEOS` dict
- **Voice volume**: `VOICE_VOLUME_BOOST` dict — per-section dB boost to normalize loudness across voices
- **Music**: `MUSIC_STING_FILE`, `MUSIC_BED_FILE`, `MUSIC_STING_VOLUME`, `MUSIC_BED_VOLUME`, `MUSIC_STING_DURATION`, `MUSIC_STING_FADE_OUT`

Output folder is `MMDDYYNewsreel/` (named from `END_DATE`), created automatically on first run.

### Music

Place MP3 files in `music/news/` (gitignored — not checked in):

| Config key | Default filename | Role |
|---|---|---|
| `MUSIC_STING_FILE` | `breaking-news.mp3` | One-shot intro sting played at full volume, fades out over `MUSIC_STING_FADE_OUT` seconds |
| `MUSIC_BED_FILE` | `independence-day.mp3` | Looping ambient bed played at low volume (`MUSIC_BED_VOLUME`) under the narration |

The sting plays from `t=0`; the bed starts when narration begins. Both mix with the narration via `CompositeAudioClip`. If either file is missing the pipeline continues without it.

---

## Two-Sides Debate Pipeline

Generates a point-counterpoint debate video on a current news or sports topic, narrated by two debaters and a neutral anchor. The debate topic is selected automatically from this week's news; the mode (news or sports) is set in `debate/config.py`.

### What It Does

1. **Generates the script** — Claude searches mode-appropriate sources, selects a debatable proposition, and writes a structured five-segment debate as JSON (`story.json`)
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
| 1 | `debate/script_generator.py` | live web search via Claude | `MMDDYYNewsDebate/` or `MMDDYYSportsDebate/story.json` |
| 2 | `debate/generate_transcript.py` | `story.json` | `…/DebateTranscriptMMDDYY.pdf` |
| 3 | `debate/tts.py` | `story.json` | `…/00–04.mp3` + timestamp JSONs |
| 4 | `debate/build_video.py` | clips + timestamps | `…/Debate.mp4` |
| 5 | `debate/generate_srt.py` | timestamp JSONs | `…/Captions.srt` |
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

### Debate Mode

Set `DEBATE_MODE` in `debate/config.py` before running:

| Mode | `DEBATE_MODE` | Sides | Tone |
|------|--------------|-------|------|
| News | `"news"` | Left Perspective vs Right Perspective | Reasoned, Socratic; concede-and-pivot common |
| Sports | `"sports"` | Traditionalist vs Analytics | Combative talk-radio; flat denial dominates |

The mode controls the system prompt, source lists, side labels (used in overlays), rebuttal strategy weights, and the output folder name (`MMDDYYNewsDebate` or `MMDDYYSportsDebate`).

### Topic Selection

Claude searches mode-appropriate sources each run:

**News mode**
- **Left-leaning**: CNN, MSNBC, NPR, The Atlantic, Washington Post
- **Right-leaning**: Fox News, New York Post, Wall Street Journal, Breitbart, The Federalist

**Sports mode**
- **Traditionalist**: ESPN, CBS Sports, Sports Illustrated, Bleacher Report, Pro Football Talk
- **Analytics**: The Athletic, FiveThirtyEight, Football Outsiders, Pro Football Reference, Stathead

Each mode maintains its own topic history file (`debate_topic_history.json` for news, `sport_debate_topic_history.json` for sports) so histories don't cross-contaminate. Entries older than 14 days are pruned automatically; files are capped at 200 entries.

### Configuration

All knobs live in `debate/config.py`:

- **Mode**: `DEBATE_MODE` — `"news"` or `"sports"`
- **Voices/model**: `EL_VOICE_ANCHOR`, `EL_VOICE_LEFT`, `EL_VOICE_RIGHT`, `ANTHROPIC_MODEL`
- **Word count targets**: `OPENER_WORDS`, `REBUTTAL_WORDS`, `ARGUMENT_WORDS`, `CLOSING_REBUTTAL_WORDS`, `ANCHOR_INTRO_WORDS`, `ANCHOR_OUTRO_WORDS`
- **Rebuttal strategy**: `REBUTTAL_STRATEGY` dict — auto-selected by mode; weights for full denial, concede-and-pivot, and genuine concession (must sum to 1.0)
- **Overlay style**: `SIDE_LABEL_STYLE`, `ANCHOR_STYLE`, `HEADLINE_STYLE`, `PROPOSITION_STYLE`
- **Background videos**: `LEFT_FLAG_VIDEO`, `RIGHT_FLAG_VIDEO`, `SECTION_VIDEOS`
- **Flag tints**: `FLAG_TINTS` — per-side RGB color and opacity for the flag wash
- **Topic history**: `TOPIC_EXCLUSION_DAYS`, `TOPIC_HISTORY_MAX`

Output folder is `MMDDYYNewsDebate/` or `MMDDYYSportsDebate/` (named from `END_DATE` and mode), created automatically on first run.

---

## Project Layout

```
run_newsreel.py             newsreel pipeline runner
run_debate.py               debate pipeline runner
requirements.txt            Python dependencies
newsreel/                   newsreel pipeline scripts
  config.py
  script_generator.py
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
  stretch_audio.py
  test_tts_before_11labs.py
  viewscript.py
  video_test.py
markdown/
  Weekly_Newsreel_Prompt.md  newsreel prompt template
stock_videos/               background clips for both pipelines
music/
  news/                     news music files (mp3s gitignored — add your own)
    breaking-news.mp3       intro sting (configure via MUSIC_STING_FILE)
    independence-day.mp3    ambient bed (configure via MUSIC_BED_FILE)
MMDDYYNewsreel/             newsreel weekly output (auto-created)
MMDDYYNewsDebate/           news debate weekly output (auto-created)
MMDDYYSportsDebate/         sports debate weekly output (auto-created)
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

# AI Newsreel Pipeline
### Automated Media Production — Case Study
*From raw RSS feeds to finished broadcast video, fully automated.*
*Internal · 2025–2026*

---

## Slide 1 — Title

**AI Newsreel Pipeline**

From raw RSS feeds to finished broadcast video — fully automated.

---

## Slide 2 — The Problem Worth Solving

Every week, there's a mountain of AI news. The goal was simple: turn that into a polished video digest that plays at internal company meetings — something people actually watch.

**The Goal**
Weekly AI news digest video for internal company meetings — to stay visible during a career transition from engineering to data science.

**The Constraint**
Fully extracurricular. No budget, no team, no formal credit. Must be repeatable every week without manual effort eating up all the ROI.

> *"Let the job find me" — visibility through demonstrated craft, not resume keywords.*

---

## Slide 3 — Five-Stage Pipeline

The pipeline has five stages. Each one is a discrete concern, and they hand off cleanly to the next.

**01 — Ingest**
Five sources. The Batch, Import AI, TLDR AI, CNBC, MIT Tech Review. Fetched and parsed each run.

**02 — Script**
Claude API generates a formatted script from the ingested stories. Structured, consistent, ready for narration.

**03 — Audio**
ElevenLabs text-to-speech converts the script to an MP3, and returns character-level timestamps we'll use later.

**04 — Post**
ffmpeg handles post-processing: audio artifacts are silenced, speed is reduced to 0.9×, and a two-second intro delay is added.

**05 — Video**
MoviePy assembles the final MP4: background video cycling, text overlays timed to the narration.

*One design rule across all of it: `config.py` holds every constant. No magic values live in execution files.*

---

## Slide 4 — Under the Hood

Three Python modules carry most of the weight.

**`newsreel_tts.py`**
Handles the ElevenLabs API call. Model selection matters here — turbo and multilingual behave differently, especially around pause artifacts. This module saves the MP3 and the timestamps JSON. One hard-learned rule: strip newlines from the script before the API call, or you get silent failures.

**`silence_artifacts.py`**
Break tags in the script — the kind used to add pauses — generate metallic pops in the audio. This module auto-detects those artifacts by analyzing the waveform and silences them in place before they reach the final mix.

**`build_video.py`**
Assembles the video using MoviePy 2.x — which is not a drop-in upgrade from 1.x; import paths changed significantly. Background videos cycle at section and story change points. Title overlays run in two phases: first centered and prominent, then tucked to the bottom-right as a reminder while narration continues.

---

## Slide 5 — What Broke and What We Learned

Every project has a list of things that burned time. Here's ours.

**ElevenLabs Models**
Turbo vs. multilingual behave differently on pause artifacts. Model selection is not cosmetic — it affects audio quality in ways you don't see until you listen.

**Break Tag Artifacts**
Break tags in SSML generate metallic pops. We detect them via waveform analysis and silence them in post. The fix works; finding the cause took longer than it should have.

**Newline Stripping**
Embedded newlines in script text cause silent API failures — no error, no audio, no indication of what went wrong. Strip before every TTS call. Always.

**ffmpeg Post-Process**
Speed reduction to 0.9× via `atempo`, plus the two-second intro delay, are applied cleanly in ffmpeg. Trying to do this in MoviePy introduced sync drift. Let each tool do what it's good at.

**MoviePy 2.x Imports**
Import paths changed significantly from 1.x. It is not a drop-in upgrade. Verify every import individually when upgrading.

**Timestamp Speed Adjustment**
ElevenLabs returns character-level timestamps based on the original audio. After slowing to 0.9×, every timestamp must be divided by the speed factor to stay in sync. Miss this and all your overlays are early.

---

## Slide 6 — Technologies and Tools

**APIs**
- Claude (Anthropic) — script generation
- ElevenLabs TTS — narration and timestamps
- 5× RSS and web sources — The Batch, Import AI, TLDR AI, CNBC, MIT Tech Review

**Audio / Video**
- ffmpeg — speed adjustment, artifact silencing, intro delay
- MoviePy 2.x — video assembly and overlay
- ElevenLabs character-level timestamps — overlay timing

**Python**
- requests / BeautifulSoup — feed fetching and parsing
- json / pathlib / os — file and data handling
- subprocess — ffmpeg invocation

**Design Decisions**
- `config.py` — single source of truth for all constants
- Modular files, one concern per file
- No constants in execution files

---

## Slide 7 — Why This Project Exists

This isn't just a pipeline. It's a strategy.

**Visibility** over keywords — internal decision-makers see the work, not just the title.

**Demonstrated craft** in GenAI tooling, API orchestration, and data pipeline thinking — the exact skills the target role requires.

**Consistent delivery** — a weekly cadence signals reliability, not just capability. Anyone can build a thing once.

**Results**
- Running weekly with consistent internal distribution
- Live demo at the Friday morning AI discussion group
- The visibility goal is working — AI compliance collaboration has come from it

**Next**
Fully lights-out publishing pipeline — auto-scheduling the final output without any manual steps remaining.

---

*Fred · M.S. Data Science, December 2025 · Mutual of Omaha · Workplace Solutions*

Y# AI Newsreel — Slide Content Outline
### Presenter-driven. Slides are the backdrop, not the script.

---

## SLIDE 1 — Title

**The AI Newsreel**
*How a weekly briefing became an automated video pipeline*

---

## SLIDE 2 — Where It Started

Nathalie started it.

As principal data scientist she established the format, the sources, the editorial philosophy. When she handed it off in early February 2026, she handed off something that already worked.

This is the story of what happened next.

*[Speaker: This is where you mention Eye of the Tiger if you're going to. It earns a smirk from at least one developer in the back row.]*

---

## SLIDE 3 — The Philosophy

> "A factual weekly briefing on generative AI developments,
> designed to inform — not persuade or hype."

- Factual
- Concise
- Faithful to sources
- No synthesis. No speculation. No grand conclusions.

*[Speaker: This philosophy has not changed. Everything that has changed is in service of it.]*

---

## SLIDE 4 — The Original Prompt

*[Show the prompt text — format as a code block or quoted text]*

```
You and I are copy editors. We're creating copy for a newsreel
that examines news releases from the last 7 days concerning
generative AI.

Our voice is factual, straight to the point, concise, and favors
directly representing the news sources through quotes and
fact-checked paraphrasing.

We avoid grand statements, overarching synthesis, and hype.

The newsreel is divided into sections. Let's work on [SECTION NAME].
This section should take [TIME] maximum.

The content must be exactly faithful to the following sources.
Quote liberally. Do not add facts or opinions.
```

Run once per section. Four sections. Four conversations. Every week.

---

## SLIDE 5 — The Script

The prompt produces a structured script — four named sections,
story titles, paragraphs, and timing markers.

*[Show a short excerpt — opening lines through first story title and a few sentences]*

The formatting is not for readability.
It is for the voice engine downstream.

Every rule in the script is an audio engineering decision
written as a writing rule.

---

## SLIDE 6 — How It Was Made (The Clipchamp Era)

*[Full slide: the Clipchamp screenshot]*

**One episode. Built by hand.**

- ElevenLabs web interface — 5,000 character limit per conversion
- Script split into chunks to fit the window
- Each chunk converted separately, downloaded as individual MP3s
- Audio reassembled in Clipchamp
- Stock video selected and dragged to the timeline manually
- Text overlays placed by hand — one at a time

10 minutes of finished video.
Every week.

---

## SLIDE 7 — The Pipeline

What replaced it.

```
News.txt  →  TTS  →  Post-Processing  →  Video Assembly  →  MP4
```

| Stage | Tool | What it does |
|---|---|---|
| Script | Claude API | Generates formatted copy from five sources |
| Audio | ElevenLabs API | Converts script to MP3, returns timestamps |
| Post | ffmpeg | Silences artifacts, adjusts speed, adds intro delay |
| Video | MoviePy | Assembles MP4 with background video and timed overlays |

One config file. No magic values in execution scripts.

*[Speaker: The folder starts empty. By the end of the demo it has everything in it.]*

---

## SLIDE 8 — Improvement: Voice and Model Selection

ElevenLabs offers multiple models.

**Turbo** — fast, lower latency, more artifact-prone at pause markers

**Multilingual v2** — slower to generate, cleaner output around SSML tags

Model selection is not cosmetic. It affects what comes out of the speaker.

The current production model was chosen by listening, not by reading a spec sheet.

---

## SLIDE 9 — Improvement: The Character Ceiling

The ElevenLabs web interface has a hard limit of 5,000 characters.

That limit drove the Clipchamp workflow — split, convert, reassemble.

Moving to the API removed the limit in theory.
In practice, a new ceiling was engineered deliberately:

**9,500 characters — hard limit, encoded in the prompt.**

A script that runs too long sounds rushed.
The ceiling is a production quality decision, not a technical constraint.

---

## SLIDE 10 — Improvement: Artifact Removal

SSML break tags tell the voice engine to pause.

They also generate metallic pops in the audio output — audible artifacts
at predictable positions in the waveform.

*[Speaker: Play the before clip here.]*

`silence_artifacts.py` detects these regions automatically
by analyzing the waveform and silences them before the final mix.

*[Speaker: Play the after clip here.]*

The prompt formatting rules — blank line before every break tag,
never immediately after a period — reduce how many artifacts are generated.
The silencer catches what gets through.

---

## SLIDE 11 — Improvement: Speed and Sync

The natural ElevenLabs output pace sounded slightly fast.

Two options were tried:
- Set a slower speaking rate in ElevenLabs directly
- Apply speed reduction in post via ffmpeg

**ffmpeg won.** The ElevenLabs rate setting changed the voice character.
ffmpeg's `atempo` filter at 0.9x preserved it.

The complication: ElevenLabs returns character-level timestamps
based on the original audio duration.

After slowing to 0.9x, every timestamp must be divided by 0.9
to stay synchronized with the slowed audio.

Miss that step and every text overlay appears early.

---

## SLIDE 12 — Improvement: Automated Overlays

ElevenLabs returns a timestamps JSON file alongside the MP3.

Each character in the script has a position in time.

`build_video.py` uses those timestamps to place text overlays
at the exact moment each story title is spoken —
no manual placement, no timeline dragging.

Two-phase overlay logic:
- **Center screen, large** — when the title is first announced
- **Bottom right, smaller** — as a reminder while the story plays

Background video cycles automatically at section boundaries and story changes.

*[Speaker: This is the part that replaced the Clipchamp timeline.]*

---

## SLIDE 13 — What the Prompt Became

*[Show current prompt — or key sections of it]*

The same four sections. The same editorial philosophy.

What changed:

- Single prompt, complete script in one pass
- Five specific URLs fetched directly — no broad search
- Hard character ceiling
- Break tag formatting rules
- AP style, no em dashes, numbers spelled out
- Content filter — topics that don't belong in a mixed corporate audience

Each rule is a scar from something that produced bad output.

---

## SLIDE 14 — The Step That Still Exists

*[Show: chat window open, prompt pasted, output being copied into News.txt]*

This is the last human step in the content pipeline.

Prompt runs in a chat window.
Output gets copied.
Pasted into News.txt.
Pipeline takes it from there.

This step goes away next.

---

## SLIDE 15 — What's Next

**API call replaces the chat window.**
The script is fetched programmatically and written to the file automatically.

**Scheduled delivery.**
A job runs Friday morning. The newsreel produces itself.

The human-in-the-loop moments visible in this demo
are the last ones.

---

## SLIDE 16 — Close

Nathalie's guide closed with one instruction:

> *"No optimization beyond that."*

That instruction was followed for approximately one week.

What exists now is a demonstration that the instinct to automate
is itself a data science instinct —
find the repeatable process,
remove the human from the loop where the human adds no value,
and redirect that attention toward the parts that still require judgment.

The prompt monitoring. The content filter.
The editorial call about what belongs in a Friday morning meeting.

Those parts are still human.

Everything else runs.

---

*In production since February 20, 2026*

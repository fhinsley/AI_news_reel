# The first prompt

## The Newsreel Creation Guide (Handoff Version)

### Purpose of the Newsreel

The newsreel is a factual weekly briefing on generative AI developments from the previous 7 days, designed to inform, not persuade or hype.

Voice and posture:

- Factual
- Concise
- Quote-heavy
- Faithful to sources
- No synthesis, speculation, or grand conclusions

### Step 1: Source Intake (What You Scan Each Week)

| Source | Why it is used |
| --- | --- |
| The Batch (DeepLearning.ai) | Research and why it matters framing |
| Import AI (Jack Clark) | Policy, safety, frontier implications |
| TLDR AI | Fast scan of releases |
| The Rundown AI | Adoption and tooling |
| AlphaSignal | What developers are actually using |

Rule:
You are not trying to read everything, you are triaging signal.

### Step 2: Lock the Structure (Timing Is Fixed)

Across all three meetings, the timebox never changes:

| Segment | Time |
| --- | --- |
| Intro and rundown | 1 min |
| Tech releases | 1 min |
| Directions in AI architecture | 4-5 min |
| AI for productivity (coding agents) | 2 min |
| Impact on the world | 1-2 min |

Key constraint:
If something does not fit the time, it does not go in.

### Step 3: Weekly Section Definitions (What Belongs Where)

These definitions were stated almost verbatim in the meetings.

#### Section 1: Core Tech Releases (1 min)

Only: newly released models, capabilities, or system-level changes.

Examples used in handoff:

- Gemini 3 Deep Think
- Claude Sonnet 4.6

Disallowed: opinions, benchmarks not in sources, this is big commentary.

#### Section 2: Directions in AI Architecture (4-5 min)

This is the conceptual heart of the reel.

Recurring sub-buckets:

- Better agents and closed-loop systems
- Personalization effects
- Human factors (for example, cognitive debt)

Rule:
Each idea should stand alone. No synthesis across them.

#### Section 3: AI for Productivity (2 min)

Focused almost entirely on coding agents and developer experience.

Examples Nathalie explicitly used:

- Coding Agents in Feb 2026
- Developer backlash to hidden AI actions

#### Section 4: Impact on the World (1-2 min)

This is economic, regulatory, or structural impact, not vibes.

Used examples:

- AI safety conflicts
- Market structure arguments
- One person startup dynamics

### Step 4: Script Generation (This Is the Secret Sauce)

From AI News Tips and Tricks II, Nathalie shared the exact prompt pattern she uses.

#### Master Prompt Template (Reusable)

```text
You and I are copy editors. We're creating copy for a newsreel
that examines news releases from the last 7 days concerning generative AI.

Our voice is factual, straight to the point, concise, and favors
directly representing the news sources through quotes and
fact-checked paraphrasing.

We avoid grand statements, overarching synthesis, and hype.

The newsreel is divided into sections. Let's work on [SECTION NAME].
This section should take [TIME] maximum.

The content must be exactly faithful to the following sources.
Quote liberally. Do not add facts or opinions.
```

This template appears multiple times, section-specific, in the meeting chat.

### Step 5: Assembly and Delivery

What Nathalie did not overcomplicate:

- No transitions between sections
- No concluding summary
- No opinionated wrap-up

Each section is self-contained, read cleanly, and time-checked.

Tooling note: She referenced an internal Create capability she expected to demo later, but did not document a required tool yet.

### Your One-Page Weekly Checklist

Every week, do exactly this:

1. Scan the 5 sources
2. Select 1-2 items per section
3. Lock timing
4. Generate scripts section-by-section using the prompt
5. Read, record, done

No optimization beyond that.

### What This Guide Intentionally Leaves Out

- Audience reaction
- Engagement metrics
- Strategic positioning
- Predictions

Those were explicitly avoided in Nathalie's approach.

If you want, next we can:

- Turn this into a personal checklist doc
- Create a single master prompt you reuse weekly
- Or map this directly to your Friday LLM prep cadence

## The current prompt

Generate this week's AI newsreel script for the week of [START DATE] through [END DATE].

<!-- BROAD SEARCH APPROACH - kept for reference
     Higher session usage, can trigger rate limits on paid plans.

Search broadly for this week's top AI stories across reputable technology and AI news outlets.
Summarize findings internally. Write the script directly from your research.
-->

<!-- TARGETED FETCH APPROACH - current production method
     Five direct URL fetches. Same story quality, fraction of the session usage. -->
Fetch content from each of the following five sources and write the script
directly from what you find. Do not include raw article text in your response.

- https://www.deeplearning.ai/the-batch/
- https://jack-clark.net/
- https://tldr.tech/ai
- https://www.cnbc.com/artificial-intelligence/
- https://www.technologyreview.com/topic/artificial-intelligence/

Follow these formatting rules exactly:

### OPENING

- First line: Welcome to the AI Newsreel. This is a weekly summary of the news in AI for the week of [DATE RANGE].
- Break tag
- Paragraph beginning with exactly: This week:
- Break tag
- Exactly: Here is what happened.
- Break tag

### SECTIONS in this exact order with these exact names

- Core Tech Releases
- Directions in AI Architecture
- AI For Productivity
- World Impact

### EACH SECTION

- Section name on its own line
- Break tag
- Story title on its own line, under 60 characters, no period at end
- Break tag
- Story paragraph(s)
- Break tag after each paragraph

### CLOSING

- Exactly: That is your weekly summary of this week's AI news.
- Break tag
- Exactly: Sources this week: [comma-separated sources]

### BREAK TAG FORMAT

Always blank line before break tag. Never immediately after a period.
Use <break time="2s" /> before section headers.
Use <break time="1s" /> before story titles and between paragraphs.

### STYLE

- AP wire style
- No em dashes, use commas instead
- No hyphens in spoken compound adjectives
- No ALL CAPS
- No superlatives or editorializing
- Attribution for strong claims
- Spell out numbers when spoken
- Target 8,500 to 9,500 characters total

### CONTENT FILTER - avoid

- Litigation or lawsuits between AI companies and government
- Politically polarizing topics
- Stories that could divide a mixed corporate audience

## The first week with eleven labs

Then get the audio files.
Split in 2 tbecause of website 5000 character limit.
Then 2 audio files pasted together in clipchamp where test overlays and stock vedeos were selected.

So pipeline was prompt to text to eleven labs (split to fit) then create video in clipchamp from audio files and add the title ans story overlays lining them up to the audio by ear (manually)
Tedious but not bad for a single small video or 2.

## Clipchamp

Open Clipchamp, show how that works.

Then go into the improvements.

Ttalk mabout the challenges of the audio voices.

The correct decisions and why.

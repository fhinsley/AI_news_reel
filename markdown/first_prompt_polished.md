# The First Prompt

## Newsreel Creation Guide (Handoff)

### Purpose

The newsreel is a factual weekly briefing on generative AI developments from the prior seven days. It is designed to inform, not persuade or hype.

Editorial posture:

- Factual
- Concise
- Quote-heavy
- Faithful to sources
- No synthesis, speculation, or grand conclusions

## 1. Source Intake (Weekly Scan)

| Source | Why it is used |
| --- | --- |
| The Batch (DeepLearning.ai) | Research depth and why-it-matters context |
| Import AI (Jack Clark) | Policy, safety, and frontier implications |
| TLDR AI | Fast release scan |
| The Rundown AI | Adoption and tooling coverage |
| AlphaSignal | What developers are actively using |

Rule: this is signal triage, not exhaustive reading.

## 2. Lock the Structure (Timing Is Fixed)

The timebox does not change:

| Segment | Time |
| --- | --- |
| Intro and rundown | 1 minute |
| Core tech releases | 1 minute |
| Directions in AI architecture | 4-5 minutes |
| AI for productivity (coding agents) | 2 minutes |
| World impact | 1-2 minutes |

Constraint: if a story does not fit the timebox, it is excluded.

## 3. Section Definitions

### Section 1: Core Tech Releases (1 minute)

Include only newly released models, capabilities, or system-level changes.

Examples:

- Gemini 3 Deep Think
- Claude Sonnet 4.6

Exclude opinions, unverified benchmark claims, and hype framing.

### Section 2: Directions in AI Architecture (4-5 minutes)

This is the conceptual center of the reel.

Recurring sub-buckets:

- Better agents and closed-loop systems
- Personalization effects
- Human factors (for example, cognitive debt)

Rule: each idea stands alone. Avoid synthesis across items.

### Section 3: AI for Productivity (2 minutes)

Focus on coding agents and developer workflow impact.

Examples used in handoff:

- Coding Agents in Feb 2026
- Developer backlash to hidden AI actions

### Section 4: World Impact (1-2 minutes)

Cover economic, regulatory, or structural impact, not general sentiment.

Examples:

- AI safety conflicts
- Market structure arguments
- One person startup dynamics

## 4. Script Generation (Core Prompt Pattern)

From AI News Tips and Tricks II, Nathalie shared this reusable template:

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

## 5. Assembly and Delivery

Keep production simple:

- No transitions between sections
- No concluding summary
- No opinionated wrap-up

Each section should be self-contained, cleanly read, and time-checked.

Note: an internal Create capability was mentioned in the handoff, but no required tool workflow was documented.

## Weekly Checklist

1. Scan the five sources.
2. Select one to two items per section.
3. Lock timing.
4. Generate script copy section by section with the prompt template.
5. Read, record, done.

## What This Approach Intentionally Excludes

- Audience reaction metrics
- Engagement optimization
- Strategic positioning
- Predictions

## Current Production Prompt

Generate this week's AI newsreel script for the week of [START DATE] through [END DATE].

<!-- BROAD SEARCH APPROACH - kept for reference
Higher session usage, can trigger rate limits on paid plans.

Search broadly for this week's top AI stories across reputable technology and AI news outlets.
Summarize findings internally. Write the script directly from your research.
-->

<!-- TARGETED FETCH APPROACH - current production method
Five direct URL fetches. Similar quality, much lower session usage. -->
Fetch content from each of the following five sources and write the script directly from what you find. Do not include raw article text in your response.

- https://www.deeplearning.ai/the-batch/
- https://jack-clark.net/
- https://tldr.tech/ai
- https://www.cnbc.com/artificial-intelligence/
- https://www.technologyreview.com/topic/artificial-intelligence/

Follow these formatting rules exactly:

### Opening

- First line exactly: Welcome to the AI Newsreel. This is a weekly summary of the news in AI for the week of [DATE RANGE].
- Break tag
- Paragraph beginning exactly: This week:
- Break tag
- Exactly: Here is what happened.
- Break tag

### Sections (in this order, with exact names)

- Core Tech Releases
- Directions in AI Architecture
- AI For Productivity
- World Impact

### For Each Section

- Section name on its own line
- Break tag
- Story title on its own line, under 60 characters, no period at the end
- Break tag
- Story paragraph(s)
- Break tag after each paragraph

### Closing

- Exactly: That is your weekly summary of this week's AI news.
- Break tag
- Exactly: Sources this week: [comma-separated sources]

### Break Tag Format

Always include a blank line before a break tag. Never place a break tag immediately after a period.

- Use <break time="2s" /> before section headers.
- Use <break time="1s" /> before story titles and between paragraphs.

### Style Constraints

- AP wire style
- No em dashes, use commas instead
- No hyphens in spoken compound adjectives
- No ALL CAPS
- No superlatives or editorializing
- Attribute strong claims
- Spell out spoken numbers
- Target 8,500 to 9,500 total characters

### Content Filter (Avoid)

- Litigation or lawsuits between AI companies and government
- Politically polarizing topics
- Stories likely to divide a mixed corporate audience

## First Week with ElevenLabs (Historical Process)

Initial workflow:

1. Generate script from prompt.
2. Split text into two parts due to 5,000-character website limits.
3. Generate two audio files in ElevenLabs.
4. Combine the audio files in Clipchamp.
5. Add title and story overlays manually.
6. Align overlays to audio by ear.

This worked for one or two small videos, but was labor intensive.

## Clipchamp Notes

- Open Clipchamp and demonstrate baseline workflow.
- Review improvements made after initial version.
- Discuss challenges with voice quality and selection.
- Capture which decisions were correct and why.

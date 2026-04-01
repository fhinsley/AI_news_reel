# AI Newsreel — Weekly Generation Prompt

## How to use this
Start a fresh Claude conversation each week. Paste the prompt below, filling in the date.
The script format rules are enforced by the Python pipeline — do not deviate from them.

---

## Weekly Prompt

Generate this week's AI newsreel script for the week of [START_DATE] through [END_DATE].

Search broadly for this week's top AI stories across reputable technology and AI news outlets.

Summarize findings internally — do not include raw article text in your response.
Write the script directly from your research.

Follow these formatting rules exactly — the video production pipeline depends on them:

**Opening:**
- First line: Welcome to the AI Newsreel. This is a weekly summary of the news in AI
  for the week of [DATE RANGE].
- Follow with a break tag
- Next paragraph must begin with exactly: This week:
- One sentence per story in the rundown, period-separated
- Follow with a break tag
- Next line must be exactly: Here is what happened.
- Follow with a break tag

**Sections — use these exact names in this exact order:**
1. Core Tech Releases
2. Directions in AI Architecture
3. AI For Productivity
4. World Impact

**Each section:**
- Section name on its own line
- Break tag after section name
- Each story title on its own line, under 60 characters, no period at the end
- Break tag after story title
- Story paragraph(s)
- Break tag after each paragraph

**Closing:**
- Must include exactly: That is your weekly summary of this week's AI news.
- Follow with a break tag
- Final line must begin with exactly: Sources this week:
- Comma-separated list of sources used

---

## Break Tag Format
Every break tag must have a blank line before it. Never place a break tag
immediately after a period on the next line.

Correct:
    ...end of sentence.

    <break time="1s" />

Wrong:
    ...end of sentence.
    <break time="1s" />

Use these durations:
- <break time="2s" /> before section headers
- <break time="1s" /> before story titles and between paragraphs
- <break time="500ms" /> is no longer used — replace with <break time="1s" />

---

## Style Rules
- AP wire style throughout
- No em dashes (—) anywhere — use commas instead
- No hyphens in spoken compound adjectives — "AI driven" not "AI-driven"
- No ALL CAPS
- No superlatives (most significant, most respected, etc.)
- No editorializing or thematic connective tissue between stories
- Attribution for strong claims: "according to Bloomberg" not stated as fact
- Numbers spoken out: "seven hundred forty-four billion" not "744 billion"
- Abbreviations: spell out on first use if potentially unclear when spoken

---

## Fixed Phrases the Pipeline Depends On
These must appear verbatim or the video overlays will break:

| Phrase | Purpose |
|--------|---------|
| `This week:` | Triggers rundown overlay |
| `Here is what happened.` | Ends rundown overlay |
| `That is your weekly summary` | Triggers outro video |
| `Sources this week:` | Triggers sources overlay |
| `Core Tech Releases` | Section header (exact) |
| `Directions in AI Architecture` | Section header (exact) |
| `AI For Productivity` | Section header (exact) |
| `World Impact` | Section header (exact) |

---

## Story Title Rules
Story titles are detected by the pipeline using these criteria:
- On their own line
- Under 60 characters
- Does not end with a period
- Is not a section header
- Does not start with `<break`
- Does not start with `Sources this week`

---

## Target Length
- 8 to 10 minutes spoken at natural pace
- Approximately 7,500 to 9,500 characters including break tags
- 3 to 4 stories per section is typical

---

## Content Filter
Avoid stories involving:
- Litigation or lawsuits between AI companies and government
- Politically polarizing topics
- Any story that could divide a mixed corporate audience

---

## Example Script Structure

```
Welcome to the AI Newsreel. This is a weekly summary of the news in AI for the week of March 19 through 26, 2026.

<break time="1s" />

This week: OpenAI launched a shopping feature in ChatGPT. Apple confirmed a redesigned Siri powered by Google's AI. DeepSeek V4 remains unreleased. And Oracle announced plans for major layoffs with AI cited as a contributing factor.

<break time="1s" />

Here is what happened.

<break time="2s" />

Core Tech Releases

<break time="1s" />

ChatGPT Shopping and the Agentic Commerce Protocol

<break time="1s" />

OpenAI launched a shopping feature in ChatGPT this week...

<break time="1s" />

[next story title]

<break time="1s" />

[story paragraph]

<break time="2s" />

Directions in AI Architecture

[... continue pattern ...]

<break time="2s" />

That is your weekly summary of this week's AI news.

<break time="1s" />

Sources this week: Bloomberg, OpenAI, Reuters, CNBC, MIT Technology Review.
```

Fetch content from each of the following five sources for the week of [START DATE] through [END DATE].
Do not include raw article text in your response. Research and summarize internally, then write the output below.

SOURCES:

- https://jack-clark.net/
- https://syncedreview.com/
- https://www.cnbc.com/artificial-intelligence/
- https://www.technologyreview.com/topic/artificial-intelligence/
- https://simonwillison.net/

---

OUTPUT FORMAT:
Respond with a single valid JSON object. No preamble, no explanation, no markdown fences. Just the JSON.

Schema:

{
  "week_of": "[START DATE] to [END DATE]",
  "sections": [
    {
      "section": "Core Tech Releases",
      "stories": [
        {
          "title": "Story title under 60 characters, no period",
          "body": "Story text, 300 to 500 characters",
          "source_name": "Publication name",
          "source_url": "https://..."
        }
      ]
    },
    {
      "section": "Directions in AI Architecture",
      "stories": [...]
    },
    {
      "section": "AI For Productivity",
      "stories": [...]
    },
    {
      "section": "World Impact",
      "stories": [...]
    }
  ]
}

SECTIONS — use these names exactly, in this order:
1. Core Tech Releases
2. Directions in AI Architecture
3. AI For Productivity
4. World Impact

STORY COUNT:
- Minimum 2 stories per section, maximum 3.
- Drop a story slot rather than padding with a weak story.

BODY LENGTH:
- Each body must be 300 to 500 characters.
- Count carefully. Do not go under 300 or over 500.
- That is roughly 50 to 80 words of tight broadcast copy.
- Lead with the most newsworthy fact. Additional context in order of importance.

BODY STYLE:
- AP wire style.
- Short, direct sentences. No multi-clause sentences.
- No em dashes. Use commas instead.
- No hyphens in spoken compound adjectives.
- No ALL CAPS. No superlatives. No editorializing.
- Attribution for strong claims.
- Spell out numbers as spoken words.
- Written to be read aloud by a news anchor. Favor spoken rhythm over written density.

CONTENT FILTER — omit any story involving:
- Litigation or lawsuits between AI companies and government.
- Politically polarizing topics.
- Stories that could divide a mixed corporate audience.

Fetch content from each of the following sources for the week of [START DATE] through [END DATE].
Do not include raw article text in your response. Research and summarize internally, then write the output below.

SOURCES:

- https://jack-clark.net/
- https://syncedreview.com/
- https://www.cnbc.com/artificial-intelligence/
- https://www.technologyreview.com/topic/artificial-intelligence/
- https://www.deeplearning.ai/the-batch/
- https://simonwillison.net/
- https://tldr.tech/ai

---

OUTPUT FORMAT:
Respond with a single valid JSON object. No preamble, no explanation, no markdown fences. Just the JSON.

[EXCLUSION BLOCK]

Schema:

{
  "week_of": "[START DATE] to [END DATE]",
  "stories": [
    {
      [SCHEMA BLOCK]
    }
  ]
}

STORY COUNT:
- Return exactly 6 stories.
- Rank by significance — lead with the most important development.
- Drop a story slot rather than padding with a weak story.
- Total: exactly 6 stories. Do not add extra stories.

BODY LENGTH:
- Each body must be [TEXT MIN] to [TEXT MAX] characters.
- Count carefully. Do not go under [TEXT MIN] or over [TEXT MAX].
- That is roughly [COPY MIN] to [COPY MAX] words of tight broadcast copy.
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

DEDUPLICATION — across all stories:
- Each company, product, or model name may appear in only one story.
- If the same event appears in multiple sources, use the most detailed version and cite the primary source only.
- Do not report on the same event or announcement from two different angles.
- Do not use one story to recap or reference another story in the same output.

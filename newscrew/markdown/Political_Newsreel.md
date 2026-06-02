Fetch content from each of the following sources covering the last [NEWS_WINDOW_HOURS] hours of news.
Do not include raw article text in your response. Research and summarize internally, then write the output below.
For each story, consult all four sources and synthesize the most complete version. Cite the source that provided the most detail 
as source_name and source_url. Additional sources used for corroboration do not need to be cited.

SOURCES:

- https://www.politico.com
- https://www.theguardian.com/us-news
- https://www.vox.com
- https://thehill.com
- https://motherjones.com
- https://newrepublic.com

---

OUTPUT FORMAT:
Respond with a single valid JSON object. No preamble, no explanation, no markdown fences. Just the JSON.

Schema:

{
  "as_of": "[CURRENT DATE AND TIME]",
  "stories": [
    {
      [SCHEMA BLOCK]
    }
  ]
}

STORY COUNT:
- Return exactly 6 stories.
- Rank by significance — lead with the most consequential story.
- Drop a story slot rather than padding with a weak story.

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
- No ALL CAPS. No superlatives.
- Attribution for strong claims.
- Spell out numbers as spoken words.
- Written to be read aloud by a news anchor. Favor spoken rhythm over written density.

RECENCY — strongly prefer stories from the last [NEWS_WINDOW_HOURS] hours.
If a story broke earlier but had significant developments in the window, include it and note the development.
Do not include stories with no activity in the last [NEWS_WINDOW_HOURS] hours.

DEDUPLICATION — across all stories:
- Each person, bill, event, or legal case may appear in only one story.
- If the same event appears in multiple sources, use the most detailed 
  version and cite the primary source only. Do not include a second 
  story covering the same event from a different angle or source.
- Do not report the same event twice.

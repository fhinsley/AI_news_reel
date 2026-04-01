# AI Newsreel — Weekly Research Prompt

## Purpose
This prompt fetches content from the five original newsreel sources and returns
a summary of this week's top stories. No script formatting — just the raw story
content for editorial review.

---

## Prompt to use in Claude

Fetch the current content from each of the following five sources and summarize
the top AI stories from each one. For each source, list the stories you find with
a 2 to 3 sentence summary of each. Do not write a script. Do not add formatting
beyond source headings and story bullet points. Just give me the news.

**Source 1 — The Batch (DeepLearning.AI)**
Fetch: https://www.deeplearning.ai/the-batch/

**Source 2 — Import AI (Jack Clark)**
Fetch: https://jack-clark.net/

**Source 3 — TLDR AI**
Fetch: https://tldr.tech/ai

**Source 4 — CNBC Artificial Intelligence**
Fetch: https://www.cnbc.com/artificial-intelligence/

**Source 5 — MIT Technology Review AI**
Fetch: https://www.technologyreview.com/topic/artificial-intelligence/

---

## After reviewing the output

Once you have the story summaries, decide which stories to include in the
newsreel. Then either:

- Write the script yourself using the format rules in Weekly_Newsreel_Prompt.md
- Or bring the selected stories back to Claude and ask it to write the script

---

## Notes

- This approach fetches targeted URLs rather than running broad web searches
- Much lighter on session usage than the search-based approach
- The five sources were selected after extensive trial and error by the original
  newsreel producer and represent a good cross-section of technical, research,
  business, and impact coverage
- If a source URL has changed or is behind a paywall, note it and skip to the next

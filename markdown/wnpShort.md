Generate this week's AI newsreel script for the week of [March 28, 2026] through [April 3, 2026].

HARD LIMIT: Total script must not exceed 9,500 characters including break tags.
Write 3 stories per section maximum. Stop before reaching the limit.

<!-- BROAD SEARCH APPROACH — kept for reference
     Higher session usage, can trigger rate limits on paid plans.

Search broadly for this week's top AI stories across reputable technology and AI news outlets.
Summarize findings internally. Write the script directly from your research.
-->

<!-- TARGETED FETCH APPROACH — current production method
     Five direct URL fetches. Same story quality, fraction of the session usage. -->
Fetch content from each of the following five sources and write the script
directly from what you find. Do not include raw article text in your response.

- https://www.deeplearning.ai/the-batch/
- https://jack-clark.net/
- https://tldr.tech/ai
- https://www.cnbc.com/artificial-intelligence/
- https://www.technologyreview.com/topic/artificial-intelligence/

Follow these formatting rules exactly:

OPENING:
- First line: Welcome to the AI Newsreel. This is a weekly summary of the news in AI for the week of [DATE RANGE].
- Break tag
- Paragraph beginning with exactly: This week:
- Break tag
- Exactly: Here is what happened.
- Break tag

SECTIONS in this exact order with these exact names:
Core Tech Releases
Directions in AI Architecture
AI For Productivity
World Impact

EACH SECTION:
- Section name on its own line
- Break tag
- Story title on its own line, under 60 characters, no period at end
- Break tag
- Story paragraph(s)
- Break tag after each paragraph

CLOSING:
- Exactly: That is your weekly summary of this week's AI news.
- Break tag
- Exactly: Sources this week: [comma-separated sources]

BREAK TAG FORMAT:
Always blank line before break tag. Never immediately after a period.
Use <break time="2s" /> before section headers.
Use <break time="1s" /> before story titles and between paragraphs.

STYLE:
- AP wire style
- No em dashes, use commas instead
- No hyphens in spoken compound adjectives
- No ALL CAPS
- No superlatives or editorializing
- Attribution for strong claims
- Spell out numbers when spoken
- Target 8,500 to 9,500 characters total
`
CONTENT FILTER — avoid:
- Litigation or lawsuits between AI companies and government
- Politically polarizing topics
- Stories that could divide a mixed corporate audience

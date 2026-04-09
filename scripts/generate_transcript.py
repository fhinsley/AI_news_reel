#!/usr/bin/env python3
"""Generate a formatted PDF transcript from shortstories.json.

Layout:
  - Title: AI Newsreel — week date range
  - Four sections, each with a heading
  - Story title as subheading, body as body text
  - Sources collected at the end

Pipeline position: run after trim_stories.py, independently of TTS/video steps.
Output: <WEEK_FOLDER>/Transcript.pdf
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak
)

import config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

INPUT_FILE  = config.ANTHROPIC_SHORT_JSON_FILE
OUTPUT_FILE = Path(config.WEEK_FOLDER) / "Transcript.pdf"

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def build_styles():
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "NewsreelTitle",
        parent=base["Title"],
        fontSize=24,
        leading=30,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )

    subtitle = ParagraphStyle(
        "NewsreelSubtitle",
        parent=base["Normal"],
        fontSize=11,
        leading=14,
        spaceAfter=20,
        textColor=colors.HexColor("#555555"),
    )

    section = ParagraphStyle(
        "SectionHeading",
        parent=base["Heading1"],
        fontSize=15,
        leading=20,
        spaceBefore=18,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
        borderPad=0,
    )

    story_title = ParagraphStyle(
        "StoryTitle",
        parent=base["Heading2"],
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#2e4057"),
    )

    body = ParagraphStyle(
        "StoryBody",
        parent=base["Normal"],
        fontSize=10,
        leading=15,
        spaceAfter=6,
        textColor=colors.HexColor("#222222"),
    )

    sources_heading = ParagraphStyle(
        "SourcesHeading",
        parent=base["Heading1"],
        fontSize=13,
        leading=18,
        spaceBefore=24,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a2e"),
    )

    source_item = ParagraphStyle(
        "SourceItem",
        parent=base["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=3,
        textColor=colors.HexColor("#444444"),
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "section": section,
        "story_title": story_title,
        "body": body,
        "sources_heading": sources_heading,
        "source_item": source_item,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not Path(INPUT_FILE).exists():
        print(f"ERROR: {INPUT_FILE} not found. Run trim_stories.py first.")
        return 1

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    styles = build_styles()
    story = []

    # --- Title block ---
    week_of = data.get("week_of", "")
    story.append(Paragraph("AI Newsreel", styles["title"]))
    story.append(Paragraph(f"Week of {week_of}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a1a2e"), spaceAfter=16))

    # --- Sections and stories ---
    seen_sources = {}  # name -> url, insertion-ordered

    for section in data.get("sections", []):
        section_name = section.get("section", "")
        story.append(Paragraph(section_name, styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=colors.HexColor("#cccccc"), spaceAfter=4))

        for article in section.get("stories", []):
            title    = article.get("title", "").strip()
            body     = article.get("body",  "").strip()
            src_name = article.get("source_name", "").strip()
            src_url  = article.get("source_url",  "").strip()

            if title:
                story.append(Paragraph(title, styles["story_title"]))
            if body:
                story.append(Paragraph(body, styles["body"]))

            if src_name and src_name not in seen_sources:
                seen_sources[src_name] = src_url

        story.append(Spacer(1, 0.1 * inch))

    # --- Sources ---
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a1a2e"), spaceBefore=12, spaceAfter=8))
    story.append(Paragraph("Sources", styles["sources_heading"]))

    for name, url in seen_sources.items():
        if url:
            line = f'<b>{name}</b> — <a href="{url}" color="#2e4057">{url}</a>'
        else:
            line = f"<b>{name}</b>"
        story.append(Paragraph(line, styles["source_item"]))

    # --- Build PDF ---
    doc = SimpleDocTemplate(
        str(OUTPUT_FILE),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=f"AI Newsreel — {week_of}",
        author="AI Newsreel",
    )
    doc.build(story)

    print(f"Transcript saved to: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

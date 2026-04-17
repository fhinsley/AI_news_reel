#!/usr/bin/env python3
"""Generate a formatted PDF transcript from story.json.

Layout:
  - Title: Two Sides — proposition
  - Week date range and topic summary
  - Each debate turn as a labeled section with speaker, role, and script
  - Proposition and framing difference summary at the end

Pipeline position: run after script_generator.py, independently
of TTS/video steps.
Output: <WEEK_FOLDER>/DebateTranscript<MMDDYY>.pdf
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)

import config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

INPUT_FILE  = config.DEBATE_JSON_FILE
OUTPUT_FILE = Path(config.WEEK_FOLDER) / f"DebateTranscript{config.WEEK_FOLDER_NAME}.pdf"

# ---------------------------------------------------------------------------
# Speaker color map — mirrors the video pipeline's left/right colors
# ---------------------------------------------------------------------------

SPEAKER_COLORS = {
    "left":   colors.HexColor("#2979ff"),   # blue
    "right":  colors.HexColor("#c83232"),   # red
    "anchor": colors.HexColor("#444444"),   # dark grey
}

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def build_styles():
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "DebateTitle",
        parent=base["Title"],
        fontSize=22,
        leading=28,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a2e"),
    )

    subtitle = ParagraphStyle(
        "DebateSubtitle",
        parent=base["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor("#555555"),
    )

    proposition = ParagraphStyle(
        "Proposition",
        parent=base["Normal"],
        fontSize=13,
        leading=18,
        spaceBefore=4,
        spaceAfter=20,
        textColor=colors.HexColor("#1a1a2e"),
        leftIndent=12,
        rightIndent=12,
    )

    speaker_left = ParagraphStyle(
        "SpeakerLeft",
        parent=base["Heading2"],
        fontSize=13,
        leading=18,
        spaceBefore=16,
        spaceAfter=2,
        textColor=SPEAKER_COLORS["left"],
    )

    speaker_right = ParagraphStyle(
        "SpeakerRight",
        parent=base["Heading2"],
        fontSize=13,
        leading=18,
        spaceBefore=16,
        spaceAfter=2,
        textColor=SPEAKER_COLORS["right"],
    )

    speaker_anchor = ParagraphStyle(
        "SpeakerAnchor",
        parent=base["Heading2"],
        fontSize=13,
        leading=18,
        spaceBefore=16,
        spaceAfter=2,
        textColor=SPEAKER_COLORS["anchor"],
    )

    role_label = ParagraphStyle(
        "RoleLabel",
        parent=base["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=6,
        textColor=colors.HexColor("#888888"),
        leftIndent=2,
    )

    body = ParagraphStyle(
        "TurnBody",
        parent=base["Normal"],
        fontSize=10,
        leading=15,
        spaceAfter=6,
        textColor=colors.HexColor("#222222"),
    )

    summary_heading = ParagraphStyle(
        "SummaryHeading",
        parent=base["Heading1"],
        fontSize=12,
        leading=16,
        spaceBefore=24,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )

    summary_body = ParagraphStyle(
        "SummaryBody",
        parent=base["Normal"],
        fontSize=10,
        leading=15,
        spaceAfter=6,
        textColor=colors.HexColor("#333333"),
        leftIndent=12,
        rightIndent=12,
    )

    return {
        "title":          title,
        "subtitle":       subtitle,
        "proposition":    proposition,
        "speaker_left":   speaker_left,
        "speaker_right":  speaker_right,
        "speaker_anchor": speaker_anchor,
        "role_label":     role_label,
        "body":           body,
        "summary_heading": summary_heading,
        "summary_body":   summary_body,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def speaker_style(side: str, styles: dict) -> ParagraphStyle:
    return styles.get(f"speaker_{side}", styles["speaker_anchor"])


def add_turn(story, speaker_name: str, role_label: str, side: str,
             text: str, styles: dict) -> None:
    """Append one debate turn (speaker heading + role label + body text)."""
    story.append(Paragraph(speaker_name, speaker_style(side, styles)))
    story.append(Paragraph(role_label, styles["role_label"]))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=SPEAKER_COLORS.get(side, colors.HexColor("#cccccc")),
        spaceAfter=6,
    ))
    story.append(Paragraph(text.strip(), styles["body"]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found. Run script_generator.py first.")
        return 1

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    debate         = data.get("debate", {})
    proposition    = data.get("proposition", "")
    topic_summary  = data.get("topic_summary", "")
    week_of        = data.get("week_of", "")
    opener_side    = data.get("opener_side",    config.DEBATE_OPENER)
    responder_side = data.get("responder_side", "right" if opener_side == "left" else "left")

    styles = build_styles()
    story  = []

    # --- Title block ---
    story.append(Paragraph("Two Sides", styles["title"]))
    story.append(Paragraph(f"Week of {week_of}", styles["subtitle"]))
    if topic_summary:
        story.append(Paragraph(topic_summary, styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a1a2e"), spaceAfter=10))
    story.append(Paragraph(f"<i>\"{proposition}\"</i>", styles["proposition"]))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#cccccc"), spaceAfter=10))

    # --- Anchor intro ---
    anchor_intro = debate.get("anchor_intro", {}).get("script", "")
    if anchor_intro:
        add_turn(story, "Anchor", "Introduction", "anchor", anchor_intro, styles)

    story.append(Spacer(1, 0.15 * inch))

    # --- Opener argument ---
    opener_arg = debate.get("opener_argument", {})
    opener_label = opener_arg.get("label", f"{opener_side.capitalize()} Perspective")
    if opener_arg.get("script"):
        add_turn(story,
                 opener_label,
                 f"Opening argument — {opener_side.capitalize()} ({opener_side} speaks first)",
                 opener_side,
                 opener_arg["script"],
                 styles)

    story.append(Spacer(1, 0.1 * inch))

    # --- Responder turn (rebuttal + argument) ---
    responder_turn  = debate.get("responder_turn", {})
    responder_label = responder_turn.get("label", f"{responder_side.capitalize()} Perspective")
    rebuttal_text   = responder_turn.get("rebuttal", "")
    argument_text   = responder_turn.get("argument", "")

    if rebuttal_text:
        add_turn(story,
                 responder_label,
                 f"Rebuttal — {responder_side.capitalize()} responds to opener's argument",
                 responder_side,
                 rebuttal_text,
                 styles)
        story.append(Spacer(1, 0.05 * inch))

    if argument_text:
        add_turn(story,
                 responder_label,
                 f"Argument — {responder_side.capitalize()} makes their affirmative case",
                 responder_side,
                 argument_text,
                 styles)

    story.append(Spacer(1, 0.1 * inch))

    # --- Opener closing rebuttal ---
    opener_rebuttal = debate.get("opener_rebuttal", {}).get("script", "")
    if opener_rebuttal:
        add_turn(story,
                 opener_label,
                 f"Closing rebuttal — {opener_side.capitalize()} responds to responder's argument",
                 opener_side,
                 opener_rebuttal,
                 styles)

    story.append(Spacer(1, 0.15 * inch))

    # --- Anchor outro ---
    anchor_outro = debate.get("anchor_outro", {}).get("script", "")
    if anchor_outro:
        add_turn(story, "Anchor", "Closing summary", "anchor", anchor_outro, styles)

    # --- Summary block ---
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a1a2e"),
                             spaceBefore=20, spaceAfter=8))
    story.append(Paragraph("Proposition", styles["summary_heading"]))
    story.append(Paragraph(f"<i>\"{proposition}\"</i>", styles["summary_body"]))

    # Build PDF ---
    doc = SimpleDocTemplate(
        str(OUTPUT_FILE),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=f"Two Sides — {proposition[:80]}",
        author="Two Sides",
    )
    doc.build(story)

    print(f"Transcript saved to: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

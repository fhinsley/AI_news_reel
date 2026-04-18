#!/usr/bin/env python3
"""Generate the weekly Two-Sides debate via the Anthropic API.

Structural mirror of scripts/script_generator.py.

Produces a structured point-counterpoint debate between a left debater
and a right debater, driven by parameters in config.py.

Segment order in output JSON:
  anchor_intro       — neutral anchor frames the proposition
  opener_argument    — first debater makes their affirmative case
  responder_rebuttal — second debater addresses opener's attacks, then argues their own case
  opener_rebuttal    — first debater responds to closer's argument
  anchor_outro       — anchor summarizes and closes

Output: <WEEK_FOLDER>/story.json
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
import anthropic
from elevenlabs import client
import config

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a debate script writer. You write structured point-counterpoint debates
between two ideologically opposed debaters — one arguing from a left-leaning
perspective, one from a right-leaning perspective.

Your writing rules:
- Each debater genuinely believes their position. Neither is a strawman.
- Arguments are specific, grounded in real facts from this week's news, and
  rhetorically forceful. They should sound like a real person who holds this
  view making their best case — not a journalist describing the view.
- No em dashes. No bullet points inside scripts. Numbers spelled out.
- Broadcast-ready prose throughout — natural spoken cadence, not written cadence.
- Return ONLY valid JSON. No preamble, no markdown fences, no text outside the JSON.

CRITICAL SCHEMA RULES — violations will break the downstream pipeline:
- The responder_turn object MUST contain exactly two content keys: "rebuttal" and "argument".
  Do NOT use "rebuttal_argument", "affirmative_argument", "own_argument", "case", or any
  other variant. The key names must be exactly "rebuttal" and "argument".
- Every script field must be a plain string. No nested objects inside script values.
- All other key names must match the schema exactly as shown in the user prompt.
"""

USER_PROMPT_TEMPLATE = """
Today is {today}. This week's date range: {start_date} through {end_date}.

{proposition_override_block}Search the following sources to find coverage of the debate topic:
  Left-leaning:  {left_sources}
  Right-leaning: {right_sources}
{topic_exclusion_block}

The debate has these roles:
  OPENER:    the {opener_side} debater — speaks first, argues IN FAVOR of the proposition
  RESPONDER: the {responder_side} debater — speaks second, argues AGAINST the proposition

Rebuttal strategy instructions for BOTH debaters when responding to the opponent's attacks:
- {full_denial_pct}% of the time: flat denial — the accusation is factually wrong, here is why
- {concede_pivot_pct}% of the time: concede the fact, contest its meaning or significance
- {genuine_concede_pct}% of the time: grant the point entirely and move past it

Word count targets:
- Opener argument:         {opener_min} to {opener_max} words
- Responder rebuttal:      {rebuttal_min} to {rebuttal_max} words  (addresses opener's attacks specifically)
- Responder argument:      {argument_min} to {argument_max} words  (their own affirmative case against the proposition)
- Opener closing rebuttal: {closing_min} to {closing_max} words    (responds to responder's argument)
- Anchor intro:            {anchor_intro_min} to {anchor_intro_max} words
- Anchor outro:            {anchor_outro_min} to {anchor_outro_max} words

Return ONLY a valid JSON object matching this exact schema.
KEY NAMES ARE MANDATORY — do not rename any field, especially "rebuttal" and "argument"
inside responder_turn:

{{
  "week_of": "{start_date} to {end_date}",
  "proposition": "<the debate proposition as a single declarative statement>",
  "topic_summary": "<one neutral sentence describing the underlying news event>",
  "opener_side": "{opener_side}",
  "responder_side": "{responder_side}",
  "debate": {{
    "anchor_intro": {{
      "voice_key": "anchor",
      "script": "<neutral anchor introduces the proposition and both sides — {anchor_intro_min} to {anchor_intro_max} words>"
    }},
    "opener_argument": {{
      "voice_key": "{opener_side}",
      "label": "<{opener_side_cap} Perspective>",
      "script": "<opener makes their affirmative case for the proposition — {opener_min} to {opener_max} words. Should include at least one specific preemptive attack on the opposing view.>"
    }},
    "responder_turn": {{
      "voice_key": "{responder_side}",
      "label": "<{responder_side_cap} Perspective>",
      "rebuttal": "<responder addresses the opener's specific attacks — {rebuttal_min} to {rebuttal_max} words. THIS KEY MUST BE NAMED 'rebuttal' EXACTLY.>",
      "argument": "<responder's own affirmative case against the proposition — {argument_min} to {argument_max} words. THIS KEY MUST BE NAMED 'argument' EXACTLY.>"
    }},
    "opener_rebuttal": {{
      "voice_key": "{opener_side}",
      "script": "<opener responds to the responder's argument using the rebuttal strategy weights above — {closing_min} to {closing_max} words>"
    }},
    "anchor_outro": {{
      "voice_key": "anchor",
      "script": "<anchor summarizes the core proposition each side defended and the sharpest point of disagreement — {anchor_outro_min} to {anchor_outro_max} words>"
    }}
  }}
}}
"""

# ---------------------------------------------------------------------------
# Topic history helpers
# ---------------------------------------------------------------------------

def load_topic_history() -> list[dict]:
    """Load history file and return only entries within the exclusion window."""
    if not config.TOPIC_HISTORY_FILE.exists():
        return []

    with open(config.TOPIC_HISTORY_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)

    cutoff = datetime.now() - timedelta(days=config.TOPIC_EXCLUSION_DAYS)
    recent = [
        e for e in entries
        if datetime.fromisoformat(e["timestamp"]) >= cutoff
    ]
    return recent


def format_history_for_prompt(history: list[dict]) -> str:
    """Format recent topics as a prompt exclusion block.
    Returns empty string if no history — leaves no gap in the prompt.
    """
    if not history:
        return ""

    lines = [
        "\nDo NOT select a topic that is substantially similar to any of the "
        f"following, which have been debated in the past {config.TOPIC_EXCLUSION_DAYS} days. "
        "Topics about the same underlying event, policy, or person count as similar "
        "even if the specific proposition would be different:\n"
    ]
    for e in history:
        lines.append(f"  - {e['topic_summary']}")
    lines.append("")
    return "\n".join(lines)


def append_to_topic_history(data: dict) -> None:
    """Add the new topic to the history file, pruning old entries."""
    topic_summary = data.get("topic_summary", "").strip()
    proposition   = data.get("proposition",   "").strip()
    if not topic_summary:
        return

    # Load full history (not just recent) so we can prune correctly
    if config.TOPIC_HISTORY_FILE.exists():
        with open(config.TOPIC_HISTORY_FILE, "r", encoding="utf-8") as f:
            all_entries = json.load(f)
    else:
        all_entries = []

    all_entries.append({
        "timestamp":     datetime.now().isoformat(),
        "topic_summary": topic_summary,
        "proposition":   proposition,
    })

    # Prune entries beyond the hard cap, keeping the most recent
    all_entries = all_entries[-config.TOPIC_HISTORY_MAX:]

    with open(config.TOPIC_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, indent=2, ensure_ascii=False)

    print(f"Topic history updated ({len(all_entries)} entries): {config.TOPIC_HISTORY_FILE}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_prompt() -> str:
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=7)

    opener_side    = config.DEBATE_OPENER
    responder_side = "right" if opener_side == "left" else "left"

    rs = config.REBUTTAL_STRATEGY
    full_denial_pct     = int(rs["full_denial_weight"]     * 100)
    concede_pivot_pct   = int(rs["concede_pivot_weight"]   * 100)
    genuine_concede_pct = int(rs["genuine_concede_weight"] * 100)

    proposition_override = config.DEBATE_PROPOSITION.strip()

    if proposition_override:
        print(f"Using proposition override: {proposition_override}")
        topic_exclusion_block    = ""
        proposition_override_block = (
            f"The debate proposition has been specified. You MUST use this exact proposition "
            f"and must NOT select a different story:\n\n"
            f'  Proposition: "{proposition_override}"\n\n'
            f"Search the sources below for left-leaning and right-leaning coverage "
            f"of this specific topic to inform the debate arguments.\n\n"
        )
    else:
        history               = load_topic_history()
        topic_exclusion_block = format_history_for_prompt(history)
        proposition_override_block = ""
        if history:
            print(f"Excluding {len(history)} recent topic(s) from selection.")

    return USER_PROMPT_TEMPLATE.format(
        today          = end_date.strftime("%B %d, %Y"),
        start_date     = start_date.strftime("%B %d, %Y"),
        end_date       = end_date.strftime("%B %d, %Y"),
        left_sources   = ", ".join(config.LEFT_SOURCES),
        right_sources  = ", ".join(config.RIGHT_SOURCES),
        opener_side    = opener_side,
        responder_side = responder_side,
        opener_side_cap    = opener_side.capitalize(),
        responder_side_cap = responder_side.capitalize(),
        full_denial_pct     = full_denial_pct,
        concede_pivot_pct   = concede_pivot_pct,
        genuine_concede_pct = genuine_concede_pct,
        opener_min     = config.OPENER_WORDS[0],
        opener_max     = config.OPENER_WORDS[1],
        rebuttal_min   = config.REBUTTAL_WORDS[0],
        rebuttal_max   = config.REBUTTAL_WORDS[1],
        argument_min   = config.ARGUMENT_WORDS[0],
        argument_max   = config.ARGUMENT_WORDS[1],
        closing_min    = config.CLOSING_REBUTTAL_WORDS[0],
        closing_max    = config.CLOSING_REBUTTAL_WORDS[1],
        anchor_intro_min = config.ANCHOR_INTRO_WORDS[0],
        anchor_intro_max = config.ANCHOR_INTRO_WORDS[1],
        anchor_outro_min = config.ANCHOR_OUTRO_WORDS[0],
        anchor_outro_max = config.ANCHOR_OUTRO_WORDS[1],
        topic_exclusion_block = topic_exclusion_block,
        proposition_override_block = proposition_override_block,
    )


def ensure_week_folder() -> None:
    folder = Path(config.WEEK_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Week folder ready: {folder}")


def generate_story(prompt: str) -> dict:
    """Send the prompt to Claude with web search and return parsed JSON.
    Same single-call pattern as script_generator.py.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    print("Sending debate prompt to Claude (web search enabled)...")

    response = client.messages.create(
        model      = config.ANTHROPIC_MODEL,
        max_tokens = config.ANTHROPIC_MAX_TOKENS,
        system     = SYSTEM_PROMPT,
        tools      = [{"type": "web_search_20250305", "name": "web_search"}],
        messages   = [{"role": "user", "content": prompt}],
    )

    print(f"  Stop reason: {response.stop_reason}")

    text_parts = [
        block.text
        for block in response.content
        if block.type == "text"
    ]

    if not text_parts:
        raise RuntimeError(
            "Claude returned no text content. "
            f"Stop reason: {response.stop_reason}. "
            f"Content types: {[b.type for b in response.content]}"
        )

    raw = "\n".join(text_parts).strip()

    # Save raw response for debugging
    Path(config.WEEK_FOLDER).mkdir(parents=True, exist_ok=True)
    (Path(config.WEEK_FOLDER) / "raw_response.txt").write_text(raw, encoding="utf-8")

    start = raw.find("{")
    end   = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(
            f"No JSON object found in Claude response.\n\nRaw:\n{raw[:500]}"
        )
    raw = raw[start : end + 1]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude response was not valid JSON: {exc}\n\nRaw:\n{raw[:500]}"
        )

    return data


def validate_and_report(data: dict) -> None:
    """Print segment word counts and warn on out-of-range lengths.

    Also validates that responder_turn uses the canonical key names and
    raises a RuntimeError immediately — before writing story.json — if
    "rebuttal" or "argument" are missing, so the user gets a clear error
    and can regenerate rather than discovering the problem in tts.py.
    """
    debate = data.get("debate", {})

    print(f"\nWeek of:     {data.get('week_of', 'unknown')}")
    print(f"Proposition: {data.get('proposition', 'no proposition')}")
    print(f"Opener:      {data.get('opener_side', '?')}  |  Responder: {data.get('responder_side', '?')}")
    print()

    # Schema guard: fail loudly before saving if responder_turn keys are wrong
    responder_turn = debate.get("responder_turn", {})
    for required_key in ("rebuttal", "argument"):
        if required_key not in responder_turn:
            actual_keys = list(responder_turn.keys())
            raise RuntimeError(
                f"Claude returned responder_turn without the required key '{required_key}'. "
                f"Actual keys: {actual_keys}. "
                f"story.json NOT saved. Regenerate the script."
            )

    segments = [
        ("anchor_intro",    debate.get("anchor_intro",    {}).get("script", ""),    config.ANCHOR_INTRO_WORDS),
        ("opener_argument", debate.get("opener_argument", {}).get("script", ""),    config.OPENER_WORDS),
        ("rebuttal",        responder_turn.get("rebuttal",  ""),                     config.REBUTTAL_WORDS),
        ("argument",        responder_turn.get("argument",  ""),                     config.ARGUMENT_WORDS),
        ("opener_rebuttal", debate.get("opener_rebuttal", {}).get("script", ""),    config.CLOSING_REBUTTAL_WORDS),
        ("anchor_outro",    debate.get("anchor_outro",    {}).get("script", ""),    config.ANCHOR_OUTRO_WORDS),
    ]

    for label, text, (mn, mx) in segments:
        wc   = len(text.split())
        flag = ""
        if wc < mn:
            flag = f"  ⚠ SHORT ({wc} words, target {mn}-{mx})"
        elif wc > mx:
            flag = f"  ⚠ LONG  ({wc} words, target {mn}-{mx})"
        print(f"  {label:<20} {wc:>4} words{flag}")


def save_story(data: dict) -> None:
    config.DEBATE_JSON_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nDebate story saved to: {config.DEBATE_JSON_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        prompt = load_prompt()
        ensure_week_folder()
        data = generate_story(prompt)
        validate_and_report(data)   # raises RuntimeError if schema is wrong
        save_story(data)
        append_to_topic_history(data)
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

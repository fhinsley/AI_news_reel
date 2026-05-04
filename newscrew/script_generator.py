#!/usr/bin/env python3
"""Generate the weekly newsreel stories via the Anthropic API.

Reads the prompt template from markdown/Weekly_Newsreel_Prompt.md,
interpolates the current date range and schema block, sends the request
to Claude with web search enabled, and writes the resulting JSON to
<EPISODE_DIR>/stories.json.

This is step 0 of the NewsCrew pipeline. The JSON is the source of truth
for all downstream steps (anchor rendering, shot planning, visual fetch,
video build).

The .md prompt template is shared with PROJ1 and must not be modified.
All NewsCrew-specific schema additions (broll_search_term) are injected
here via the [SCHEMA_BLOCK] replacement before the prompt is sent.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from functools import reduce

import anthropic
import config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROMPT_FILE = Path(config.PROJECT_ROOT) / "markdown" / "Weekly_Newsreel_Prompt.md"

# ---------------------------------------------------------------------------
# Schema block — injected into the prompt in place of [SCHEMA_BLOCK].
# This extends the base story schema from the .md file with fields that
# NewsCrew needs for video production without touching the shared template.
# ---------------------------------------------------------------------------

NEWSCREW_SCHEMA_BLOCK = """\
Each story object must include these fields:

  "title":            Story title under 60 characters, no period
  "body":             Story text, [TEXT MIN] to [TEXT MAX] characters
  "source_name":      Publication name
  "source_url":       "https://..."
  "broll_search_term": 3 to 6 words suitable for a stock photo search engine.
                       Concrete and visual — prefer nouns and places over
                       abstract concepts. No brand names, no proper nouns
                       that would not appear in stock imagery.
                       Examples: "data center server racks", "robot arm factory",
                       "satellite dish night sky", "office worker laptop screen"
"""

def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")

    template = PROMPT_FILE.read_text(encoding="utf-8")

    # Inject exclusion block if history exists
    history = load_story_history()
    if history:
        print(f"Excluding {len(history)} recent story/stories from selection.")
        exclusion_block = format_exclusion_block(history)
    else:
        exclusion_block = ""

    replacements = {
        "[START DATE]":      config.START_DATE.strftime("%B %d, %Y"),
        "[END DATE]":        config.END_DATE.strftime("%B %d, %Y"),
        "[TEXT MIN]":        str(config.STORY_TEXT_MIN),
        "[TEXT MAX]":        str(config.STORY_TEXT_MAX),
        "[COPY MIN]":        str(config.STORY_COPY_MIN),
        "[COPY MAX]":        str(config.STORY_COPY_MAX),
        "[EXCLUSION BLOCK]": exclusion_block,
        "[SCHEMA BLOCK]":    NEWSCREW_SCHEMA_BLOCK,
    }

    return reduce(
        lambda text, kv: text.replace(kv[0], kv[1]),
        replacements.items(),
        template,
    )


# ---------------------------------------------------------------------------
# Story history — prevents repeated topics across weekly runs
# ---------------------------------------------------------------------------

def load_story_history() -> list[dict]:
    """Return history entries within the exclusion window."""
    if not config.STORY_HISTORY_FILE.exists():
        return []
    with open(config.STORY_HISTORY_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)
    cutoff = datetime.now() - timedelta(days=config.STORY_EXCLUSION_DAYS)
    return [
        e for e in entries
        if datetime.fromisoformat(e["timestamp"]) >= cutoff
    ]


def format_exclusion_block(history: list[dict]) -> str:
    if not history:
        return ""
    lines = [
        "PREVIOUSLY COVERED — do not repeat any story substantially similar to the following,",
        "which appeared in recent newsreels. A story is substantially similar if it covers the",
        "same product release, model announcement, company action, or event, even from a",
        "different angle or source:\n",
    ]
    for e in history:
        section = f" [{e['section']}]" if e.get("section") else ""
        lines.append(f"  - {e['topic_summary']}{section}")
    lines.append("")
    return "\n".join(lines)


def append_to_story_history(data: dict) -> None:
    """Record each story's title into the history file to prevent repeats."""
    entries = []
    if config.STORY_HISTORY_FILE.exists():
        with open(config.STORY_HISTORY_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)

    for section in data.get("sections", []):
        for story in section.get("stories", []):
            summary = story.get("title", "").strip()
            if summary:
                entries.append({
                    "timestamp":     datetime.now().isoformat(),
                    "topic_summary": summary,
                    "section":       section.get("section", ""),
                })

    entries = entries[-config.STORY_HISTORY_MAX:]
    with open(config.STORY_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Story history updated ({len(entries)} entries): {config.STORY_HISTORY_FILE}")


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def ensure_episode_dir() -> None:
    config.EPISODE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Episode folder ready: {config.EPISODE_DIR}")


def generate_stories(prompt: str) -> dict:
    """Send the prompt to Claude with web search and return parsed JSON."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    print("Sending prompt to Claude (web search enabled) — this may take a minute...")

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.ANTHROPIC_MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text blocks; skip tool-use and tool-result blocks
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

    # Find the first complete top-level JSON object via brace-depth tracking
    start = raw.find("{")
    if start == -1:
        raise RuntimeError(
            f"No JSON object found in Claude response.\n\nRaw response:\n{raw[:500]}"
        )
    depth = 0
    end = None
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise RuntimeError(
            f"Unclosed JSON object in Claude response.\n\nRaw response:\n{raw[:500]}"
        )

    raw = raw[start: end + 1]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude response was not valid JSON: {exc}\n\nRaw response:\n{raw[:500]}"
        )

    return data


# ---------------------------------------------------------------------------
# Validation + output
# ---------------------------------------------------------------------------

def validate_and_report(data: dict) -> None:
    """Print a summary and flag stories outside the character target or
    missing broll_search_term."""
    sections = data.get("sections", [])
    print(f"\nWeek of: {data.get('week_of', 'unknown')}")
    print(f"Sections: {len(sections)}")

    for section in sections:
        name   = section.get("section", "unnamed")
        stories = section.get("stories", [])
        print(f"\n  [{name}] — {len(stories)} stories")
        for i, story in enumerate(stories, 1):
            body       = story.get("body", "")
            char_count = len(body)
            flags      = []

            if char_count < config.STORY_LEN_MIN:
                flags.append(f"SHORT ({char_count} chars)")
            elif char_count > config.STORY_LEN_MAX:
                flags.append(f"LONG ({char_count} chars)")

            if not story.get("broll_search_term"):
                flags.append("MISSING broll_search_term")

            flag_str = f"  ⚠ {', '.join(flags)}" if flags else ""
            print(f"    Story {i}: {story.get('title', 'no title')[:55]}{flag_str}")


def save_stories(data: dict) -> None:
    config.STORIES_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nStories saved to: {config.STORIES_JSON}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        prompt = load_prompt()
        ensure_episode_dir()
        data = generate_stories(prompt)
        validate_and_report(data)
        save_stories(data)
        append_to_story_history(data)
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

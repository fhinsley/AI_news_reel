#!/usr/bin/env python3
"""Generate newsreel stories via the Anthropic API.

Supports two profiles:
  --profile ai         Weekly AI newsreel (default)
  --profile political  Political newsreel — top stories from last NEWS_WINDOW_HOURS

Reads the appropriate prompt template from markdown/, interpolates
config values and schema block, sends to Claude with web search,
and writes the resulting JSON to <EPISODE_DIR>/stories.json.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from functools import reduce

import anthropic
import config

# ---------------------------------------------------------------------------
# Schema blocks
# ---------------------------------------------------------------------------

NEWSCREW_SCHEMA_BLOCK = """\
Each story object must include these fields:

  "title":            Story title under 60 characters, no period
  "sentences":        Array of strings — the story broken into individual sentences.
                      Total length across all sentences must be [TEXT MIN] to [TEXT MAX] characters.
                      Each sentence is a single broadcast-style sentence, complete and self-contained.
                      Do not add break_after, break_question, or break_response_lead — those are
                      editorial fields added manually after generation.
  "source_name":      Publication name
  "source_url":       "https://..."
  "broll_search_term": 3 to 6 words suitable for a stock photo search engine.
                       Concrete and visual — prefer nouns and places over
                       abstract concepts. No brand names, no proper nouns
                       that would not appear in stock imagery.
                       Examples: "data center server racks", "robot arm factory",
                       "satellite dish night sky", "office worker laptop screen"
"""

POLITICAL_SCHEMA_BLOCK = """\
Each story object must include these fields:

  "title":            Story title under 60 characters, no period
  "sentences":        Array of strings — the story broken into individual sentences.
                      Total length across all sentences must be [TEXT MIN] to [TEXT MAX] characters.
                      Each sentence is a single broadcast-style sentence, complete and self-contained.
                      Do not add editorial fields — those are added manually after generation.
  "source_name":      Publication name (e.g. "Politico", "The Guardian")
  "source_url":       "https://..."
  "broll_search_term": 3 to 6 words suitable for a stock photo or video search engine.
                       Concrete and visual. Examples: "capitol building washington dc",
                       "protest crowd city street", "senate hearing chamber",
                       "white house press briefing"
"""


# ---------------------------------------------------------------------------
# Prompt loading — profile-aware
# ---------------------------------------------------------------------------

def load_prompt(profile: str) -> str:
    if profile == "political":
        prompt_file = config.POLITICAL_PROMPT_FILE
        schema_block = POLITICAL_SCHEMA_BLOCK
    else:
        prompt_file = config.AI_PROMPT_FILE
        schema_block = NEWSCREW_SCHEMA_BLOCK

    if not Path(prompt_file).exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    template = Path(prompt_file).read_text(encoding="utf-8")

    replacements = {
        "[TEXT MIN]":           str(config.STORY_TEXT_MIN),
        "[TEXT MAX]":           str(config.STORY_TEXT_MAX),
        "[COPY MIN]":           str(config.STORY_COPY_MIN),
        "[COPY MAX]":           str(config.STORY_COPY_MAX),
        "[SCHEMA BLOCK]":       schema_block,
        "[NEWS_WINDOW_HOURS]":  str(config.NEWS_WINDOW_HOURS),
        "[CURRENT DATE AND TIME]": datetime.now().strftime("%B %d, %Y %H:%M"),
    }

    # AI profile only — inject date range and exclusion block
    if profile == "ai":
        history = load_story_history()
        if history:
            print(f"Excluding {len(history)} recent story/stories from selection.")
            exclusion_block = format_exclusion_block(history)
        else:
            exclusion_block = ""
        replacements.update({
            "[START DATE]":      config.START_DATE.strftime("%B %d, %Y"),
            "[END DATE]":        config.END_DATE.strftime("%B %d, %Y"),
            "[EXCLUSION BLOCK]": exclusion_block,
        })

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


def append_to_story_history(data: dict, profile: str) -> None:
    """Record story titles into history to prevent repeats. Skipped for political profile."""
    if profile == "political":
        return   # political news is time-sensitive — no deduplication across runs

    entries = []
    if config.STORY_HISTORY_FILE.exists():
        with open(config.STORY_HISTORY_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)

    for story in data.get("stories", []):
        summary = story.get("title", "").strip()
        if summary:
            entries.append({
                "timestamp":     datetime.now().isoformat(),
                "topic_summary": summary,
                "section":       "",
            })

    entries = entries[-config.STORY_HISTORY_MAX:]
    with open(config.STORY_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Story history updated ({len(entries)} entries): {config.STORY_HISTORY_FILE}")


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def ensure_episode_dir(profile: str) -> None:

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

def validate_and_report(data: dict, profile: str) -> None:
    """Print a summary and flag issues. Handles both ai (sectioned) and political (flat) schemas."""

    if profile == "political":
        stories = data.get("stories", [])
        print(f"\nAs of: {data.get('as_of', 'unknown')}")
        print(f"Stories: {len(stories)}")
        if len(stories) != 6:
            print(f"  ⚠ WRONG COUNT (got {len(stories)}, expected 6)")
        for i, story in enumerate(stories, 1):
            sentences  = story.get("sentences", [])
            body       = " ".join(sentences)
            char_count = len(body)
            flags      = []
            if not sentences:
                flags.append("MISSING sentences")
            elif char_count < config.STORY_LEN_MIN:
                flags.append(f"SHORT ({char_count} chars)")
            elif char_count > config.STORY_LEN_MAX:
                flags.append(f"LONG ({char_count} chars)")
            if not story.get("broll_search_term"):
                flags.append("MISSING broll_search_term")
            flag_str = f"  ⚠ {', '.join(flags)}" if flags else ""
            print(f"  Story {i}: {story.get('title','no title')[:55]}  [{len(sentences)} sentences]{flag_str}")
        return

    # AI profile — flat schema (sections removed)
    EXPECTED_TOTAL = 6

    stories = data.get("stories", [])
    print(f"\nWeek of: {data.get('week_of', 'unknown')}")
    print(f"Stories: {len(stories)}")
    if len(stories) != EXPECTED_TOTAL:
        print(f"  ⚠ WRONG COUNT (got {len(stories)}, expected {EXPECTED_TOTAL})")

    for i, story in enumerate(stories, 1):
        sentences  = story.get("sentences", [])
        body       = " ".join(sentences)
        char_count = len(body)
        flags      = []
        if not sentences:
            flags.append("MISSING sentences")
        elif char_count < config.STORY_LEN_MIN:
            flags.append(f"SHORT ({char_count} chars)")
        elif char_count > config.STORY_LEN_MAX:
            flags.append(f"LONG ({char_count} chars)")
        if not story.get("broll_search_term"):
            flags.append("MISSING broll_search_term")
        flag_str = f"  ⚠ {', '.join(flags)}" if flags else ""
        print(f"  Story {i}: {story.get('title','no title')[:55]}  [{len(sentences)} sentences]{flag_str}")


def save_stories(data: dict) -> None:
    # Inject default broll fields into every story that doesn't already have them.
    # broll_after=1 — B-roll starts after sentence 1
    # broll_return=3 — anchor returns after sentence 3
    for story in _all_stories(data):
        story.setdefault("broll_after",  1)
        story.setdefault("broll_return", 3)

    config.STORIES_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nStories saved to: {config.STORIES_JSON}")


def _all_stories(data: dict) -> list:
    """Return flat list of all story dicts regardless of schema shape."""
    if "sections" in data:
        return [s for sec in data["sections"] for s in sec.get("stories", [])]
    return data.get("stories", [])


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="NewsCrew script generator")
    parser.add_argument(
        "--profile",
        choices=["ai", "political"],
        default="ai",
        help="Prompt profile to use (default: ai)",
    )
    args = parser.parse_args()

    try:
        print(f"Profile: {args.profile}")
        prompt = load_prompt(args.profile)
        ensure_episode_dir(args.profile)
        data = generate_stories(prompt)
        validate_and_report(data, args.profile)
        save_stories(data)
        append_to_story_history(data, args.profile)
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

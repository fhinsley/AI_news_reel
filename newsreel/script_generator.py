#!/usr/bin/env python3
"""Generate the weekly newsreel stories via the Anthropic API.

Reads the prompt template from markdown/Weekly_Newsreel_Prompt.md,
interpolates the current date range, sends the request to Claude
with web search enabled, and writes the resulting JSON to
<WEEK_FOLDER>/stories.json.

This is step 0 of the pipeline. The JSON is the source of truth
for all downstream steps (TTS assembly, video build, etc.).
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
import anthropic
import config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROMPT_FILE = Path(config.PROJECT_ROOT) / "markdown" / "Weekly_Newsreel_Prompt.md"
OUTPUT_FILE = Path(config.WEEK_FOLDER) / "stories.json"

def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")

    template = PROMPT_FILE.read_text(encoding="utf-8")

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=7)

    prompt = template.replace("[START DATE]", start_date.strftime("%B %d, %Y"))
    prompt = prompt.replace("[END DATE]",   end_date.strftime("%B %d, %Y"))

    # Inject exclusion block if history exists
    history = load_story_history()
    if history:
        print(f"Excluding {len(history)} recent story/stories from selection.")
        exclusion_block = format_exclusion_block(history)
        # Append just before the closing instruction in the prompt.
        # "[EXCLUSION_BLOCK]" is a placeholder you add to the markdown template (see note below).
        prompt = prompt.replace("[EXCLUSION_BLOCK]", exclusion_block)
    else:
        prompt = prompt.replace("[EXCLUSION_BLOCK]", "")

    return prompt


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
        f"which appeared in recent newsreels. A story is substantially similar if it covers the",
        f"same product release, model announcement, company action, or event, even from a",
        f"different angle or source:\n",
    ]
    for e in history:
        section = f" [{e['section']}]" if e.get("section") else ""
        lines.append(f"  - {e['topic_summary']}{section}")
    lines.append("")
    return "\n".join(lines)



def append_to_story_history(data: dict) -> None:
    """Record each story from this week's JSON into the history file."""
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

def ensure_week_folder() -> None:
    """Create the weekly output folder if it does not already exist."""
    folder = Path(config.WEEK_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Week folder ready: {folder}")

def generate_stories(prompt: str) -> dict:
    """Send the prompt to Claude and return parsed JSON stories.

    Web search is enabled so Claude can fetch the news sources listed
    in the prompt template.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    print("Sending prompt to Claude (web search enabled) — this may take a minute...")

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.ANTHROPIC_MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract all text blocks (tool-use blocks are skipped)
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

    # Find the outermost { ... } and parse only that, ignoring anything before or after.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(
            f"No JSON object found in Claude response.\n\nRaw response:\n{raw[:500]}"
        )
    raw = raw[start : end + 1]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude response was not valid JSON: {exc}\n\nRaw response:\n{raw[:500]}"
        )

    return data

def validate_and_report(data: dict) -> None:
    """Print a summary and warn on any stories outside the character target."""
    sections = data.get("sections", [])
    print(f"\nWeek of: {data.get('week_of', 'unknown')}")
    print(f"Sections: {len(sections)}")

    for section in sections:
        name = section.get("section", "unnamed")
        stories = section.get("stories", [])
        print(f"\n  [{name}] — {len(stories)} stories")
        for i, story in enumerate(stories, 1):
            body = story.get("body", "")
            char_count = len(body)
            flag = ""
            if char_count < 660:
                flag = f"  ⚠ SHORT ({char_count} chars)"
            elif char_count > 1100:
                flag = f"  ⚠ LONG ({char_count} chars)"
            print(f"    Story {i}: {story.get('title', 'no title')[:55]}{flag}")

def save_stories(data: dict) -> None:
    """Write the validated JSON to the weekly stories file."""
    config.ANTHROPIC_JSON_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nStories saved to: {config.ANTHROPIC_JSON_FILE}")


def main() -> int:
    try:
        prompt = load_prompt()
        ensure_week_folder()
        data = generate_stories(prompt)
        validate_and_report(data)
        save_stories(data)
        append_to_story_history(data)   # <-- add this line
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1
    

if __name__ == "__main__":
    raise SystemExit(main())

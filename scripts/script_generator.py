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
    """Read the prompt template and interpolate the current date range."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")

    template = PROMPT_FILE.read_text(encoding="utf-8")

    # Mirror the date math already in config.py
    end_date = datetime.today()
    start_date = end_date - timedelta(days=7)

    start_str = start_date.strftime("%B %d, %Y")
    end_str = end_date.strftime("%B %d, %Y")

    prompt = template.replace("[START DATE]", start_str)
    prompt = prompt.replace("[END DATE]", end_str)

    return prompt

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
            if char_count < 600:
                flag = f"  ⚠ SHORT ({char_count} chars)"
            elif char_count > 1000:
                flag = f"  ⚠ LONG ({char_count} chars)"
            print(f"    Story {i}: {story.get('title', 'no title')[:55]}{flag}")

def save_stories(data: dict) -> None:
    """Write the validated JSON to the weekly stories file."""
    config.ANTHROPIC_OUTPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nStories saved to: {config.ANTHROPIC_OUTPUT_FILE}")

def main() -> int:
    try:
        prompt = load_prompt()
        ensure_week_folder()
        data = generate_stories(prompt)
        validate_and_report(data)
        save_stories(data)
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

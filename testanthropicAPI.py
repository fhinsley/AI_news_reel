#!/usr/bin/env python3

from pathlib import Path

import anthropic
import scripts.config  # Local config file for API keys and settings

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_FILE = Path("anthropic_response.txt")

def generate_response(prompt: str) -> str:

    api_key = scripts.config.ANTHROPIC_API_KEY  # raises clearly if missing

    client = anthropic.Anthropic(api_key=api_key)

    print("Sending prompt to Claude (web search enabled) — this may take a minute...")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    # Extract all text blocks from the response (tool-use blocks are skipped)
    script_parts = [
        block.text
        for block in response.content
        if block.type == "text"
    ]

    if not script_parts:
        raise RuntimeError(
            "Claude returned no text content. "
            f"Stop reason: {response.stop_reason}. "
            f"Content types: {[b.type for b in response.content]}"
        )

    return "\n".join(script_parts).strip()

def save_response(response: str) -> None:
    OUTPUT_FILE.write_text(response, encoding="utf-8")
    char_count = len(response)
    print(f"Response saved to: {OUTPUT_FILE}")
    print(f"Character count: {char_count:,}")

def main() -> int:
    try:
        prompt = "explain what RAG is in artificial intelligence applications"
        response = generate_response(prompt)
        save_response(response)
        print("\nScript generation complete.")
        return 0
    except Exception as exc:
        print(f"\nScript generation failed: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

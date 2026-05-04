#!/usr/bin/env python3
"""
NewsCrew pipeline entry point.

Runs all steps in sequence. Any step that exits with a non-zero return code
halts the pipeline immediately for review. No selective execution flags —
comment out individual step() calls below to skip a step manually.

Step order:
    1. script_generator.py   — fetch news, generate stories.json via Claude
    2. anchor_renderer.py    — submit HeyGen jobs, poll, download anchor clips
    3. plan_shots.py         — generate shot_plan.json, backfill clip paths
    4. fetch_visuals.py      — fetch b-roll images for broll segments
    5. build_video.py        — composite final News.mp4

Usage:
    python run_newscrew.py
"""

import subprocess
import sys
import time
from pathlib import Path

# All pipeline scripts live in the same directory as this entry point
PIPELINE_DIR = Path(__file__).parent


def step(label: str, script: str, *args: str) -> None:
    """
    Run a pipeline script as a subprocess and block until it completes.
    Halts the pipeline with a non-zero exit code if the script fails.
    """
    script_path = PIPELINE_DIR / script
    cmd = [sys.executable, str(script_path), *args]

    print()
    print("─" * 70)
    print(f"  STEP: {label}")
    print(f"  CMD:  {' '.join(cmd)}")
    print("─" * 70)

    start = time.monotonic()
    result = subprocess.run(cmd)
    elapsed = time.monotonic() - start

    if result.returncode != 0:
        print()
        print(f"✗ PIPELINE HALTED — '{label}' exited with code {result.returncode}.")
        print(f"  Review output above before re-running.")
        sys.exit(result.returncode)

    print(f"  ✓ Done ({elapsed:.1f}s)")


def main() -> None:
    print()
    print("═" * 70)
    print("  NewsCrew Pipeline")
    print("═" * 70)

    pipeline_start = time.monotonic()

    # ── Steps ─────────────────────────────────────────────────────────────────
    # Comment out any line below to skip that step manually.

    step("Generate stories",        "script_generator.py")
    step("Render anchor clips",     "anchor_renderer.py",  "--run")
    step("Build shot plan",         "plan_shots.py",       "--backfill")
    step("Fetch b-roll visuals",    "fetch_visuals.py")
    step("Composite final video",   "build_video.py")

    # ── Done ──────────────────────────────────────────────────────────────────
    total = time.monotonic() - pipeline_start
    minutes, seconds = divmod(int(total), 60)

    print()
    print("═" * 70)
    print(f"  Pipeline complete — {minutes}m {seconds}s total")
    print("═" * 70)
    print()


if __name__ == "__main__":
    main()

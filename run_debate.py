#!/usr/bin/env python3
"""run_debate.py
One-command runner for the Two-Sides debate pipeline.
Structural mirror of run_newsreel.py.

Run from project root:
  python run_debate.py

Steps:
  1. script_generator.py     → MMDDYY_debate/story.json
  2. generate_transcript.py  → MMDDYY_debate/DebateTranscriptMMDDYY.pdf
  3. tts.py                  → MMDDYY_debate/00–04.mp3 + timestamps
  4. build_video.py          → MMDDYY_debate/Debate.mp4
  5. generate_srt.py         → MMDDYY_debate/Captions.srt
  6. upload_youtube.py       → published YouTube video + captions

Flags:
  --skip-script   reuse existing story.json
  --skip-tts      reuse existing audio files
  --skip-upload   skip YouTube upload (local render only)
"""

import argparse
import subprocess
import sys
import time
import debate.config as debate_config


def run_step(label: str, script_path: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=debate_config.PROJECT_ROOT,
        check=False,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n✗ {label} failed (exit {result.returncode})")
        sys.exit(result.returncode)
    print(f"\n✓ {label} completed in {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Two-Sides debate pipeline")
    parser.add_argument("--skip-script", action="store_true",
                        help="Skip script generation — reuse existing story.json")
    parser.add_argument("--skip-tts",    action="store_true",
                        help="Skip TTS synthesis — reuse existing audio files")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip YouTube upload — local render only")
    args = parser.parse_args()

    script_dir = debate_config.SCRIPT_DIR
    t_start    = time.time()

    if not args.skip_script:
        run_step("Step 1: Script Generation (Claude + web search)",
                 str(script_dir / "script_generator.py"))

    run_step("Step 2: Transcript (PDF)",
             str(script_dir / "generate_transcript.py"))

    if not args.skip_tts:
        run_step("Step 3: TTS Synthesis (ElevenLabs)",
                 str(script_dir / "tts.py"))

    run_step("Step 4: Video Assembly (MoviePy)",
             str(script_dir / "build_video.py"))

    run_step("Step 5: Caption Generation",
             str(script_dir / "generate_srt.py"))

    if not args.skip_upload:
        run_step("Step 6: YouTube Upload",
                 str(script_dir / "upload_youtube.py"))

    total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Pipeline complete in {total:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

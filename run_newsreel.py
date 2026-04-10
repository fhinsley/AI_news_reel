#!/usr/bin/env python3
"""Run the full weekly newsreel pipeline from project root.

This wrapper keeps command usage simple after moving implementation files
into the scripts/ folder.
"""

import subprocess
import sys
import scripts.config as config


def run_step(script_name: str) -> None:
    script_path = config.SCRIPT_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    print(f"\n==> Running {script_name}")
    subprocess.run([sys.executable, str(script_path)], cwd=config.PROJECT_ROOT, check=True)


def main() -> int:
    try:
        run_step("script_generator.py")
        run_step("trim_stories.py")
        run_step("newsreel_tts.py")
        run_step("build_video.py")
        run_step("generate_srt.py")
        run_step("generate_transcript.py")
        run_step("upload_youtube.py")
    except subprocess.CalledProcessError as exc:
        print(f"\nPipeline failed with exit code {exc.returncode}")
        return exc.returncode
    except Exception as exc:  # Keep message clear for quick troubleshooting
        print(f"\nPipeline failed: {exc}")
        return 1

    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

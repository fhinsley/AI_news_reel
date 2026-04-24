#!/usr/bin/env python3
"""stretch_audio.py
Time-stretch the TTS audio clips to speed up delivery without changing pitch.

Uses librosa's phase vocoder (time_stretch) which preserves pitch quality
— no chipmunk effect. Overwrites the .mp3 files in the week folder so
build_video.py picks up the faster audio with no changes.

Install dependencies if needed:
  pip install librosa soundfile

Pipeline position: run after newsreel_tts.py, before build_video.py.

Speed factors are configured in config.py via AUDIO_SPEED_FACTORS.
A factor of 1.2 means 20% faster. 1.0 means no change.
Reasonable range: 1.0 to 1.3. Above 1.3 quality degrades noticeably.
"""

import shutil
from pathlib import Path

import librosa
import soundfile as sf
import numpy as np

import config

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def stretch_clip(mp3_path: Path, factor: float) -> None:
    """Time-stretch a single mp3 file in place.

    Reads mp3 → stretches → writes back as mp3 via soundfile + ffmpeg fallback.
    Keeps a .orig backup on first run so you can restore if needed.
    """
    if factor == 1.0:
        print(f"  {mp3_path.name}: factor=1.0 — skipping")
        return

    # Keep original backup (only on first stretch — don't overwrite the backup)
    backup_path = mp3_path.with_suffix(".orig.mp3")
    if not backup_path.exists():
        shutil.copy2(mp3_path, backup_path)

    # Load audio — librosa loads as float32 mono or stereo
    y, sr = librosa.load(str(mp3_path), sr=None, mono=False)

    # Handle stereo: stretch each channel independently
    if y.ndim == 2:
        stretched = np.stack([
            librosa.effects.time_stretch(y[ch], rate=factor)
            for ch in range(y.shape[0])
        ])
    else:
        stretched = librosa.effects.time_stretch(y, rate=factor)

    # Write back — soundfile writes wav, then we convert to mp3 via ffmpeg
    tmp_wav = mp3_path.with_suffix(".tmp.wav")
    if y.ndim == 2:
        sf.write(str(tmp_wav), stretched.T, sr)
    else:
        sf.write(str(tmp_wav), stretched, sr)

    # Convert wav → mp3 using ffmpeg (already required by moviepy)
    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(tmp_wav), "-codec:a", "libmp3lame",
         "-q:a", "2", str(mp3_path)],
        capture_output=True,
    )
    tmp_wav.unlink()

    if result.returncode != 0:
        print(f"  ERROR: ffmpeg failed for {mp3_path.name}")
        print(result.stderr.decode())
        return

    orig_dur   = librosa.get_duration(path=str(backup_path))
    new_dur    = librosa.get_duration(path=str(mp3_path))
    print(f"  {mp3_path.name}: {orig_dur:.1f}s → {new_dur:.1f}s (factor={factor})")


def main() -> int:
    week = Path(config.WEEK_FOLDER)
    factors = config.AUDIO_SPEED_FACTORS

    print(f"\nTime-stretching audio clips in: {week}\n")

    any_processed = False
    for stem, factor in factors.items():
        mp3_path = week / f"{stem}.mp3"
        if not mp3_path.exists():
            print(f"  SKIP: {mp3_path.name} not found")
            continue
        stretch_clip(mp3_path, factor)
        any_processed = True

    if not any_processed:
        print("No clips found — run newsreel_tts.py first.")
        return 1

    print("\nDone. Originals saved as .orig.mp3 if you need to restore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

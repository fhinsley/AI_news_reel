"""
Submits anchor video render jobs to HeyGen for all segments in stories.json,
tracks job IDs in anchor_jobs.json, and downloads completed clips.

Usage:
    python anchor_renderer.py --submit     # submit all jobs
    python anchor_renderer.py --poll       # check status + download ready clips
    python anchor_renderer.py --run        # submit then poll until all done
"""

import argparse
import json
import time
import requests
from pathlib import Path

from config import (
    HEYGEN_API_BASE, HEYGEN_API_KEY,
    HEYGEN_AVATAR_DIMENSION, HEYGEN_BACKGROUND_COLOR,
    STORIES_JSON, ANCHOR_JOBS_JSON, ANCHOR_CLIPS_DIR,
    ANCHORS, ANCHOR_LEAD,
)

HEADERS = {
    "X-Api-Key": HEYGEN_API_KEY,
    "Content-Type": "application/json",
}

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS     = 60   # 30 min ceiling


# ── Anchor assignment ──────────────────────────────────────────────────────────

def assign_anchors(stories: dict) -> list[dict]:
    """
    Flatten all segments across sections into an ordered list,
    assign anchors alternating A/B, with intro/outro forced to ANCHOR_LEAD.
    Returns a list of segment dicts ready for job submission.
    """
    anchor_lookup = {a["id"]: a for a in ANCHORS}

    # Seat anchors only — sorted a then b — drive story alternation.
    # List order in ANCHORS does not matter; seat field does.
    seat_anchors = sorted(
        [a for a in ANCHORS if a.get("seat") in ("a", "b")],
        key=lambda a: a["seat"],
    )
    if len(seat_anchors) != 2:
        raise RuntimeError(
            f"Expected exactly 2 anchors with seat 'a' and 'b', "
            f"found: {[a['id'] for a in seat_anchors]}"
        )

    segments = []
    story_counter = 0

    for section_data in stories["sections"]:
        section_name = section_data["section"]

        # Section intro line (if present)
        if intro := section_data.get("intro"):
            anchor = anchor_lookup[ANCHOR_LEAD]
            segments.append({
                "segment_id":   f"{section_name}__intro",
                "section":      section_name,
                "type":         "intro",
                "script":       intro,
                "anchor_id":    anchor["id"],
                "avatar_id":    anchor["avatar_id"],
                "voice_id":     anchor["voice_id"],
            })

        for story in section_data.get("stories", []):
            anchor = seat_anchors[story_counter % 2]
            segments.append({
                "segment_id":   f"{section_name}__{story['title'][:40]}",
                "section":      section_name,
                "type":         "story",
                "script":       story["body"],
                "anchor_id":    anchor["id"],
                "avatar_id":    anchor["avatar_id"],
                "voice_id":     anchor["voice_id"],
                "source_name":  story.get("source_name"),
                "source_url":   story.get("source_url"),
            })
            story_counter += 1

    return segments


# ── Job submission ─────────────────────────────────────────────────────────────

def build_heygen_payload(segment: dict) -> dict:
    """Build the HeyGen v2 video generation request body for one segment."""
    return {
        "video_inputs": [
            {
                "character": {
                    "type":         "avatar",
                    "avatar_id":    segment["avatar_id"],
                    "avatar_style": "normal",
                },
                "voice": {
                    "type":       "text",
                    "voice_id":   segment["voice_id"],
                    "input_text": segment["script"],
                },
                "background": {
                    "type":  "color",
                    "value": HEYGEN_BACKGROUND_COLOR,
                },
            }
        ],
        "dimension": HEYGEN_AVATAR_DIMENSION,
        "test": False,
    }


def submit_all(segments: list[dict]) -> dict:
    """
    Submit all segments to HeyGen. Returns a jobs dict keyed by segment_id.
    Skips segments that already have a job_id in anchor_jobs.json.
    """
    existing_jobs = load_jobs()

    for seg in segments:
        sid = seg["segment_id"]
        if sid in existing_jobs:
            print(f"  skip (already submitted): {sid}")
            continue

        payload = build_heygen_payload(seg)
        resp = requests.post(
            f"{HEYGEN_API_BASE}/v2/video/generate",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        job_id = data["data"]["video_id"]
        existing_jobs[sid] = {
            "job_id":     job_id,
            "status":     "pending",
            "segment":    seg,
            "clip_path":  None,
        }
        print(f"  submitted: {sid} → {job_id}")
        save_jobs(existing_jobs)   # save after each submit — safe to interrupt

    return existing_jobs


# ── Polling + download ─────────────────────────────────────────────────────────

def poll_and_download(jobs: dict) -> dict:
    """Poll HeyGen for status on all pending jobs. Download completed clips."""
    ANCHOR_CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    pending = [sid for sid, j in jobs.items() if j["status"] != "completed"]
    print(f"  {len(pending)} segments pending...")

    for attempt in range(MAX_POLL_ATTEMPTS):
        if not pending:
            break

        time.sleep(POLL_INTERVAL_SECONDS)
        still_pending = []

        for sid in pending:
            job = jobs[sid]
            try:
                resp = requests.get(
                    f"{HEYGEN_API_BASE}/v1/video_status.get",
                    headers=HEADERS,
                    params={"video_id": job["job_id"]},
                    timeout=60,
                )
            except requests.exceptions.Timeout:
                print(f"  attempt {attempt + 1}: poll timed out for {sid}, will retry next cycle.")
                still_pending.append(sid)
                continue
            if resp.status_code in (502, 503, 504):
                print(f"  attempt {attempt + 1}: transient {resp.status_code}, retrying...")
                still_pending.append(sid)
                continue
            resp.raise_for_status()
            status_data = resp.json()["data"]
            heygen_status = status_data.get("status")

            if heygen_status == "completed":
                video_url = status_data["video_url"]
                clip_path = ANCHOR_CLIPS_DIR / f"{sid}.mp4"
                _download_clip(video_url, clip_path)
                jobs[sid]["status"]    = "completed"
                jobs[sid]["clip_path"] = str(clip_path)
                print(f"  downloaded: {sid}")
                save_jobs(jobs)

            elif heygen_status == "failed":
                jobs[sid]["status"] = "failed"
                print(f"  FAILED: {sid}")
                save_jobs(jobs)

            else:
                still_pending.append(sid)

        pending = still_pending
        print(f"  attempt {attempt + 1}: {len(pending)} still pending")

    if pending:
        print(f"  WARNING: {len(pending)} segments still pending after max attempts.")

    return jobs


def _download_clip(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


# ── Jobs file I/O ──────────────────────────────────────────────────────────────

def load_jobs() -> dict:
    if ANCHOR_JOBS_JSON.exists():
        return json.loads(ANCHOR_JOBS_JSON.read_text())
    return {}

def save_jobs(jobs: dict) -> None:
    ANCHOR_JOBS_JSON.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR_JOBS_JSON.write_text(json.dumps(jobs, indent=2))


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--poll",   action="store_true")
    parser.add_argument("--run",    action="store_true")
    args = parser.parse_args()

    stories = json.loads(STORIES_JSON.read_text())
    segments = assign_anchors(stories)
    print(f"Total segments: {len(segments)}")

    if args.submit or args.run:
        jobs = submit_all(segments)

    if args.poll or args.run:
        jobs = load_jobs()
        jobs = poll_and_download(jobs)

    completed = sum(1 for j in load_jobs().values() if j["status"] == "completed")
    failed    = sum(1 for j in load_jobs().values() if j["status"] == "failed")
    print(f"\nDone. {completed} completed, {failed} failed.")

if __name__ == "__main__":
    main()
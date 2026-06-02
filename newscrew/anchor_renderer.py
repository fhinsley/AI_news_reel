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

def _safe_sid(segment_id: str) -> str:
    """Sanitize a segment ID for use as a filename — replace path-unsafe characters."""
    return segment_id.replace("/", "-").replace("\\", "-").replace(":", "-")


HEADERS = {
    "X-Api-Key": HEYGEN_API_KEY,
    "Content-Type": "application/json",
}

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS     = 60   # 30 min ceiling


# ── Schema normalization ───────────────────────────────────────────────────────

def normalize_stories(data: dict) -> list[dict]:
    """
    Return a flat list of story dicts regardless of schema shape.

    Sectioned schema (AI profile):
        data["sections"] = [{"section": "...", "stories": [...], "bumper": "..."}, ...]

    Flat schema (political profile):
        data["stories"] = [{...}, ...]

    For the flat schema, stories get section="", bumper="" so downstream
    code that reads those fields gets safe empty defaults.
    """
    if "sections" in data:
        flat = []
        for sec in data["sections"]:
            for story in sec.get("stories", []):
                story = dict(story)
                story.setdefault("_section", sec.get("section", ""))
                story.setdefault("_bumper",  sec.get("bumper",  ""))
                flat.append(story)
        return flat
    else:
        for story in data.get("stories", []):
            story.setdefault("_section", "")
            story.setdefault("_bumper",  "")
        return data.get("stories", [])


def iter_sections(data: dict):
    """
    Yield (section_name, bumper_text, stories_list) for each logical section.
    For flat schema yields a single unnamed section with all stories.
    """
    if "sections" in data:
        for sec in data["sections"]:
            yield sec.get("section", ""), sec.get("bumper", ""), sec.get("stories", [])
    else:
        yield "", "", data.get("stories", [])


# ── Anchor assignment ──────────────────────────────────────────────────────────

def assign_anchors(stories: dict) -> list[dict]:
    """
    Flatten all segments into an ordered list for HeyGen submission.

    Segment types emitted (in order):
      - episode intro   (top-level stories["intro"] if present)
      - per section:    bumper (section["bumper"] if present)
                        stories (alternating A/B)
      - episode outro   (top-level stories["outro"] if present)

    Works with both sectioned (AI) and flat (political) schemas.
    Only segments with non-empty script text are submitted.
    """
    anchor_lookup = {a["id"]: a for a in ANCHORS}

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
    lead_anchor = anchor_lookup.get(ANCHOR_LEAD, seat_anchors[0])

    # ── Episode intro ──────────────────────────────────────────────────────────
    if intro_text := stories.get("intro", "").strip():
        segments.append({
            "segment_id": "__intro__",
            "type":       "intro",
            "script":     intro_text,
            "anchor_id":  lead_anchor["id"],
            "avatar_id":  lead_anchor["avatar_id"],
            "voice_id":   lead_anchor["voice_id"],
        })

    for section_name, bumper_text, story_list in iter_sections(stories):

        # ── Section bumper ─────────────────────────────────────────────────────
        if bumper_text.strip():
            bumper_sid = f"{section_name}__bumper" if section_name else "__bumper__"
            segments.append({
                "segment_id": bumper_sid,
                "section":    section_name,
                "type":       "bumper",
                "script":     bumper_text.strip(),
                "anchor_id":  lead_anchor["id"],
                "avatar_id":  lead_anchor["avatar_id"],
                "voice_id":   lead_anchor["voice_id"],
            })

        # ── Stories ────────────────────────────────────────────────────────────
        for story in story_list:
            story_anchor    = seat_anchors[story_counter % 2]
            other_anchor    = seat_anchors[(story_counter + 1) % 2]

            # toss_to overrides which anchor delivers pre/post lines
            toss_id = story.get("toss_to", "").strip()
            if toss_id:
                toss_anchor = anchor_lookup.get(toss_id, other_anchor)
            else:
                toss_anchor = other_anchor

            # ── Derive scripts from sentences ──────────────────────────────
            sentences = story.get("sentences", [])
            if not sentences:
                print(f"  WARNING: story '{story.get('title','?')[:40]}' has no sentences — skipping")
                story_counter += 1
                continue

            break_after = story.get("break_after")
            has_break   = (
                break_after is not None
                and story.get("break_question", "").strip()
                and story.get("break_response_lead", "").strip()
            )

            broll_after  = story.get("broll_after")
            broll_return = story.get("broll_return")
            has_broll    = broll_after is not None

            if has_break:
                idx         = int(break_after)
                part_a      = " ".join(sentences[:idx])
                part_b      = f"{story.get('break_response_lead','').strip()} {' '.join(sentences[idx:])}.strip()"
                question    = story.get("break_question", "").strip()
            elif has_broll:
                b_start     = int(broll_after)
                b_end       = int(broll_return) if broll_return is not None else len(sentences)
                part_a      = " ".join(sentences[:b_start])
                broll_voice = " ".join(sentences[b_start:b_end])
                part_b      = " ".join(sentences[b_end:]) if b_end < len(sentences) else None
            else:
                part_a = " ".join(sentences)

            # ── pre_story ──────────────────────────────────────────────────
            if pre_text := story.get("pre_story", "").strip():
                pre_id = f"{section_name}__{story['title'][:40]}__pre"
                segments.append({
                    "segment_id": pre_id,
                    "section":    section_name,
                    "type":       "pre_story",
                    "script":     pre_text,
                    "anchor_id":  toss_anchor["id"],
                    "avatar_id":  toss_anchor["avatar_id"],
                    "voice_id":   toss_anchor["voice_id"],
                })

            # ── story body part A ──────────────────────────────────────────
            segments.append({
                "segment_id":  f"{section_name}__{story['title'][:40]}",
                "section":     section_name,
                "type":        "story",
                "script":      part_a,
                "anchor_id":   story_anchor["id"],
                "avatar_id":   story_anchor["avatar_id"],
                "voice_id":    story_anchor["voice_id"],
                "source_name": story.get("source_name"),
                "source_url":  story.get("source_url"),
            })

            # ── broll voice clip ───────────────────────────────────────────
            if has_broll and broll_voice.strip():
                segments.append({
                    "segment_id": f"{section_name}__{story['title'][:40]}__broll_voice",
                    "section":    section_name,
                    "type":       "broll_voice",
                    "script":     broll_voice,
                    "anchor_id":  story_anchor["id"],
                    "avatar_id":  story_anchor["avatar_id"],
                    "voice_id":   story_anchor["voice_id"],
                })
                if part_b and part_b.strip():
                    segments.append({
                        "segment_id":  f"{section_name}__{story['title'][:40]}__broll_return",
                        "section":     section_name,
                        "type":        "broll_return",
                        "script":      part_b,
                        "anchor_id":   story_anchor["id"],
                        "avatar_id":   story_anchor["avatar_id"],
                        "voice_id":    story_anchor["voice_id"],
                        "source_name": story.get("source_name"),
                        "source_url":  story.get("source_url"),
                    })

            # ── mid-story anchor break ─────────────────────────────────────
            if has_break:
                part_b_lead = story.get("break_response_lead", "").strip()
                part_b_body = " ".join(sentences[int(break_after):])
                part_b_full = f"{part_b_lead} {part_b_body}".strip()
                question_text = story.get("break_question", "").strip()
                segments.append({
                    "segment_id": f"{section_name}__{story['title'][:40]}__break_q",
                    "section":    section_name,
                    "type":       "break_question",
                    "script":     question_text,
                    "anchor_id":  toss_anchor["id"],
                    "avatar_id":  toss_anchor["avatar_id"],
                    "voice_id":   toss_anchor["voice_id"],
                })
                segments.append({
                    "segment_id":  f"{section_name}__{story['title'][:40]}__break_r",
                    "section":     section_name,
                    "type":        "break_response",
                    "script":      part_b_full,
                    "anchor_id":   story_anchor["id"],
                    "avatar_id":   story_anchor["avatar_id"],
                    "voice_id":    story_anchor["voice_id"],
                    "source_name": story.get("source_name"),
                    "source_url":  story.get("source_url"),
                })

            # ── post_story ─────────────────────────────────────────────────
            if post_text := story.get("post_story", "").strip():
                post_id = f"{section_name}__{story['title'][:40]}__post"
                segments.append({
                    "segment_id": post_id,
                    "section":    section_name,
                    "type":       "post_story",
                    "script":     post_text,
                    "anchor_id":  toss_anchor["id"],
                    "avatar_id":  toss_anchor["avatar_id"],
                    "voice_id":   toss_anchor["voice_id"],
                })

            story_counter += 1

    # ── Episode outro ──────────────────────────────────────────────────────────
    if outro_text := stories.get("outro", "").strip():
        segments.append({
            "segment_id": "__outro__",
            "type":       "outro",
            "script":     outro_text,
            "anchor_id":  lead_anchor["id"],
            "avatar_id":  lead_anchor["avatar_id"],
            "voice_id":   lead_anchor["voice_id"],
        })

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
            "clip_path":  str(ANCHOR_CLIPS_DIR / f"{_safe_sid(sid)}.mp4"),
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
                safe_sid  = _safe_sid(sid)
                clip_path = ANCHOR_CLIPS_DIR / f"{safe_sid}.mp4"
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
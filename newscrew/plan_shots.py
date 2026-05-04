"""
Generates shot_plan.json for the current episode by reading stories.json
and back-filling anchor clip paths from anchor_jobs.json (if available).

Usage:
    python plan_shots.py              # generate / regenerate shot_plan.json
    python plan_shots.json --backfill # only update anchor_clip paths from
                                      # anchor_jobs.json without rebuilding

Shot mode rules:
    - Section intros  → "wide"
    - Story segments  → "solo_a" (Annie) | "solo_b" (Vesperi)
    - "broll"         → manual editorial override only; never auto-assigned

Anchor assignment mirrors anchor_renderer.py:
    - Section intros are always forced to ANCHOR_LEAD
    - Stories alternate A/B globally across all sections via a counter

stories.json schema expected:
    {
        "week_of": "...",
        "sections": [
            {
                "section": "Core Tech Releases",
                "stories": [
                    {
                        "title": "...",
                        "body": "...",
                        "source_name": "...",
                        "source_url": "..."
                    }
                ]
            }
        ]
    }
"""

import argparse
import json
from pathlib import Path

from config import (
    STORIES_JSON,
    ANCHOR_JOBS_JSON,
    SHOT_PLAN_JSON,
    ANCHORS,
    ANCHOR_LEAD,
    EPISODE_DIR,
)

# Map anchor id → solo shot mode, derived from seat field.
# List order in ANCHORS does not matter.
SOLO_SHOT = {a["id"]: f"solo_{a['seat']}" for a in ANCHORS if a.get("seat")}

# Seat anchors sorted a then b — used for story alternation.
SEAT_ANCHORS = sorted(
    [a for a in ANCHORS if a.get("seat") in ("a", "b")],
    key=lambda a: a["seat"],
)
if len(SEAT_ANCHORS) != 2:
    raise RuntimeError(
        f"Expected exactly 2 anchors with seat 'a' and 'b', "
        f"found: {[a['id'] for a in SEAT_ANCHORS]}"
    )


def load_json(path: Path) -> dict | list | None:
    if path.exists():
        return json.loads(path.read_text())
    return None


def build_segments(stories: dict, jobs: dict | None) -> list[dict]:
    """
    Walk stories.json sections (list format) and emit one segment per
    section intro and one segment per story, with shot mode and anchor
    assignment applied.  anchor_clip is back-filled from anchor_jobs.json
    when available.
    """
    anchor_lookup = {a["id"]: a for a in ANCHORS}
    segments      = []
    story_counter = 0

    for section_data in stories["sections"]:
        section_name = section_data["section"]

        # ── Section intro segment ──────────────────────────────────────────
        intro_id = f"{section_name}__intro"
        segments.append(
            _make_segment(
                segment_id          = intro_id,
                shot_mode           = "wide",
                anchor_id           = ANCHOR_LEAD,
                lower_third_headline= section_name,
                lower_third_source  = None,
                transition_in       = "cut" if not segments else "crossfade",
                transition_out      = "crossfade",
                anchor_clip         = _clip_path(intro_id, jobs),
                comment             = f"Section opener — wide shot, {ANCHOR_LEAD} leads",
            )
        )

        # ── Story segments ─────────────────────────────────────────────────
        for story in section_data.get("stories", []):
            anchor    = SEAT_ANCHORS[story_counter % 2]
            anchor_id = anchor["id"]
            shot_mode = SOLO_SHOT.get(anchor_id, "solo_a")

            # Segment ID matches anchor_renderer.py's convention
            headline  = story.get("title", story.get("headline", "untitled"))
            seg_id    = f"{section_name}__{headline[:40]}"

            segments.append(
                _make_segment(
                    segment_id          = seg_id,
                    shot_mode           = shot_mode,
                    anchor_id           = anchor_id,
                    lower_third_headline= headline,
                    lower_third_source  = story.get("source_name"),
                    transition_in       = "crossfade",
                    transition_out      = "cut",
                    anchor_clip         = _clip_path(seg_id, jobs),
                    comment             = f"{anchor_id} reads story {story_counter + 1}",
                )
            )
            story_counter += 1

    return segments


def _make_segment(
    *,
    segment_id: str,
    shot_mode: str,
    anchor_id: str,
    lower_third_headline: str,
    lower_third_source: str | None,
    transition_in: str,
    transition_out: str,
    anchor_clip: str | None,
    comment: str,
) -> dict:
    return {
        "_comment":             comment,
        "segment_id":           segment_id,
        "shot_mode":            shot_mode,
        "anchor_id":            anchor_id,
        "anchor_clip":          anchor_clip,
        "broll_clip":           None,
        "lower_third_headline": lower_third_headline,
        "lower_third_source":   lower_third_source,
        "transition_in":        transition_in,
        "transition_out":       transition_out,
    }


def _clip_path(segment_id: str, jobs: dict | None) -> str | None:
    """Return clip path from anchor_jobs.json if the job completed, else None."""
    if not jobs:
        return None
    job = jobs.get(segment_id)
    if job and job.get("status") == "completed":
        return job.get("clip_path")
    return None


def backfill_clips(segments: list[dict], jobs: dict) -> int:
    """
    Update anchor_clip in-place for any segment whose job is now completed.
    Returns count of newly filled paths.
    """
    filled = 0
    for seg in segments:
        if seg["anchor_clip"] is None:
            path = _clip_path(seg["segment_id"], jobs)
            if path:
                seg["anchor_clip"] = path
                filled += 1
    return filled


def write_shot_plan(episode_id: str, segments: list[dict]) -> None:
    plan = {"episode": episode_id, "segments": segments}
    SHOT_PLAN_JSON.parent.mkdir(parents=True, exist_ok=True)
    SHOT_PLAN_JSON.write_text(json.dumps(plan, indent=2))
    print(f"Wrote {len(segments)} segments → {SHOT_PLAN_JSON}")


def main():
    parser = argparse.ArgumentParser(description="Generate shot_plan.json")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Only update anchor_clip paths from anchor_jobs.json; do not rebuild.",
    )
    args = parser.parse_args()

    stories = load_json(STORIES_JSON)
    if not stories:
        raise FileNotFoundError(f"stories.json not found at {STORIES_JSON}")

    jobs = load_json(ANCHOR_JOBS_JSON)  # None if not yet run — that's fine

    episode_id = EPISODE_DIR.name

    if args.backfill:
        # Load existing plan and only patch anchor_clip fields
        existing = load_json(SHOT_PLAN_JSON)
        if not existing:
            raise FileNotFoundError(
                f"No existing shot_plan.json at {SHOT_PLAN_JSON}. "
                "Run without --backfill to generate it first."
            )
        if not jobs:
            print("No anchor_jobs.json found — nothing to backfill.")
            return

        filled = backfill_clips(existing["segments"], jobs)
        print(f"Backfilled {filled} anchor clip path(s).")
        write_shot_plan(existing["episode"], existing["segments"])

    else:
        segments = build_segments(stories, jobs)
        write_shot_plan(episode_id, segments)

        # Report any segments still missing a clip
        missing = [s["segment_id"] for s in segments if s["anchor_clip"] is None]
        if missing:
            print(f"\n{len(missing)} segment(s) have no anchor clip yet "
                  f"(run anchor_renderer.py --run, then plan_shots.py --backfill):")
            for sid in missing:
                print(f"  {sid}")
        else:
            print("All anchor clips present.")


if __name__ == "__main__":
    main()

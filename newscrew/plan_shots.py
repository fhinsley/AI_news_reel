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


def _iter_sections(stories: dict):
    """Yield (section_name, bumper_text, story_list) for sectioned or flat schemas."""
    if "sections" in stories:
        for sec in stories["sections"]:
            yield sec.get("section", ""), sec.get("bumper", ""), sec.get("stories", [])
    else:
        yield "", "", stories.get("stories", [])


def build_segments(stories: dict, jobs: dict | None) -> list[dict]:
    """
    Walk stories.json and emit segments in broadcast order:
      - episode intro   (if stories["intro"] is present and non-empty)
      - per section:    bumper (if section["bumper"] is present and non-empty)
                        wide section opener (always — rest images, no clip needed)
                        stories (alternating A/B)
      - episode outro   (if stories["outro"] is present and non-empty)
    """
    segments      = []
    story_counter = 0

    # ── Episode intro ──────────────────────────────────────────────────────────
    if stories.get("intro", "").strip():
        intro_id = "__intro__"
        segments.append(_make_segment(
            segment_id           = intro_id,
            shot_mode            = "bumper",
            anchor_id            = ANCHOR_LEAD,
            lower_third_headline = None,
            lower_third_source   = None,
            transition_in        = "cut",
            transition_out       = "cut",
            anchor_clip          = _clip_path(intro_id, jobs),
            comment              = "Episode intro — wall default + voice",
        ))

    for section_name, bumper_text, story_list in _iter_sections(stories):

        # ── Section bumper ─────────────────────────────────────────────────────
        if bumper_text.strip():
            bumper_id = f"{section_name}__bumper" if section_name else "__bumper__"
            segments.append(_make_segment(
                segment_id           = bumper_id,
                shot_mode            = "bumper",
                anchor_id            = ANCHOR_LEAD,
                lower_third_headline = section_name or None,
                lower_third_source   = None,
                transition_in        = "cut",
                transition_out       = "cut",
                anchor_clip          = _clip_path(bumper_id, jobs),
                comment              = f"Section bumper — {section_name or 'intro'}",
            ))

        # ── Story segments ─────────────────────────────────────────────────────
        for story in story_list:
            story_anchor = SEAT_ANCHORS[story_counter % 2]
            other_anchor = SEAT_ANCHORS[(story_counter + 1) % 2]

            # toss_to overrides who delivers pre/post lines
            toss_id        = story.get("toss_to", "").strip()
            toss_anchor_id = toss_id if toss_id else other_anchor["id"]

            headline  = story.get("title", story.get("headline", "untitled"))
            seg_id    = f"{section_name}__{headline[:40]}"
            shot_mode = SOLO_SHOT.get(story_anchor["id"], "solo_a")

            has_break = (
                story.get("break_after") is not None
                and story.get("break_question", "").strip()
                and story.get("break_response_lead", "").strip()
            )

            has_broll = story.get("broll_after") is not None

            # ── pre_story ──────────────────────────────────────────────────
            if story.get("pre_story", "").strip():
                pre_id = f"{seg_id}__pre"
                toss_shot = SOLO_SHOT.get(toss_anchor_id, "solo_a")
                segments.append(_make_segment(
                    segment_id           = pre_id,
                    shot_mode            = toss_shot,
                    anchor_id            = toss_anchor_id,
                    lower_third_headline = None,
                    lower_third_source   = None,
                    transition_in        = "cut",
                    transition_out       = "cut",
                    anchor_clip          = _clip_path(pre_id, jobs),
                    comment              = f"{toss_anchor_id} tosses to {story_anchor['id']}",
                ))

            # ── story body part A ──────────────────────────────────────────
            segments.append(_make_segment(
                segment_id           = seg_id,
                shot_mode            = shot_mode,
                anchor_id            = story_anchor["id"],
                lower_third_headline = headline,
                lower_third_source   = story.get("source_name"),
                transition_in        = "crossfade",
                transition_out       = "cut",
                anchor_clip          = _clip_path(seg_id, jobs),
                comment              = f"{story_anchor['id']} reads story {story_counter + 1}",
            ))

            # ── broll window ───────────────────────────────────────────────
            if has_broll:
                broll_id = f"{seg_id}__broll_voice"
                segments.append(_make_segment(
                    segment_id           = broll_id,
                    shot_mode            = "broll",
                    anchor_id            = story_anchor["id"],
                    lower_third_headline = headline,
                    lower_third_source   = story.get("source_name"),
                    transition_in        = "cut",
                    transition_out       = "cut",
                    anchor_clip          = _clip_path(broll_id, jobs),
                    comment              = f"B-roll — {story_anchor['id']} voice over video",
                ))
                # Return to anchor if broll_return index doesn't reach end of sentences
                broll_return = story.get("broll_return")
                n_sentences  = len(story.get("sentences", []))
                if broll_return is not None and int(broll_return) < n_sentences:
                    broll_r_id = f"{seg_id}__broll_return"
                    segments.append(_make_segment(
                        segment_id           = broll_r_id,
                        shot_mode            = shot_mode,
                        anchor_id            = story_anchor["id"],
                        lower_third_headline = headline,
                        lower_third_source   = story.get("source_name"),
                        transition_in        = "cut",
                        transition_out       = "cut",
                        anchor_clip          = _clip_path(broll_r_id, jobs),
                        comment              = f"{story_anchor['id']} returns after broll",
                    ))

            # ── mid-story break ────────────────────────────────────────────
            if has_break:
                break_q_id = f"{seg_id}__break_q"
                break_r_id = f"{seg_id}__break_r"
                toss_shot  = SOLO_SHOT.get(toss_anchor_id, "solo_a")
                segments.append(_make_segment(
                    segment_id           = break_q_id,
                    shot_mode            = toss_shot,
                    anchor_id            = toss_anchor_id,
                    lower_third_headline = None,
                    lower_third_source   = None,
                    transition_in        = "cut",
                    transition_out       = "cut",
                    anchor_clip          = _clip_path(break_q_id, jobs),
                    comment              = f"{toss_anchor_id} asks break question",
                ))
                segments.append(_make_segment(
                    segment_id           = break_r_id,
                    shot_mode            = shot_mode,
                    anchor_id            = story_anchor["id"],
                    lower_third_headline = headline,
                    lower_third_source   = story.get("source_name"),
                    transition_in        = "cut",
                    transition_out       = "cut",
                    anchor_clip          = _clip_path(break_r_id, jobs),
                    comment              = f"{story_anchor['id']} responds and continues",
                ))

            # ── post_story ─────────────────────────────────────────────────
            if story.get("post_story", "").strip():
                post_id   = f"{seg_id}__post"
                toss_shot = SOLO_SHOT.get(toss_anchor_id, "solo_a")
                segments.append(_make_segment(
                    segment_id           = post_id,
                    shot_mode            = toss_shot,
                    anchor_id            = toss_anchor_id,
                    lower_third_headline = None,
                    lower_third_source   = None,
                    transition_in        = "cut",
                    transition_out       = "cut",
                    anchor_clip          = _clip_path(post_id, jobs),
                    comment              = f"{toss_anchor_id} reacts to story {story_counter + 1}",
                ))

            story_counter += 1

    # ── Episode outro ──────────────────────────────────────────────────────────
    if stories.get("outro", "").strip():
        outro_id = "__outro__"
        segments.append(_make_segment(
            segment_id           = outro_id,
            shot_mode            = "bumper",
            anchor_id            = ANCHOR_LEAD,
            lower_third_headline = None,
            lower_third_source   = None,
            transition_in        = "cut",
            transition_out       = "cut",
            anchor_clip          = _clip_path(outro_id, jobs),
            comment              = "Episode outro — wall default + voice",
        ))

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

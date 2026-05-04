"""
Smoke test: submit one story to HeyGen in test mode, poll, download.
Run from newscrew/ directory: python smoke_test.py
"""

import json
import time
import requests
from pathlib import Path
import config

HEADERS = {
    "X-Api-Key": config.HEYGEN_API_KEY,
    "Content-Type": "application/json",
}

TEST_NAME = "smoke_test_003"
REAL_STORY_NAME = "real_story_test_002"

# ── Single test segment ────────────────────────────────────────────────────────
TEST_SEGMENT = {
    "segment_id": TEST_NAME,
    "script":     "Hello Vadim. My name is Annie, and I am a virtual news anchor created by HeyGen.",
    "avatar_id":  config.ANCHORS[0]["avatar_id"],
    "voice_id":   config.ANCHORS[0]["voice_id"],
}

def submit_test_job(segment: dict) -> str:
    payload = {
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
            }
        ],
        "dimension": {"width": 1920, "height": 1080},
        "test": False,   # ← watermarked, free, safe to run repeatedly
    }

    print(f"Submitting test job for avatar: {segment['avatar_id']}")
    resp = requests.post(
        f"{config.HEYGEN_API_BASE}/v2/video/generate",
        headers=HEADERS,
        json=payload,
        timeout=(10,120),
    )

    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text}")
        resp.raise_for_status()

    video_id = resp.json()["data"]["video_id"]
    print(f"Job submitted. video_id: {video_id}")
    return video_id


def poll_until_done(video_id: str, interval: int = 15, max_attempts: int = 80) -> str | None:
    print(f"Polling every {interval}s...")
    for attempt in range(1, max_attempts + 1):
        time.sleep(interval)
        try:
            resp = requests.get(
                f"{config.HEYGEN_API_BASE}/v1/video_status.get",
                headers=HEADERS,
                params={"video_id": video_id},
                timeout=30,
            )
            if resp.status_code in (502, 503, 504):
                print(f"  attempt {attempt}: transient {resp.status_code}, retrying...")
                continue
            resp.raise_for_status()
            data = resp.json()["data"]
            print(f"  raw response: {data}")  # add this temporarily
            status = data.get("status")
            print(f"  attempt {attempt}: {status}")

            if status == "completed":
                return data["video_url"]
            elif status == "failed":
                print(f"  FAILED: {data}")
                return None

        except requests.exceptions.ReadTimeout:
            print(f"  attempt {attempt}: read timeout, retrying...")
            continue

    print("Max attempts reached.")
    return None


def download_clip(url: str, dest: Path) -> None:
    print(f"Downloading to {dest}...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"Done. File size: {dest.stat().st_size / 1024:.1f} KB")

def test_real_story(stories_path: str) -> None:
    """Submit one real story from stories.json in test mode."""
    import json
    stories = json.loads(Path(stories_path).read_text())
    
    # Grab the first story from the first section
    selected_story = stories["sections"][0]["stories"][0]
    
    segment = {
        "segment_id": REAL_STORY_NAME,
        "script":     selected_story["body"],
        "avatar_id":  config.ANCHORS[4]["avatar_id"],
        "voice_id":   config.ANCHORS[4]["voice_id"],
    }
    
    print(f"Testing with story: {selected_story['title']}")
    print(f"Script length: {len(selected_story['body'])} chars")
    
    video_id = submit_test_job(segment)
    video_url = poll_until_done(video_id)
    
    if video_url:
        out = config.ANCHOR_CLIPS_DIR / f"{REAL_STORY_NAME}.mp4"
        download_clip(video_url, out)
        print(f"\nReal story test PASSED. Clip at: {out}")
    else:
        print("\nReal story test FAILED.")

if __name__ == "__main__":
    test_real_story(config.STORIES_JSON)

    # video_id = submit_test_job(TEST_SEGMENT)
    #video_url = poll_until_done(video_id)

    # if video_url:
      #  out = ANCHOR_CLIPS_DIR / f"{TEST_NAME}.mp4"
    #     download_clip(video_url, out)
    #     print(f"\nSmoke test PASSED. Clip at: {out}")
    # else:
    #     print("\nSmoke test FAILED.")

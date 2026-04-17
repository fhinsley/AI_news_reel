#!/usr/bin/env python3
"""Upload the weekly Two-Sides debate video and captions to YouTube.

Identical OAuth and upload mechanics as upload_youtube.py.
Adapted for the debate pipeline: different playlist, title derived
from the debate proposition, debate-appropriate tags and description.

First run: opens a browser window to authorize access to your YouTube
channel. Saves a token file so all subsequent runs are fully headless.

Uploads:
  - Debate.mp4          → video
  - DebateCaptions.srt  → caption track (English)

Pipeline position: run after build_video.py and generate_srt.py.
"""

import json
import pickle
import webbrowser
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config
from generate_srt import SRT_OUTPUT_FILE

# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Replace with your Two-Sides playlist ID once created in YouTube Studio.
# Grab the ID from the playlist URL: ?list=XXXXXXXXXX
DEBATE_PLAYLIST_ID = "PLrR4Ecy5-paerFxTneDsXZL5A8RuvutCU"

# Reuse the same OAuth credentials and token as the newsreel pipeline.
SECRETS_FILE = config.PROJECT_ROOT / "client_secrets.json"
TOKEN_FILE   = config.PROJECT_ROOT / "youtube_token.pickle"

# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------

CATEGORY_ID = "28"       # Science & Technology
PRIVACY     = "public"   # "public", "unlisted", or "private"

TAGS = [
    "politics", "debate", "point counterpoint",
    "left vs right", "media bias", "two sides",
    "news analysis", "current events",
]

# ---------------------------------------------------------------------------
# Auth — identical to upload_youtube.py
# ---------------------------------------------------------------------------

def get_youtube_client():
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print("Token saved — future runs will not require browser auth.")

    return build("youtube", "v3", credentials=creds)

# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def load_proposition() -> tuple[str, str, str]:
    with open(config.DEBATE_JSON_FILE, "r") as f:
        data = json.load(f)
    proposition   = data.get("proposition",   "Two Sides Debate")
    topic_summary = data.get("topic_summary", "")
    week_of       = data.get("week_of",       config.START_DATE.strftime("%B %d, %Y"))
    return proposition, topic_summary, week_of


def upload_video(youtube) -> str:
    video_path = Path(config.OUTPUT_VIDEO)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    proposition, topic_summary, week_of = load_proposition()

    # YouTube enforces a 100-character title limit.
    # Truncate the proposition at a word boundary if it would push over.
    prefix = "Two Sides | "
    max_prop_len = 100 - len(prefix)
    if len(proposition) > max_prop_len:
        truncated = proposition[:max_prop_len].rsplit(" ", 1)[0].rstrip(",;:")
        prop_display = truncated + "..."
    else:
        prop_display = proposition
    title = f"{prefix}{prop_display}"

    description = (
        f"Week of {week_of}\n\n"
        f"{topic_summary}\n\n"
        f'Proposition: "{proposition}"\n\n'
        "A structured point-counterpoint debate presenting the strongest "
        "left-leaning and right-leaning arguments on this week's top story. "
        "Both sides argue from genuine conviction — not strawmen.\n\n"
        "Generated with an automated debate pipeline using "
        "Claude (Anthropic) and ElevenLabs."
    )

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        TAGS,
            "categoryId":  CATEGORY_ID,
        },
        "status": {
            "privacyStatus":           PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 8,
    )

    print(f"Uploading video: {video_path.name}")
    print(f"Title: {title}")

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Upload progress: {pct}%", end="\r")

    video_id = response["id"]
    print(f"\nVideo uploaded: https://www.youtube.com/watch?v={video_id}")
    return video_id


def upload_captions(youtube, video_id: str) -> None:
    """Upload DebateCaptions.srt as English captions — identical to upload_youtube.py."""
    if not SRT_OUTPUT_FILE.exists():
        print(f"WARNING: {SRT_OUTPUT_FILE} not found — skipping captions.")
        print("         Run generate_srt.py first.")
        return

    print(f"Uploading captions: {SRT_OUTPUT_FILE.name}")
    media = MediaFileUpload(str(SRT_OUTPUT_FILE), mimetype="application/octet-stream")

    youtube.captions().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId":  video_id,
                "language": "en",
                "name":     "English",
                "isDraft":  False,
            }
        },
        media_body=media,
    ).execute()
    print("Captions uploaded.")


def add_to_playlist(youtube, video_id: str) -> None:
    if DEBATE_PLAYLIST_ID == "YOUR_DEBATE_PLAYLIST_ID_HERE":
        print("WARNING: DEBATE_PLAYLIST_ID not set — skipping playlist assignment.")
        print("         Paste your playlist ID into upload_youtube.py")
        return

    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": DEBATE_PLAYLIST_ID,
                "resourceId": {
                    "kind":    "youtube#video",
                    "videoId": video_id,
                },
            }
        },
    ).execute()
    print(f"Added to playlist: {DEBATE_PLAYLIST_ID}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not SECRETS_FILE.exists():
        print(f"ERROR: {SECRETS_FILE} not found.")
        print("(Same client_secrets.json used by the newsreel pipeline — no new credentials needed.)")
        return 1

    try:
        youtube  = get_youtube_client()
        video_id = upload_video(youtube)
        upload_captions(youtube, video_id)
        add_to_playlist(youtube, video_id)
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"\nDone. Watch: {url}")
        webbrowser.open(url)
        return 0
    except Exception as exc:
        print(f"\nUpload failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Upload the weekly newsreel video and captions to YouTube.

First run: opens a browser window to authorize access to your YouTube
channel. Saves a token file so all subsequent runs are fully headless.

Uploads:
  - News.mp4     → video
  - Captions.srt → caption track (English)

Pipeline position: run after build_video.py and generate_srt.py.
"""

import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

PLAYLIST_ID = "PLrR4Ecy5-pac3xXoGOmmdcHne0hVW_lWG"  # "AI Newsreel" playlist

SECRETS_FILE = Path(__file__).resolve().parent.parent / "client_secrets.json"
TOKEN_FILE   = Path(__file__).resolve().parent.parent / "youtube_token.pickle"

# ---------------------------------------------------------------------------
# Video metadata — pulled from config where possible
# ---------------------------------------------------------------------------

CATEGORY_ID  = "28"        # Science & Technology
PRIVACY      = "public"    # "public", "unlisted", or "private"
TAGS         = ["AI", "artificial intelligence", "AI news", "weekly AI newsreel",
                "machine learning", "tech news"]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_youtube_client():
    """Return an authenticated YouTube API client.

    Loads saved credentials if available, otherwise runs the OAuth flow
    (opens a browser on first run) and saves the token for future runs.
    """
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
# Upload
# ---------------------------------------------------------------------------

def upload_video(youtube) -> str:
    """Upload News.mp4 and return the YouTube video ID."""
    video_path = Path(config.OUTPUT_VIDEO)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    title       = config.OPENING_TITLE
    description = (
        f"Weekly summary of AI news for {config.OPENING_TITLE.replace('AI Newsreel ', '')}.\n\n"
        "Sources: DeepLearning.AI The Batch, Import AI, CNBC AI, "
        "MIT Technology Review, Synced Review, Simon Willison.\n\n"
        "Generated with an automated multi-voice pipeline using "
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
        chunksize=1024 * 1024 * 8,  # 8 MB chunks
    )

    print(f"Uploading video: {video_path.name}")
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


def add_to_playlist(youtube, video_id: str) -> None:
    """Add the uploaded video to the newsreel playlist."""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": PLAYLIST_ID,
                "resourceId": {
                    "kind":    "youtube#video",
                    "videoId": video_id,
                },
            }
        },
    ).execute()
    print(f"Added to playlist: {PLAYLIST_ID}")


def upload_captions(youtube, video_id: str) -> None:
    """Upload Captions.srt to the video as English captions."""
    srt_path = config.SRT_OUTPUT_FILE
    if not srt_path.exists():
        print(f"WARNING: Caption file not found: {srt_path} — skipping captions.")
        return

    print(f"Uploading captions: {srt_path.name}")
    media = MediaFileUpload(str(srt_path), mimetype="application/octet-stream")

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

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not SECRETS_FILE.exists():
        print(f"ERROR: {SECRETS_FILE} not found.")
        print("Download OAuth credentials from Google Cloud Console and save as client_secrets.json")
        return 1

    try:
        youtube  = get_youtube_client()
        video_id = upload_video(youtube)
        upload_captions(youtube, video_id)
        add_to_playlist(youtube, video_id)
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"\nDone. Watch: {url}")
        # webbrowser.open(url)
        return 0
    except Exception as exc:
        print(f"\nUpload failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

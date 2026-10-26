"""Upload finished videos to Google Drive (for posting from a phone) or to YouTube directly."""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/drive.file",
]


def _creds() -> Credentials:
    # One refresh token from Google's OAuth Playground, stored as GitHub secrets.
    return Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )


def _drive_folder(drive, name: str, parent: str = None) -> str:
    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent:
        q += f" and '{parent}' in parents"
    found = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    return drive.files().create(body=meta, fields="id").execute()["id"]


def to_drive(folder_name: str, subfolder: str, files) -> str:
    """Copy files into Drive/<folder_name>/<subfolder>. Returns the subfolder link."""
    drive = build("drive", "v3", credentials=_creds(), cache_discovery=False)
    root = _drive_folder(drive, folder_name)
    sub = _drive_folder(drive, subfolder, root)
    for f in files:
        f = Path(f)
        drive.files().create(
            body={"name": f.name, "parents": [sub]},
            media_body=MediaFileUpload(str(f), resumable=True),
            fields="id",
        ).execute()
    return f"https://drive.google.com/drive/folders/{sub}"


def to_youtube(video: Path, title: str, description: str, tags, category: str,
               publish_at: str, thumbnail: Path = None, captions: Path = None) -> str:
    """Upload as a private video scheduled for publish_at (RFC 3339, UTC). Returns the video id.

    The video stays private until publish_at, so there is time to review it in YouTube Studio.
    Only works once Google has approved the API project's audit; before that YouTube locks
    API uploads as private.
    """
    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    body = {
        "snippet": {"title": title[:100], "description": description[:5000],
                    "tags": tags[:30], "categoryId": category, "defaultLanguage": "en"},
        "status": {"privacyStatus": "private", "publishAt": publish_at,
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    if thumbnail:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
    if captions:
        yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": vid, "language": "en", "name": "English"}},
            media_body=MediaFileUpload(str(captions), mimetype="application/octet-stream"),
        ).execute()
    return vid

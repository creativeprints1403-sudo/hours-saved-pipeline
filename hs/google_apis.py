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
    missing = [k for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing GitHub secret(s): {', '.join(missing)}. Add them under "
                         "Settings > Secrets and variables > Actions, spelled exactly like this.")
    return Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        # No scopes here: asking for scopes on refresh fails with invalid_scope if the
        # token was granted fewer. The token keeps the scopes ticked in the Playground.
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
    """Copy files into Drive/<folder_name>/<subfolder>. Returns the subfolder link and {name: file id}."""
    drive = build("drive", "v3", credentials=_creds(), cache_discovery=False)
    root = _drive_folder(drive, folder_name)
    sub = _drive_folder(drive, subfolder, root)
    ids = {}
    for f in files:
        f = Path(f)
        ids[f.name] = drive.files().create(
            body={"name": f.name, "parents": [sub]},
            media_body=MediaFileUpload(str(f), resumable=True),
            fields="id",
        ).execute()["id"]
    return f"https://drive.google.com/drive/folders/{sub}", ids


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


def check(mode: str):
    """Fail in seconds, not after rendering, if the token can't do what config.toml asks."""
    import json
    import urllib.request
    from google.auth.transport.requests import Request
    creds = _creds()
    creds.refresh(Request())
    with urllib.request.urlopen(f"https://oauth2.googleapis.com/tokeninfo?access_token={creds.token}") as r:
        granted = json.load(r).get("scope", "").split()
    print("Google token allows: " + (", ".join(s.rsplit("/", 1)[-1] for s in granted) or "nothing"))
    # Google won't grant YouTube and Drive scopes in one request, so the token holds
    # only the scope for the current mode (force-ssl also covers uploads).
    need = [SCOPES[1]] if mode == "youtube" else [SCOPES[2]]
    missing = [s for s in need if s not in granted]
    if missing:
        raise SystemExit(f"The refresh token is missing: {', '.join(missing)}. Make a new one in the OAuth "
                         "Playground with only that scope and tick its box on Google's permission screen.")


if __name__ == "__main__":
    import tomllib
    with open(Path(__file__).resolve().parent.parent / "config.toml", "rb") as f:
        check(tomllib.load(f)["youtube"]["mode"])

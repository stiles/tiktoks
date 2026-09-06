"""Upload an assembled post as a YouTube Short.

There is no Shorts-specific API. `videos.insert` plus a vertical MP4 under three
minutes is enough; YouTube classifies it. Image carousels on the Shorts feed are
channel posts, not this endpoint, and have no API.

Needs the `youtube` extra and a Desktop OAuth client JSON at
`data/youtube-client-secrets.json`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tiktoks.config import POSTS_DIR, YOUTUBE_CLIENT_SECRETS, YOUTUBE_TOKEN
from tiktoks.post import merge_publish
from tiktoks.video import assemble, load_manifest, resolve_post_dir

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
# Education. Geography quizzes and data maps belong here more than People & Blogs.
CATEGORY_EDUCATION = "27"


class YouTubeError(RuntimeError):
    """OAuth or upload failed."""


def auth(*, secrets: Path | None = None, token: Path | None = None) -> Path:
    """Open a browser once, then store a refresh token for later uploads."""
    flow_cls, _, _ = _google()
    secrets_path = Path(secrets or YOUTUBE_CLIENT_SECRETS)
    token_path = Path(token or YOUTUBE_TOKEN)
    if not secrets_path.exists():
        raise YouTubeError(
            f"{secrets_path} is missing. Create a Desktop OAuth client in Google Cloud, "
            "enable YouTube Data API v3, and save the JSON there."
        )
    flow = flow_cls.from_client_secrets_file(str(secrets_path), scopes=SCOPES)
    credentials = flow.run_local_server(port=0)
    _write_token(token_path, credentials)
    return token_path


def upload(
    post_dir: Path | str,
    *,
    privacy: str = "private",
    assemble_if_missing: bool = True,
    audio: Path | str | bool | None = None,
    secrets: Path | None = None,
    token: Path | None = None,
) -> dict:
    """Upload the post's MP4 and write the video ID into post.json.

    Default privacy is private so a first upload can be checked in Studio.
    """
    if privacy not in {"private", "unlisted", "public"}:
        raise YouTubeError(f"Unknown privacy {privacy!r}")

    directory = resolve_post_dir(post_dir)
    manifest = load_manifest(directory)
    video_path = directory / f"{manifest['slug']}.mp4"
    if not video_path.exists():
        if not assemble_if_missing:
            raise YouTubeError(f"No video at {video_path}. Run tiktoks video first.")
        video_path = assemble(directory, audio=audio)

    youtube = _service(secrets=secrets, token=token)
    media_cls = _media()
    body = {
        "snippet": {
            "title": _title(manifest),
            "description": _description(manifest),
            "tags": [tag.lstrip("#") for tag in manifest.get("hashtags") or []],
            "categoryId": CATEGORY_EDUCATION,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media_cls(str(video_path), mimetype="video/mp4", resumable=True),
    )
    response = request.execute()
    video_id = response.get("id")
    if not video_id:
        raise YouTubeError(f"Upload returned no video id: {response}")
    return record_upload(directory / "post.json", video_id)


def pending_uploads(root: Path | str | None = None) -> list[Path]:
    """Theme directories with an MP4 and no YouTube id yet."""
    base = Path(root or POSTS_DIR)
    pending = []
    for manifest_path in sorted(base.rglob("post.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        youtube = (data.get("publish") or {}).get("youtube") or {}
        if youtube.get("video_id"):
            continue
        slug = data.get("slug")
        if slug and (manifest_path.parent / f"{slug}.mp4").exists():
            pending.append(manifest_path.parent)
    return pending


def record_upload(manifest_path: Path | str, video_id: str, when: date | None = None) -> dict:
    """Write the YouTube id into an existing post.json without touching TikTok fields."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    youtube = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "posted_at": (when or date.today()).isoformat(),
    }
    data["publish"] = merge_publish(data.get("publish") or {}, {"youtube": youtube})
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return youtube


def _title(manifest: dict) -> str:
    title = (manifest.get("title") or manifest["slug"]).strip()
    if len(title) > 100:
        title = title[:97].rstrip() + "..."
    return title


def _description(manifest: dict) -> str:
    caption = (manifest.get("caption") or "").strip()
    sources = "\n".join(manifest.get("sources") or [])
    credit = None
    audio = manifest.get("audio")
    if isinstance(audio, dict):
        credit = (audio.get("attribution") or "").strip() or None
    parts = [part for part in (caption, sources, credit, "#Shorts") if part]
    return "\n\n".join(parts)


def _service(*, secrets: Path | None = None, token: Path | None = None):
    _, credentials_cls, request_cls = _google()
    from googleapiclient.discovery import build

    token_path = Path(token or YOUTUBE_TOKEN)
    secrets_path = Path(secrets or YOUTUBE_CLIENT_SECRETS)
    credentials = None
    if token_path.exists():
        credentials = credentials_cls.from_authorized_user_file(str(token_path), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(request_cls())
        _write_token(token_path, credentials)
    if not credentials or not credentials.valid:
        if not secrets_path.exists():
            raise YouTubeError(
                f"No YouTube token at {token_path}. Run: uv run tiktoks youtube auth"
            )
        auth(secrets=secrets_path, token=token_path)
        credentials = credentials_cls.from_authorized_user_file(str(token_path), SCOPES)
    return build("youtube", "v3", credentials=credentials)


def _write_token(path: Path, credentials) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")


def _google():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise YouTubeError(
            "YouTube upload needs the youtube extra: uv sync --extra youtube"
        ) from exc
    return InstalledAppFlow, Credentials, Request


def _media():
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise YouTubeError(
            "YouTube upload needs the youtube extra: uv sync --extra youtube"
        ) from exc
    return MediaFileUpload

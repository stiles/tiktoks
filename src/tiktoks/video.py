"""Assemble a vertical MP4 from a rendered post's PNG sequence.

Shorts are video. The slides already exist; each one becomes a clip held for its
kind, with a slow push-in on the map so the frame is never dead. Clips are then
joined under the music bed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tiktoks.config import AUDIO_CATALOG_PATH, AUDIO_DIR, CANVAS_SIZE
from tiktoks.io import read_yaml
from tiktoks.paths import ensure_dir

FPS = 30
# Zoom gained over a slide's hold, as a fraction. The map pushes harder than a
# whole frame can: text stays put, and 3.5% on type drifts it toward the margins.
MAP_PUSH = 0.07
FRAME_PUSH = 0.035
# Keeps the map panel's own border out of the zoomed crop.
MAP_INSET = 2
SEGMENT_DIR = ".segments"

# Seconds on screen. Prompt and mystery are the guess beats; answers cut sooner.
HOLD = {
    "cover": 2.5,
    "prompt": 4.0,
    "hint": 3.0,
    "mystery": 5.0,
    "answer": 2.5,
    "scorecard": 3.5,
    "challenge": 4.0,
}
DEFAULT_HOLD = 2.5

# Bed sits under the maps. Loud enough to read as a Short, quiet enough to think.
AUDIO_VOLUME = 0.28
AUDIO_FADE_IN = 0.4
AUDIO_FADE_OUT = 1.0


class VideoError(RuntimeError):
    """ffmpeg failed, or the post directory is missing slides."""


def hold_for(kind: str) -> float:
    return HOLD.get(kind, DEFAULT_HOLD)


def resolve_post_dir(post_dir: Path | str) -> Path:
    path = Path(post_dir)
    if path.is_file() and path.name == "post.json":
        return path.parent
    return path


def load_manifest(post_dir: Path | str) -> dict:
    directory = resolve_post_dir(post_dir)
    path = directory / "post.json"
    if not path.exists():
        raise VideoError(f"No post.json in {directory}")
    return json.loads(path.read_text(encoding="utf-8"))


def slide_files(
    post_dir: Path | str, manifest: dict | None = None
) -> list[tuple[Path, str, float]]:
    """PNG path, kind and hold, in slide order. Skips the contact sheet."""
    directory = resolve_post_dir(post_dir)
    manifest = manifest or load_manifest(directory)
    rows = []
    missing = []
    for record in manifest.get("slides") or []:
        path = directory / record["file"]
        if not path.exists():
            missing.append(record["file"])
            continue
        kind = record.get("kind") or "slide"
        rows.append((path, kind, hold_for(kind)))
    if missing:
        raise VideoError(f"Missing slides in {directory}: {', '.join(missing)}")
    if not rows:
        raise VideoError(f"No slides listed in {directory / 'post.json'}")
    return rows


def map_rects(manifest: dict) -> list[list[int] | None]:
    """Map box per slide, aligned with `slide_files`. None for slides without a map."""
    return [record.get("map") for record in manifest.get("slides") or []]


def frame_count(seconds: float) -> int:
    return max(round(seconds * FPS), 1)


def total_duration(rows: list[tuple[Path, str, float]]) -> float:
    return sum(frame_count(duration) for _, _, duration in rows) / FPS


def push_graph(frames: int, map_rect: list[int] | None = None) -> str:
    """ffmpeg filter graph for one slide: the map zooms inside its own box, or, with no
    map, the whole frame pushes gently. zoompan jitters at integer crops, so it works
    on a 2x upscale."""
    width, height = CANVAS_SIZE
    base = f"[0:v]scale={width}:{height}"
    if map_rect is None:
        zoom = f"1+{FRAME_PUSH}*on/{frames}"
        return (
            f"{base},scale={width * 2}:{height * 2},"
            f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
            f":d=1:s={width}x{height}:fps={FPS},format=yuv420p"
        )
    x0, y0, w, h = _push_box(map_rect)
    zoom = f"1+{MAP_PUSH}*on/{frames}"
    return (
        f"{base},split[bg][m];"
        f"[m]crop={w}:{h}:{x0}:{y0},scale={w * 2}:{h * 2},"
        f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
        f":d=1:s={w}x{h}:fps={FPS}[z];"
        f"[bg][z]overlay={x0}:{y0},format=yuv420p"
    )


def _push_box(rect: list[int]) -> tuple[int, int, int, int]:
    """(x, y, w, h) inset from the map box and snapped to even pixels for 4:2:0."""
    width, height = CANVAS_SIZE
    x0 = max(int(rect[0]) + MAP_INSET, 0)
    y0 = max(int(rect[1]) + MAP_INSET, 0)
    x1 = min(int(rect[2]) - MAP_INSET, width)
    y1 = min(int(rect[3]) - MAP_INSET, height)
    x0, y0 = x0 + x0 % 2, y0 + y0 % 2
    x1, y1 = x1 - x1 % 2, y1 - y1 % 2
    return x0, y0, x1 - x0, y1 - y0


def render_segment(
    png: Path,
    frames: int,
    destination: Path,
    *,
    map_rect: list[int] | None = None,
) -> Path:
    """One slide as a silent clip of exactly `frames` frames."""
    _encode(
        "-framerate",
        str(FPS),
        "-loop",
        "1",
        "-i",
        str(png),
        "-filter_complex",
        push_graph(frames, map_rect),
        "-frames:v",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-r",
        str(FPS),
        str(destination),
    )
    return destination


def _encode(*args: str) -> None:
    result = subprocess.run(
        [_ffmpeg(), "-y", "-v", "error", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout or "").strip().splitlines()[-12:])
        raise VideoError(f"ffmpeg failed:\n{tail or 'no ffmpeg output'}")


def load_catalog(path: Path | str | None = None) -> dict:
    catalog_path = Path(path or AUDIO_CATALOG_PATH)
    if not catalog_path.exists():
        return {"default": None, "beds": []}
    data = read_yaml(catalog_path)
    return {"default": data.get("default"), "beds": data.get("beds") or []}


def beds(path: Path | str | None = None) -> dict[str, dict]:
    return {entry["slug"]: entry for entry in load_catalog(path)["beds"] if entry.get("slug")}


def load_audio_meta(path: Path | str | None = None) -> dict:
    """Metadata for the default bed, or for a slug if `path` is a slug string."""
    catalog = beds()
    if path and str(path) in catalog:
        return catalog[str(path)]
    default = load_catalog().get("default")
    return catalog.get(default) or {}


def music_attribution(meta: dict | None = None) -> str | None:
    data = meta if meta is not None else load_audio_meta()
    text = (data.get("attribution") or "").strip()
    return text or None


def assemble(
    post_dir: Path | str,
    *,
    output: Path | str | None = None,
    audio: Path | str | bool | None = None,
) -> Path:
    """Write `{slug}.mp4` next to the PNGs. Returns the video path.

    `audio` is the bed track, False for silence, None for format matching.
    """
    directory = resolve_post_dir(post_dir)
    manifest = load_manifest(directory)
    rows = slide_files(directory, manifest)
    destination = Path(output) if output else directory / f"{manifest['slug']}.mp4"
    ffmpeg = _ffmpeg()
    duration = total_duration(rows)
    audio_path, audio_meta = resolve_bed(audio, manifest=manifest)

    work = ensure_dir(directory / SEGMENT_DIR)
    concat_path = work / "concat.txt"
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        *_audio_input(audio_path, duration),
        "-t",
        f"{duration:.3f}",
        *_audio_filters(audio_path, duration),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    try:
        names = []
        for index, ((png, _, hold), rect) in enumerate(
            zip(rows, map_rects(manifest), strict=True), start=1
        ):
            segment = render_segment(
                png, frame_count(hold), work / f"slide-{index:02d}.mp4", map_rect=rect
            )
            names.append(segment.name)
        concat_path.write_text("".join(f"file '{name}'\n" for name in names), encoding="utf-8")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = "\n".join(detail[-12:]) if detail else "no ffmpeg output"
        raise VideoError(f"ffmpeg failed for {destination}:\n{tail}")
    _record_audio(directory / "post.json", audio_meta, destination)
    return destination


def audio_approval(entry: dict) -> str | None:
    """Catalog evidence is a human review record, not a legal guarantee."""
    license_name = entry.get("license")
    if license_name not in {
        "CC0 1.0",
        "CC BY 3.0",
        "CC BY 4.0",
        "Artlist",
        "YouTube Audio Library",
    }:
        return "unsupported or missing music license"
    if license_name in {"Artlist", "YouTube Audio Library"}:
        if entry.get("rights_verified") is not True or not entry.get("license_evidence"):
            return "confirm license coverage and record license_evidence for this track"
    if license_name in {"CC BY 3.0", "CC BY 4.0"} and not entry.get("attribution"):
        return "missing required Creative Commons attribution"
    if not entry.get("source") or not entry.get("license_url"):
        return "missing source or license evidence"
    if entry.get("reviewed_clean") is not True:
        return "not reviewed for spoken ads, vocals and preview watermarks"
    if not entry.get("sha256"):
        return "missing checksum for the reviewed audio file"
    return None


def select_bed(manifest: dict) -> str:
    """Choose only reviewed tracks explicitly matched to this post's format."""
    candidates = [
        slug
        for slug, entry in beds().items()
        if audio_approval(entry) is None and manifest.get("format") in entry.get("formats", [])
    ]
    if not candidates:
        raise VideoError(
            f"No reviewed music for format {manifest.get('format')!r}. "
            "Add a clean, style-matched track to content/audio/catalog.yaml, "
            "then retry. See docs/youtube-workflow.md."
        )
    preferred = load_catalog().get("default")
    return preferred if preferred in candidates else sorted(candidates)[0]


def resolve_bed(
    audio: Path | str | bool | None, *, manifest: dict | None = None
) -> tuple[Path | None, dict | None]:
    """False is silence; None chooses reviewed music for the post format."""
    if audio is False:
        return None, None
    catalog = beds()
    if audio in (None, True):
        slug = select_bed(manifest or {})
        audio = slug
    text = str(audio)
    if text in catalog:
        entry = catalog[text]
        reason = audio_approval(entry)
        if reason:
            raise VideoError(f"Audio {text!r} blocked: {reason}. See docs/youtube-workflow.md.")
        path = AUDIO_DIR / entry["file"]
        if not path.exists():
            raise VideoError(f"Audio file for {text!r} is missing: {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise VideoError(f"Audio {text!r} changed since review; review the file again.")
        return path, entry
    path = Path(text)
    if path.exists():
        resolved = path.resolve()
        for entry in catalog.values():
            candidate = AUDIO_DIR / entry["file"]
            if candidate.exists() and candidate.resolve() == resolved:
                return resolve_bed(entry["slug"], manifest=manifest)
        raise VideoError(
            "Uncataloged audio is blocked. Add license evidence and a clean-file review."
        )
    known = ", ".join(catalog) or "(none)"
    raise VideoError(f"Unknown audio {text!r}. Known beds: {known}")


def _audio_input(audio_path: Path | None, duration: float) -> list[str]:
    if audio_path is None:
        return ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    return ["-stream_loop", "-1", "-i", str(audio_path)]


def _audio_filters(audio_path: Path | None, duration: float) -> list[str]:
    if audio_path is None:
        return []
    fade_out_start = max(0.0, duration - AUDIO_FADE_OUT)
    return [
        "-af",
        (
            f"volume={AUDIO_VOLUME},"
            f"afade=t=in:st=0:d={AUDIO_FADE_IN},"
            f"afade=t=out:st={fade_out_start:.3f}:d={AUDIO_FADE_OUT}"
        ),
    ]


def _record_audio(manifest_path: Path, meta: dict | None, video_path: Path) -> None:
    if not manifest_path.exists():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    payload["video_sha256"] = hashlib.sha256(video_path.read_bytes()).hexdigest()
    if meta:
        payload["audio"] = {
            "slug": meta.get("slug"),
            "title": meta.get("title"),
            "artist": meta.get("artist"),
            "license": meta.get("license"),
            "license_url": meta.get("license_url"),
            "rights_verified": meta.get("rights_verified"),
            "license_evidence": meta.get("license_evidence"),
            "reviewed_clean": meta.get("reviewed_clean"),
            "sha256": meta.get("sha256"),
            "source": meta.get("source"),
            "attribution": (meta.get("attribution") or "").strip() or None,
        }
    else:
        payload["audio"] = None
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise VideoError("ffmpeg is not on PATH")
    return path

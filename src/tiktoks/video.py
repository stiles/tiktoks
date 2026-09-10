"""Assemble a vertical MP4 from a rendered post's PNG sequence.

Shorts are video. The slides already exist; this is an ffmpeg concat with a hold
per slide kind so a prompt sits long enough to read and the answer cuts in.
A Ken Burns push on the map is still open.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tiktoks.config import AUDIO_CATALOG_PATH, AUDIO_DIR, CANVAS_SIZE
from tiktoks.io import read_yaml

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
CONCAT_NAME = ".concat.txt"


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


def concat_script(rows: list[tuple[Path, str, float]]) -> str:
    """ffmpeg concat demuxer list. The last file is repeated so its duration sticks."""
    lines = []
    for path, _, duration in rows:
        lines.append(_file_line(path))
        lines.append(f"duration {duration}")
    lines.append(_file_line(rows[-1][0]))
    return "\n".join(lines) + "\n"


def total_duration(rows: list[tuple[Path, str, float]]) -> float:
    return sum(duration for _, _, duration in rows)


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

    `audio` is the bed track, False for silence, None for the default bed.
    """
    directory = resolve_post_dir(post_dir)
    manifest = load_manifest(directory)
    rows = slide_files(directory, manifest)
    destination = Path(output) if output else directory / f"{manifest['slug']}.mp4"
    ffmpeg = _ffmpeg()
    duration = total_duration(rows)
    audio_path, audio_meta = resolve_bed(audio)

    concat_path = directory / CONCAT_NAME
    concat_path.write_text(concat_script(rows), encoding="utf-8")
    width, height = CANVAS_SIZE
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
        "-vf",
        f"scale={width}:{height},fps=30,format=yuv420p",
        *_audio_filters(audio_path, duration),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
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
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    finally:
        concat_path.unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = "\n".join(detail[-12:]) if detail else "no ffmpeg output"
        raise VideoError(f"ffmpeg failed for {destination}:\n{tail}")
    _record_audio(directory / "post.json", audio_meta)
    return destination


def resolve_bed(audio: Path | str | bool | None) -> tuple[Path | None, dict | None]:
    """False is silence. None is the catalog default. A slug or a file path otherwise."""
    if audio is False:
        return None, None
    catalog = beds()
    if audio in (None, True):
        slug = load_catalog().get("default")
        if not slug:
            return None, None
        audio = slug
    text = str(audio)
    if text in catalog:
        entry = catalog[text]
        path = AUDIO_DIR / entry["file"]
        if not path.exists():
            raise VideoError(f"Audio file for {text!r} is missing: {path}")
        return path, entry
    path = Path(text)
    if path.exists():
        resolved = path.resolve()
        for entry in catalog.values():
            candidate = AUDIO_DIR / entry["file"]
            if candidate.exists() and candidate.resolve() == resolved:
                return path, entry
        return path, _meta_from_filename(path)
    known = ", ".join(catalog) or "(none)"
    raise VideoError(f"Unknown audio {text!r}. Known beds: {known}")


def _meta_from_filename(path: Path) -> dict:
    stem = path.stem
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return {"title": title, "artist": artist, "file": path.name}
    return {"title": stem, "file": path.name}


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


def _record_audio(manifest_path: Path, meta: dict | None) -> None:
    if not manifest_path.exists():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if meta:
        payload["audio"] = {
            "slug": meta.get("slug"),
            "title": meta.get("title"),
            "artist": meta.get("artist"),
            "license": meta.get("license"),
            "source": meta.get("source"),
            "attribution": (meta.get("attribution") or "").strip() or None,
        }
    else:
        payload["audio"] = None
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _file_line(path: Path) -> str:
    text = str(path.resolve()).replace("'", r"'\''")
    return f"file '{text}'"


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise VideoError("ffmpeg is not on PATH")
    return path

"""Narrated video: slides cut to a voice track instead of fixed holds.

A post's `voiceover.yaml` holds the script (one entry per slide) and either the
recorded tracks with a cue per slide, or TTS settings. Each slide stays up from
just before its line starts until the next slide's line, so the sync comes from
the recording rather than from guessed durations.

Recorded takes need cue times. `suggest_cues` finds them from pauses: it spreads
the take across slides by script word count, then snaps each estimate to the
longest nearby pause. Speakers pause longer between slides than between
sentences, so the estimate only has to land close.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests

from tiktoks.config import CANVAS_SIZE, ROOT
from tiktoks.io import read_yaml
from tiktoks.paths import ensure_dir
from tiktoks.video import _ffmpeg, load_manifest, slide_files

FPS = 30
# Slow push-in per slide, as a fraction of the frame.
ZOOM = 0.035
# Bands quieter than this, for at least this long, count as a pause.
NOISE_DB = -40
MIN_PAUSE = 0.35
# How far from the word-count estimate a pause may be and still be the cut.
WINDOW = 3.0
LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=11"
TTS_URL = "https://api.openai.com/v1/audio/speech"


class VoiceoverError(RuntimeError):
    """The config, the audio or ffmpeg is not usable."""


@dataclass
class Track:
    file: Path
    slides: int
    cues: list[float] = field(default_factory=list)


@dataclass
class Voiceover:
    path: Path
    post_dir: Path
    script: list[str]
    tracks: list[Track]
    lead: float = 0.25
    gap: float = 0.3
    tail: float = 1.0
    tts: dict = field(default_factory=dict)

    @property
    def voice_dir(self) -> Path:
        return self.path.parent / "voice"


def load(path: Path | str) -> Voiceover:
    path = Path(path).resolve()
    data = read_yaml(path)
    tracks = []
    for entry in data.get("tracks") or []:
        cues = [float(c) for c in entry.get("cues") or []]
        tracks.append(
            Track(
                file=path.parent / entry["file"],
                slides=int(entry.get("slides", len(cues))),
                cues=cues,
            )
        )
    return Voiceover(
        path=path,
        post_dir=ROOT / data["post"],
        script=[str(s).strip() for s in data.get("script") or []],
        tracks=tracks,
        lead=float(data.get("lead", 0.25)),
        gap=float(data.get("gap", 0.3)),
        tail=float(data.get("tail", 1.0)),
        tts=data.get("tts") or {},
    )


# Pauses and cues


def parse_silences(log: str) -> list[tuple[float, float]]:
    """(start, end) pairs from ffmpeg silencedetect output."""
    starts = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    return [(max(s, 0.0), e) for s, e in zip(starts, ends, strict=False)]


def detect_pauses(
    audio: Path, *, noise_db: float = NOISE_DB, min_pause: float = MIN_PAUSE
) -> list[tuple[float, float]]:
    result = subprocess.run(
        [
            _ffmpeg(),
            "-hide_banner",
            "-i",
            str(audio),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_pause}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VoiceoverError(f"ffmpeg could not read {audio}")
    return parse_silences(result.stderr)


def speech_span(pauses: list[tuple[float, float]], duration: float) -> tuple[float, float]:
    """When the talking starts and stops, ignoring room tone at either end."""
    start, end = 0.0, duration
    if pauses and pauses[0][0] <= 0.05:
        start = pauses[0][1]
    if pauses and pauses[-1][1] >= duration - 0.05:
        end = pauses[-1][0]
    return start, end


def suggest_cues(
    pauses: list[tuple[float, float]],
    word_counts: list[int],
    span: tuple[float, float],
    *,
    window: float = WINDOW,
) -> list[tuple[float, float, float | None]]:
    """(cue, estimate, pause length) per slide. The first slide always starts at 0.

    Each estimate snaps to the end of the longest pause within `window` seconds, so
    the cut lands where the next line begins. Pause length is None when nothing was
    close and the estimate stands.
    """
    start, end = span
    total = sum(word_counts) or 1
    results: list[tuple[float, float, float | None]] = [(0.0, start, None)]
    done = word_counts[0] if word_counts else 0
    previous = 0.0
    for count in word_counts[1:]:
        estimate = start + (end - start) * done / total
        done += count
        nearby = [
            (e - s, e)
            for s, e in pauses
            if abs(e - estimate) <= window and e > previous and start < e < end
        ]
        if nearby:
            length, cue = max(nearby)
            results.append((round(cue, 2), round(estimate, 2), round(length, 2)))
        else:
            cue = estimate
            results.append((round(cue, 2), round(estimate, 2), None))
        previous = cue
    return results


# Timeline


def slide_windows(
    tracks: list[tuple[list[float], float]], *, lead: float, gap: float, tail: float
) -> list[tuple[float, float]]:
    """(start, end) on the joined timeline for every slide, given each track's cues and
    duration. A slide comes up `lead` seconds before its line and holds until the next
    slide; the last one holds `tail` seconds past the end of the audio."""
    starts: list[float] = []
    offset = 0.0
    for cues, duration in tracks:
        for index, cue in enumerate(cues):
            at = offset + cue
            starts.append(offset if index == 0 and cue <= lead else max(offset, at - lead))
        offset += duration + gap
    end = offset - gap + tail
    bounds = starts + [end]
    return [(bounds[i], bounds[i + 1]) for i in range(len(starts))]


def frame_counts(windows: list[tuple[float, float]], fps: int = FPS) -> list[int]:
    """Frames per slide, rounded on absolute times so error never accumulates."""
    return [round(end * fps) - round(start * fps) for start, end in windows]


# Build


def build(config_path: Path | str, *, tts: bool = False, voice: str | None = None) -> Path:
    """Write `{slug}.mp4` into the post directory and record the voiceover in post.json."""
    config = load(config_path)
    manifest = load_manifest(config.post_dir)
    slides = [path for path, _, _ in slide_files(config.post_dir, manifest)]

    tracks = synthesize(config, voice=voice) if tts else config.tracks
    _validate(tracks, len(slides))
    durations = [audio_duration(track.file) for track in tracks]
    windows = slide_windows(
        [(track.cues, d) for track, d in zip(tracks, durations, strict=True)],
        lead=config.lead,
        gap=config.gap,
        tail=config.tail,
    )

    work = ensure_dir(config.post_dir / ".voiceover")
    voice_mix = _mix(tracks, config, work / "voice.wav")
    segments = []
    for index, (png, frames) in enumerate(zip(slides, frame_counts(windows), strict=True)):
        segment = work / f"slide-{index + 1:02d}.mp4"
        _segment(png, frames, segment)
        segments.append(segment)

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    destination = config.post_dir / f"{manifest['slug']}.mp4"
    _run(
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-i",
        str(voice_mix),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(destination),
    )
    _record(config, tracks, windows, destination, source="tts" if tts else "recorded")
    return destination


def synthesize(config: Voiceover, *, voice: str | None = None) -> list[Track]:
    """One TTS clip per script entry, cached by text and settings."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise VoiceoverError("Set OPENAI_API_KEY to use --tts.")
    if not config.script:
        raise VoiceoverError(f"No script in {config.path}")
    settings = {
        "model": config.tts.get("model", "gpt-4o-mini-tts"),
        "voice": voice or config.tts.get("voice", "marin"),
        "instructions": config.tts.get("style", ""),
        "response_format": "wav",
    }
    say = config.tts.get("say") or {}
    out = ensure_dir(config.voice_dir / "tts")
    tracks = []
    for index, text in enumerate(config.script, start=1):
        spoken = text
        for pattern, replacement in say.items():
            spoken = re.sub(pattern, replacement, spoken)
        digest = hashlib.sha1(json.dumps([settings, spoken]).encode()).hexdigest()[:10]
        path = out / f"slide-{index:02d}-{digest}.wav"
        if not path.exists():
            response = requests.post(
                TTS_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={**settings, "input": spoken},
                timeout=120,
            )
            if response.status_code == 401:
                raise VoiceoverError("OpenAI rejected the API key (401).")
            response.raise_for_status()
            path.write_bytes(response.content)
        tracks.append(Track(file=path, slides=1, cues=[0.0]))
    return tracks


def _validate(tracks: list[Track], slide_count: int) -> None:
    if not tracks:
        raise VoiceoverError("No tracks. Add recordings to voiceover.yaml or pass --tts.")
    for track in tracks:
        if not track.file.exists():
            raise VoiceoverError(f"Missing audio: {track.file}")
        if len(track.cues) != track.slides:
            raise VoiceoverError(
                f"{track.file.name} covers {track.slides} slides but has {len(track.cues)} "
                "cues. Run `tiktoks voiceover cues` to find them."
            )
        if track.cues != sorted(track.cues):
            raise VoiceoverError(f"Cues for {track.file.name} are out of order.")
    cues = sum(len(track.cues) for track in tracks)
    if cues != slide_count:
        raise VoiceoverError(f"{cues} cues for {slide_count} slides.")


def _mix(tracks: list[Track], config: Voiceover, path: Path) -> Path:
    """Join the takes with a short gap, pad the tail and match loudness for phones."""
    inputs = [arg for track in tracks for arg in ("-i", str(track.file))]
    count = len(tracks)
    chain = "".join(
        f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono,"
        f"apad=pad_dur={config.gap if i < count - 1 else config.tail}[a{i}];"
        for i in range(count)
    )
    chain += "".join(f"[a{i}]" for i in range(count))
    chain += f"concat=n={count}:v=0:a=1,highpass=f=80,{LOUDNESS}[out]"
    _run(*inputs, "-filter_complex", chain, "-map", "[out]", "-ar", "48000", str(path))
    return path


def _segment(png: Path, frames: int, path: Path) -> None:
    width, height = CANVAS_SIZE
    zoom = f"1+{ZOOM}*on/{max(frames, 1)}"
    _run(
        "-loop",
        "1",
        "-i",
        str(png),
        "-filter_complex",
        f"scale={width * 2}:{height * 2},zoompan=z='{zoom}':x='iw/2-iw/zoom/2'"
        f":y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={FPS},format=yuv420p",
        "-frames:v",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-r",
        str(FPS),
        str(path),
    )


def _record(
    config: Voiceover,
    tracks: list[Track],
    windows: list[tuple[float, float]],
    video: Path,
    *,
    source: str,
) -> None:
    """Narration is the post's own audio, so there is no music bed to license."""
    manifest_path = config.post_dir / "post.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["video_sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
    payload["audio"] = None
    payload["voiceover"] = {
        "config": str(config.path.relative_to(ROOT)),
        "source": source,
        "tracks": [
            {
                "file": track.file.name,
                "sha256": hashlib.sha256(track.file.read_bytes()).hexdigest()[:16],
                "cues": track.cues,
            }
            for track in tracks
        ],
        "slides": [[round(start, 2), round(end, 2)] for start, end in windows],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VoiceoverError(f"ffprobe could not read {path}")
    return float(json.loads(result.stdout)["format"]["duration"])


def _run(*args: str) -> None:
    result = subprocess.run(
        [_ffmpeg(), "-y", "-v", "error", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-12:])
        raise VoiceoverError(f"ffmpeg failed:\n{tail}")

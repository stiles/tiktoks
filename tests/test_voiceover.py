"""Voiceover timing: pauses, cue suggestions and the slide timeline."""

from pathlib import Path

import pytest

from tiktoks.voiceover import (
    Track,
    VoiceoverError,
    _validate,
    frame_counts,
    parse_silences,
    slide_windows,
    speech_span,
    suggest_cues,
)

LOG = """
[silencedetect @ 0x1] silence_start: -0.01
[silencedetect @ 0x1] silence_end: 0.4 | silence_duration: 0.41
[silencedetect @ 0x1] silence_start: 9.2
[silencedetect @ 0x1] silence_end: 10.2 | silence_duration: 1.0
[silencedetect @ 0x1] silence_start: 13.0
[silencedetect @ 0x1] silence_end: 13.4 | silence_duration: 0.4
[silencedetect @ 0x1] silence_start: 19.5
[silencedetect @ 0x1] silence_end: 20.0 | silence_duration: 0.5
"""


def test_parse_silences_pairs_starts_and_ends():
    assert parse_silences(LOG) == [(0.0, 0.4), (9.2, 10.2), (13.0, 13.4), (19.5, 20.0)]


def test_speech_span_trims_room_tone_at_both_ends():
    pauses = parse_silences(LOG)
    assert speech_span(pauses, duration=20.0) == (0.4, 19.5)
    assert speech_span(pauses[1:3], duration=20.0) == (0.0, 20.0)


def test_cues_snap_to_the_longest_nearby_pause():
    pauses = parse_silences(LOG)
    # Two slides with equal words split the take near 10s; the 1s pause beats the
    # shorter one at 13.4s.
    rows = suggest_cues(pauses, [20, 20], (0.4, 19.5))
    assert [cue for cue, _, _ in rows] == [0.0, 10.2]
    assert rows[1][2] == 1.0


def test_cues_fall_back_to_the_estimate_without_a_pause():
    rows = suggest_cues([], [10, 30], (0.0, 40.0))
    assert rows[1] == (10.0, 10.0, None)


def test_cues_never_go_backwards():
    pauses = [(4.0, 5.0)]
    rows = suggest_cues(pauses, [10, 1, 10], (0.0, 20.0), window=6.0)
    cues = [cue for cue, _, _ in rows]
    assert cues == sorted(cues)
    assert cues.count(5.0) == 1


def test_windows_lead_each_line_and_hold_the_tail():
    windows = slide_windows([([0.0, 10.0], 20.0), ([0.0], 5.0)], lead=0.25, gap=0.3, tail=1.0)
    assert windows == [(0.0, 9.75), (9.75, 20.3), (20.3, 26.3)]


def test_frame_counts_do_not_drift():
    windows = [(0.0, 1.016), (1.016, 2.033), (2.033, 3.05)]
    frames = frame_counts(windows, fps=30)
    assert sum(frames) == round(3.05 * 30)


def test_validate_checks_cues_against_slides(tmp_path: Path):
    audio = tmp_path / "take.m4a"
    audio.write_bytes(b"")
    with pytest.raises(VoiceoverError, match="has 1 cues"):
        _validate([Track(file=audio, slides=2, cues=[0.0])], slide_count=2)
    with pytest.raises(VoiceoverError, match="3 cues for 2 slides"):
        _validate([Track(file=audio, slides=3, cues=[0.0, 1.0, 2.0])], slide_count=2)
    with pytest.raises(VoiceoverError, match="out of order"):
        _validate([Track(file=audio, slides=2, cues=[5.0, 1.0])], slide_count=2)
    _validate([Track(file=audio, slides=2, cues=[0.0, 1.0])], slide_count=2)

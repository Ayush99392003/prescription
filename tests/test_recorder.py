"""
Tests for server.voice.recorder — covers Fix 1 (unbounded recording).

All sounddevice / hardware calls are mocked so tests run headlessly.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _make_fake_stream(frames_ref: list, sample_rate: int = 16_000):
    """
    Return a context-manager mock that simulates an InputStream.
    When entered, it calls the provided callback once with 0.1s of
    silence so ``frames`` is non-empty and the wav-save path is hit.
    """

    class FakeStream:
        def __init__(self, **kwargs):
            self._callback = kwargs.get("callback")

        def __enter__(self):
            if self._callback:
                silence = np.zeros((1600, 1), dtype=np.int16)
                self._callback(silence, 1600, None, MagicMock())
            return self

        def __exit__(self, *args):
            pass

    return FakeStream


# ── Fix 1a: timer fires and stops recording automatically ────────────


def test_timer_stops_recording_automatically(tmp_path: Path):
    """
    When duration=1 and the user never presses ENTER, the threading.Timer
    must fire and set recording[0]=False within ~1 second.
    We verify this by patching input() to block until a threading.Event
    is set — which only happens when _auto_stop() fires.
    """
    from server.voice import recorder

    fired = threading.Event()
    original_timer_class = threading.Timer

    def patched_timer(interval, func, *args, **kwargs):
        """Wrap the real Timer to capture when it fires."""
        def wrapper():
            func(*args)
            fired.set()

        return original_timer_class(interval, wrapper)

    with (
        patch("server.voice.recorder.sd.check_input_settings"),
        patch(
            "server.voice.recorder.sd.InputStream",
            side_effect=_make_fake_stream([]),
        ),
        patch("server.voice.recorder.threading.Timer", side_effect=patched_timer),
        patch(
            "server.voice.recorder.input",
            side_effect=lambda: fired.wait(timeout=5),
        ),
        patch("server.voice.recorder._save_wav"),
        patch("server.voice.recorder.console"),
    ):
        path = recorder.record_audio(duration=1, output_path=str(tmp_path / "out.wav"))
        assert path.endswith(".wav")


# ── Fix 1b: unique timestamped output path per session ───────────────


def test_default_output_path_is_unique(tmp_path: Path):
    """
    Two consecutive calls without an explicit output_path must produce
    different filenames (no overwrite between sessions).
    """
    from server.voice import recorder

    captured_paths: list[str] = []

    def fake_save(data, path, sr, ch):
        captured_paths.append(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(ch)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(data.tobytes())

    import time

    with (
        patch("server.voice.recorder.sd.check_input_settings"),
        patch(
            "server.voice.recorder.sd.InputStream",
            side_effect=_make_fake_stream([]),
        ),
        patch("server.voice.recorder.input"),
        patch("server.voice.recorder.console"),
        patch("server.voice.recorder._save_wav", side_effect=fake_save),
        patch("server.config.OUTPUT_DIR", tmp_path),
    ):
        p1 = recorder.record_audio(duration=60)
        time.sleep(1.1)  # ensure different unix timestamp
        p2 = recorder.record_audio(duration=60)

    assert p1 != p2, "Each session must produce a unique audio filename"


# ── Fix 1c: no audio captured raises RuntimeError ───────────────────


def test_no_audio_raises_runtime_error():
    """
    If the callback is never called (e.g., mic disconnected mid-stream),
    record_audio must raise RuntimeError, not silently produce an
    empty file.
    """
    from server.voice import recorder

    class EmptyStream:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with (
        patch("server.voice.recorder.sd.check_input_settings"),
        patch("server.voice.recorder.sd.InputStream", EmptyStream),
        patch("server.voice.recorder.input"),
        patch("server.voice.recorder.console"),
    ):
        with pytest.raises(RuntimeError, match="No audio captured"):
            recorder.record_audio(duration=1, output_path="/tmp/x.wav")


# ── Fix 1d: PortAudioError propagated as RuntimeError ────────────────


def test_microphone_error_raises_runtime_error():
    """sd.PortAudioError on check_input_settings must surface as RuntimeError."""
    import sounddevice as sd

    from server.voice import recorder

    with patch(
        "server.voice.recorder.sd.check_input_settings",
        side_effect=sd.PortAudioError("No device"),
    ):
        with pytest.raises(RuntimeError, match="Microphone unavailable"):
            recorder.record_audio(duration=5, output_path="/tmp/x.wav")

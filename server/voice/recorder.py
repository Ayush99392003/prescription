"""
Microphone audio recorder using sounddevice.
Records to a WAV file at 16kHz mono — Whisper's native format.
"""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from rich.console import Console
from rich.panel import Panel

from server import config

console = Console()


def record_audio(
    duration: int = config.AUDIO_MAX_SECONDS,
    output_path: Optional[str] = None,
) -> str:
    """
    Record audio from the default microphone and save to WAV.

    Stops automatically after `duration` seconds OR when the user
    presses ENTER — whichever comes first.  This prevents unbounded
    memory growth when the mic is left running unattended.

    Args:
        duration: Hard upper bound on recording length in seconds.
        output_path: Path to save the WAV file.  Defaults to a
                     unique timestamped file inside server/output/.

    Returns:
        Absolute path string to the saved WAV file.

    Raises:
        RuntimeError: If no microphone is found or capture fails.
    """
    if output_path is None:
        ts = int(time.time())
        output_path = str(
            config.OUTPUT_DIR / f"audio_{ts}.wav"
        )

    sample_rate = config.AUDIO_SAMPLE_RATE
    channels = config.AUDIO_CHANNELS

    try:
        sd.check_input_settings(
            samplerate=sample_rate,
            channels=channels,
        )
    except sd.PortAudioError as exc:
        raise RuntimeError(
            f"Microphone unavailable: {exc}. "
            "Check that a mic is connected and not in use."
        ) from exc

    frames: list[np.ndarray] = []
    recording = [True]
    stop_event = threading.Event()

    def _callback(
        indata: np.ndarray,
        frame_count: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if recording[0]:
            frames.append(indata.copy())

    def _auto_stop() -> None:
        """Timer callback: stop recording after `duration` secs."""
        recording[0] = False
        stop_event.set()
        console.print(
            f"\n[yellow]⏱  Max duration ({duration}s) reached "
            "— recording stopped automatically.[/yellow]"
        )

    timer = threading.Timer(duration, _auto_stop)

    console.print(
        Panel(
            "[bold green]🎙  Recording started[/bold green]\n"
            f"Speak clearly. Press [bold yellow]ENTER[/bold yellow]"
            f" to stop (max {duration}s).",
            title="Voice Capture",
            border_style="green",
        )
    )

    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        callback=_callback,
    ):
        timer.start()
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            timer.cancel()
            recording[0] = False

    if not frames:
        raise RuntimeError(
            "No audio captured. Is the microphone working?"
        )

    audio_data = np.concatenate(frames, axis=0)
    _save_wav(audio_data, output_path, sample_rate, channels)
    console.print(
        f"[dim]Audio saved → {output_path}[/dim]"
    )
    return output_path


def _save_wav(
    data: np.ndarray,
    path: str,
    sample_rate: int,
    channels: int,
) -> None:
    """Write numpy int16 audio array to a WAV file with peak normalization."""
    # Peak normalization to improve volume clarity for STT
    max_val = np.max(np.abs(data)) if data.size > 0 else 0
    if max_val > 0:
        target_peak = 29490  # ~90% of max int16 (32767)
        scaling_factor = target_peak / max_val
        data = np.clip(data * scaling_factor, -32768, 32767).astype(np.int16)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)   # int16 = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

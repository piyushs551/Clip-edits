"""Loud-moment detection (audio energy peaks). Offline, numpy only."""
from __future__ import annotations

import subprocess

import numpy as np

from .commands import build_audio_pcm_cmd
from .util import BadFileError, FFmpegFailed, require_ffmpeg

SAMPLE_RATE = 8000
WINDOW_MS = 50


def window_energy(samples: np.ndarray, sample_rate: int = SAMPLE_RATE,
                  window_ms: int = WINDOW_MS) -> tuple[np.ndarray, float]:
    """Mean-square energy per window. Returns (energy array, window seconds)."""
    n = max(1, int(sample_rate * window_ms / 1000))
    k = len(samples) // n
    if k == 0:
        return np.zeros(0, dtype=np.float64), n / sample_rate
    x = samples[: k * n].astype(np.float64) / 32768.0
    return (x.reshape(k, n) ** 2).mean(axis=1), n / sample_rate


def find_peaks(energy: np.ndarray, window_s: float, percentile: float = 95.0,
               min_gap_s: float = 4.0, max_peaks: int | None = 30) -> list[dict]:
    """Windows above the percentile threshold, strongest first, >= min_gap_s apart.

    Returns [{"time": seconds, "energy": value}] sorted by time.
    max_peaks keeps only the strongest N (None = no limit).
    """
    if len(energy) == 0:
        return []
    thr = np.percentile(energy, percentile)
    cand = np.flatnonzero(energy > thr)
    if len(cand) == 0:
        return []
    order = cand[np.argsort(-energy[cand], kind="stable")]
    min_gap_w = min_gap_s / window_s
    chosen: list[int] = []
    for idx in order:
        if all(abs(idx - c) >= min_gap_w for c in chosen):
            chosen.append(int(idx))
            if max_peaks is not None and len(chosen) >= max_peaks:
                break
    chosen.sort()
    peak = float(energy.max()) or 1.0
    return [{"time": round(i * window_s + window_s / 2, 3),
             "energy": round(float(energy[i]) / peak, 4)} for i in chosen]


def decode_audio(src: str) -> np.ndarray:
    require_ffmpeg()
    res = subprocess.run(build_audio_pcm_cmd(src, SAMPLE_RATE), capture_output=True)
    if res.returncode != 0:
        msg = res.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["unknown"]
        raise FFmpegFailed(f"Couldn't read the audio track: {msg[0]}")
    if not res.stdout:
        raise BadFileError("This video has no audio track, so there are no loud moments to find.")
    return np.frombuffer(res.stdout, dtype=np.int16)


def suggest_moments(src: str, max_peaks: int = 30) -> list[dict]:
    samples = decode_audio(src)
    energy, win = window_energy(samples)
    return find_peaks(energy, win, max_peaks=max_peaks)

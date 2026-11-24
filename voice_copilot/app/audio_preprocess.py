import io
import math
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def preprocess_audio_bytes(
    audio_bytes: bytes,
    target_sr: int = 16000,
    silence_peak_rms_threshold: float = 0.005,
    target_rms: float = 0.1,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Preprocess raw audio WAV bytes for Gipformer ASR.

    Pipeline:
    1. Decode audio & mix down to mono float32.
    2. Resample to 16 kHz via polyphase filtering.
    3. Remove DC offset.
    4. Energy-based VAD / silence trimming with 120ms boundary padding.
       Flags silent clips so Gipformer does not hallucinate filler syllables.
    5. RMS & peak normalization for stable Fbank extraction.
    """
    samples, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = np.ascontiguousarray(samples, dtype=np.float32)

    if len(samples) == 0:
        return samples, {
            "duration_s": 0.0,
            "trimmed_duration_s": 0.0,
            "peak_rms": 0.0,
            "is_silent": True,
        }

    if int(sample_rate) != target_sr:
        divisor = math.gcd(target_sr, int(sample_rate))
        up = target_sr // divisor
        down = int(sample_rate) // divisor
        samples = resample_poly(samples, up, down).astype(np.float32)

    duration_s = round(len(samples) / target_sr, 3)

    # Remove DC offset
    samples = samples - float(np.mean(samples))

    # Frame-based energy VAD (20ms window, 10ms hop)
    frame_len = int(0.020 * target_sr)  # 320
    hop_len = int(0.010 * target_sr)    # 160

    if len(samples) < frame_len:
        peak_rms = float(np.sqrt(np.mean(samples ** 2)))
        is_silent = peak_rms < silence_peak_rms_threshold
        return samples, {
            "duration_s": duration_s,
            "trimmed_duration_s": 0.0 if is_silent else duration_s,
            "peak_rms": round(peak_rms, 5),
            "is_silent": is_silent,
        }

    num_frames = 1 + (len(samples) - frame_len) // hop_len
    frame_rms = np.empty(num_frames, dtype=np.float32)
    for idx in range(num_frames):
        start = idx * hop_len
        frame = samples[start : start + frame_len]
        frame_rms[idx] = float(np.sqrt(np.mean(frame * frame)))

    peak_rms = float(np.max(frame_rms))
    if peak_rms < silence_peak_rms_threshold:
        return np.zeros(0, dtype=np.float32), {
            "duration_s": duration_s,
            "trimmed_duration_s": 0.0,
            "peak_rms": round(peak_rms, 5),
            "is_silent": True,
        }

    vad_thresh = max(0.008, 0.05 * peak_rms)
    active = np.where(frame_rms >= vad_thresh)[0]
    if len(active) == 0:
        return np.zeros(0, dtype=np.float32), {
            "duration_s": duration_s,
            "trimmed_duration_s": 0.0,
            "peak_rms": round(peak_rms, 5),
            "is_silent": True,
        }

    pad_samples = int(0.120 * target_sr)  # 120ms padding on each side
    start_sample = max(0, int(active[0]) * hop_len - pad_samples)
    end_sample = min(len(samples), int(active[-1]) * hop_len + frame_len + pad_samples)
    trimmed = samples[start_sample:end_sample]
    trimmed_duration_s = round(len(trimmed) / target_sr, 3)

    # RMS normalization with peak protection (<= 0.9)
    speech_rms = float(np.sqrt(np.mean(trimmed ** 2)))
    if speech_rms > 1e-6:
        gain = target_rms / speech_rms
        max_abs = float(np.max(np.abs(trimmed)))
        if max_abs * gain > 0.9:
            gain = 0.9 / max_abs
        trimmed = np.clip(trimmed * gain, -1.0, 1.0).astype(np.float32)

    return np.ascontiguousarray(trimmed, dtype=np.float32), {
        "duration_s": duration_s,
        "trimmed_duration_s": trimmed_duration_s,
        "peak_rms": round(peak_rms, 5),
        "is_silent": False,
    }

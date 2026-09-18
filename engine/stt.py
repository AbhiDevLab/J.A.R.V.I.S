"""J.A.R.V.I.S. multilingual speech-to-text and language detection.

Phase 5:
- Local faster-whisper transcription with automatic language detection.
- English (en) and Hindi (hi) are the supported assistant languages.
- Google Web Speech remains an optional fallback if local STT is unavailable.
"""

from __future__ import annotations

import io
import os
from typing import Tuple

import speech_recognition as sr

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception:
    WhisperModel = None

_MODEL = None


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_model():
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed.")

    model_name = os.getenv("JARVIS_STT_MODEL", "small").strip()
    configured_device = os.getenv("JARVIS_STT_DEVICE", "auto").strip().lower()
    configured_compute = os.getenv("JARVIS_STT_COMPUTE_TYPE", "auto").strip().lower()

    if configured_device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    else:
        device = configured_device

    if configured_compute == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    else:
        compute_type = configured_compute

    print(
        "Loading speech recognition model: "
        f"{model_name} (device={device}, compute_type={compute_type})"
    )

    try:
        _MODEL = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
    except Exception:
        if device == "cuda":
            print("CUDA STT initialization failed; falling back to CPU.")
            _MODEL = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
            )
        else:
            raise

    return _MODEL


def _transcribe_local(audio_data: sr.AudioData) -> Tuple[str, str, float]:
    model = _get_model()

    wav_bytes = audio_data.get_wav_data()
    audio_stream = io.BytesIO(wav_bytes)
    audio_stream.seek(0)

    try:
        beam_size = int(os.getenv("JARVIS_STT_BEAM_SIZE", "5"))
    except Exception:
        beam_size = 5

    try:
        language_detection_segments = int(
            os.getenv("JARVIS_STT_LANGUAGE_DETECTION_SEGMENTS", "2")
        )
    except Exception:
        language_detection_segments = 2

    segments, info = model.transcribe(
        audio_stream,
        language=None,
        task="transcribe",
        beam_size=beam_size,
        vad_filter=True,
        condition_on_previous_text=False,
        language_detection_segments=language_detection_segments,
        language_detection_threshold=0.5,
    )

    text = " ".join(
        segment.text.strip()
        for segment in segments
        if segment.text and segment.text.strip()
    ).strip()

    language = str(getattr(info, "language", "")).lower()
    try:
        probability = float(getattr(info, "language_probability", 0.0))
    except Exception:
        probability = 0.0

    return text, language, probability


def _transcribe_google_fallback(audio_data: sr.AudioData) -> Tuple[str, str, float]:
    recognizer = sr.Recognizer()

    for language_code, language_name in (("en-IN", "en"), ("hi-IN", "hi")):
        try:
            text = recognizer.recognize_google(
                audio_data,
                language=language_code,
            ).strip()
            if text:
                return text, language_name, 0.0
        except (sr.UnknownValueError, sr.RequestError):
            continue

    return "", "", 0.0


def transcribe_audio(audio_data: sr.AudioData) -> Tuple[str, str, float]:
    """Return (transcript, detected_language, language_probability)."""
    if _env_flag("JARVIS_STT_ENABLED", True):
        try:
            text, language, confidence = _transcribe_local(audio_data)
            if text:
                print(
                    f"Detected language: {language} "
                    f"(confidence={confidence:.2f})"
                )
                print(f"Transcript: {text}")
                return text, language, confidence
            print("Local STT returned no transcript.")
        except Exception as e:
            print("Local STT unavailable:", e)

    if _env_flag("JARVIS_STT_FALLBACK_GOOGLE", True):
        result = _transcribe_google_fallback(audio_data)
        if result[0]:
            print(
                "Google STT fallback used. "
                f"Detected language: {result[1]}"
            )
            print(f"Transcript: {result[0]}")
        return result

    return "", "", 0.0


def detect_text_language(text: str) -> str:
    """Choose a language for typed input: Devanagari -> Hindi, otherwise English."""
    if any("\u0900" <= char <= "\u097F" for char in text):
        return "hi"
    return "en"

"""J.A.R.V.I.S. multilingual speech-to-text and language detection.

Phase 5:
- Local faster-whisper transcription with automatic language detection.
- English and Hindi remain fully supported, while low-confidence Whisper language misclassifications are corrected from transcript evidence before command handling.
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


# Common English function words are used only as a fallback signal when
# Whisper's language classifier is uncertain. This does not replace Whisper;
# it prevents a low-confidence misclassification from discarding a good
# transcript such as "How are you feeling now?".
_ENGLISH_HINT_WORDS = {
    "a",
    "about",
    "after",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "get",
    "go",
    "have",
    "he",
    "hello",
    "help",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "need",
    "now",
    "of",
    "on",
    "open",
    "or",
    "please",
    "play",
    "put",
    "show",
    "start",
    "tell",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}

_HINDI_RANGES = (
    ("\u0900", "\u097F"),  # Devanagari
)


def _contains_script(
    text: str,
    start: str,
    end: str,
) -> bool:
    return any(
        start <= char <= end
        for char in str(text or "")
    )


def _looks_like_hindi(
    text: str,
) -> bool:
    return _contains_script(
        text,
        "\u0900",
        "\u097F",
    )


def _english_hint_score(
    text: str,
) -> int:
    words = {
        word
        for word in (
            str(text or "")
            .lower()
            .replace("'", " ")
            .split()
        )
        if word.isalpha()
    }

    return len(
        words.intersection(
            _ENGLISH_HINT_WORDS
        )
    )


def _normalize_detected_language(
    text: str,
    language: str,
    confidence: float,
) -> str:
    """
    Keep Whisper's language result when it is reliable, but recover from
    low-confidence misclassifications using the transcript itself.

    This is intentionally conservative:
    - explicit Hindi script -> hi
    - English function-word evidence -> en
    - otherwise preserve Whisper's detected language
    """
    detected = str(
        language or ""
    ).strip().lower()

    try:
        threshold = float(
            os.getenv(
                "JARVIS_STT_LANGUAGE_CONFIDENCE_THRESHOLD",
                "0.75",
            )
        )
    except Exception:
        threshold = 0.75

    if detected in {"en", "hi"}:
        return detected

    # Only reinterpret an unsupported language when Whisper itself is
    # uncertain. Stronger classifications are preserved.
    if confidence >= threshold:
        return detected

    if _looks_like_hindi(text):
        return "hi"

    if _english_hint_score(text) >= 2:
        return "en"

    return detected


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

    language = str(
        getattr(
            info,
            "language",
            "",
        )
    ).lower()

    try:
        probability = float(
            getattr(
                info,
                "language_probability",
                0.0,
            )
        )
    except Exception:
        probability = 0.0

    normalized_language = _normalize_detected_language(
        text,
        language,
        probability,
    )

    if (
        normalized_language != language
        and text
    ):
        print(
            "Language detection corrected from "
            f"{language or 'unknown'} to "
            f"{normalized_language} "
            f"(Whisper confidence={probability:.2f})"
        )

    return (
        text,
        normalized_language,
        probability,
    )


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

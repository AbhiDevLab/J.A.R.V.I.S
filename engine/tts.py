"""J.A.R.V.I.S. neural TTS with interruptible playback and SAPI5 fallback."""

from __future__ import annotations

import os
import re
import tempfile
import time
import uuid
from html import unescape
from pathlib import Path
from threading import Lock

import pyttsx3

try:
    import soundfile as sf  # type: ignore
except Exception:
    sf = None

try:
    from kokoro import KPipeline  # type: ignore
except Exception:
    KPipeline = None

try:
    import espeakng_loader  # type: ignore

    espeakng_loader.make_library_available()
except Exception:
    espeakng_loader = None

try:
    import pygame  # type: ignore
except Exception:
    pygame = None

_mixer_lock = Lock()
_mixer_initialized = False

_kokoro_lock = Lock()
_kokoro_pipelines = {}


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097F" for char in text)

def _prepare_speech_text(text: str) -> str:
    """
    Convert Markdown, HTML, and technical formatting into natural speech.

    The frontend keeps the original Markdown response for rich rendering.
    TTS receives a cleaned, speech-friendly representation.
    """
    if not text:
        return ""

    spoken = str(text)

    # Decode HTML entities such as &amp;, &lt;, &gt;, etc.
    spoken = unescape(spoken)

    # Replace fenced code blocks with a short spoken cue.
    # The actual code remains visible in the frontend.
    spoken = re.sub(
        r"```[\w+-]*\s*[\s\S]*?```",
        " I've included a code example in the response. ",
        spoken,
    )

    # Convert Markdown images to their alt text.
    spoken = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        r"\1",
        spoken,
    )

    # Convert Markdown links to their visible text.
    spoken = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        spoken,
    )

    # Remove Markdown heading markers.
    spoken = re.sub(
        r"^\s{0,3}#{1,6}\s*",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Remove blockquote markers.
    spoken = re.sub(
        r"^\s*>\s?",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Remove unordered-list markers.
    spoken = re.sub(
        r"^\s*[-*+]\s+",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Remove numbered-list markers.
    spoken = re.sub(
        r"^\s*\d+[.)]\s+",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Remove horizontal-rule-only lines.
    spoken = re.sub(
        r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Remove Markdown emphasis markers.
    spoken = spoken.replace("**", "")
    spoken = spoken.replace("__", "")
    spoken = spoken.replace("~~", "")

    # Remove inline-code markers while keeping their contents.
    spoken = spoken.replace("`", "")

    # Convert common technical symbols into natural spoken equivalents.
    spoken = spoken.replace("→", " to ")
    spoken = spoken.replace("⇒", " implies ")
    spoken = spoken.replace("↔", " is equivalent to ")
    spoken = spoken.replace("←", " from ")
    spoken = spoken.replace("≤", " less than or equal to ")
    spoken = spoken.replace("≥", " greater than or equal to ")
    spoken = spoken.replace("≠", " not equal to ")
    spoken = spoken.replace("≈", " approximately ")
    spoken = spoken.replace("×", " times ")
    spoken = spoken.replace("÷", " divided by ")
    spoken = spoken.replace("•", " ")

    # Remove Markdown table separator rows.
    spoken = re.sub(
        r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$",
        "",
        spoken,
        flags=re.MULTILINE,
    )

    # Turn remaining table separators into natural pauses.
    spoken = spoken.replace("|", ". ")

    # Remove simple HTML tags.
    spoken = re.sub(
        r"<[^>]+>",
        " ",
        spoken,
    )

    # Unescape escaped Markdown punctuation.
    spoken = re.sub(
        r"\\([\\`*_\[\]{}()#+.!>|~\-])",
        r"\1",
        spoken,
    )

    # Normalize whitespace within lines.
    spoken = re.sub(
        r"[ \t]+",
        " ",
        spoken,
    )

    # Prevent excessive blank lines from creating awkward pauses.
    spoken = re.sub(
        r"\n{3,}",
        "\n\n",
        spoken,
    )

    return spoken.strip()

def _select_kokoro_voice(
    text: str,
    language: str | None = None,
) -> tuple[str, str]:
    """Return the Kokoro language code and configured voice."""
    detected = (language or "").strip().lower()
    configured = os.getenv(
        "JARVIS_TTS_LANGUAGE",
        "auto",
    ).strip().lower()

    def _english_voice():
        voice = os.getenv(
            "JARVIS_TTS_EN_VOICE",
            "am_michael",
        )
        # Kokoro's b language pipeline is used by British voices.
        language_code = "b" if voice.lower().startswith(("bm_", "bf_")) else "a"
        return language_code, voice

    if detected in {"hi", "hi-in", "hindi"}:
        return (
            "h",
            os.getenv(
                "JARVIS_TTS_HI_VOICE",
                "hm_omega",
            ),
        )

    if detected in {"en", "en-in", "en-us", "english"}:
        return _english_voice()

    if configured in {"hi", "hi-in", "hindi"}:
        return (
            "h",
            os.getenv(
                "JARVIS_TTS_HI_VOICE",
                "hm_omega",
            ),
        )

    if configured in {"en", "en-in", "en-us", "english"}:
        return _english_voice()

    if _contains_devanagari(text):
        return (
            "h",
            os.getenv(
                "JARVIS_TTS_HI_VOICE",
                "hm_omega",
            ),
        )

    return _english_voice()

def _safe_unlink(path: Path) -> None:
    for _ in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except Exception:
            time.sleep(0.05)


def _ensure_mixer() -> None:
    global _mixer_initialized
    with _mixer_lock:
        if _mixer_initialized:
            return
        if pygame is None:
            raise RuntimeError("pygame is not installed.")
        pygame.mixer.init()
        _mixer_initialized = True


def _get_kokoro_pipeline(language_code: str):
    if KPipeline is None:
        raise RuntimeError("Kokoro is not installed.")

    with _kokoro_lock:
        pipeline = _kokoro_pipelines.get(language_code)

        if pipeline is None:
            print(
                "Loading Kokoro TTS pipeline "
                f"for language '{language_code}'..."
            )

            pipeline = KPipeline(
                lang_code=language_code
            )

            _kokoro_pipelines[language_code] = pipeline

            print("Kokoro TTS pipeline ready.")

        return pipeline


def _synthesize_kokoro(
    text: str,
    language_code: str,
    voice: str,
    output_path: Path,
) -> None:
    if sf is None:
        raise RuntimeError("soundfile is not installed.")

    pipeline = _get_kokoro_pipeline(language_code)

    speed = float(
        os.getenv(
            "JARVIS_KOKORO_SPEED",
            "1.0",
        )
    )

    split_pattern = r"\n+"
    if _env_flag("JARVIS_TTS_SENTENCE_PAUSES", True):
        # Give Kokoro a short natural boundary between sentences. This keeps
        # the voice measured without adding a second TTS engine.
        text = re.sub(r"(?<=[.!?])\s+(?=[A-Z0-9])", "\n", text)
        split_pattern = r"\n+"

    generator = pipeline(
        text,
        voice=voice,
        speed=speed,
        split_pattern=split_pattern,
    )

    wrote_audio = False

    with sf.SoundFile(
        str(output_path),
        mode="w",
        samplerate=24000,
        channels=1,
        subtype="PCM_16",
    ) as wav_file:
        for _, _, audio in generator:
            if audio is None:
                continue

            wav_file.write(
                audio.detach().cpu().numpy()
            )
            wrote_audio = True

    if not wrote_audio:
        raise RuntimeError("Kokoro generated no audio.")


def _play_with_interrupt(audio_path: Path, interrupt_event=None, speaking_event=None) -> bool:
    _ensure_mixer()
    if interrupt_event is not None:
        interrupt_event.clear()

    interrupted = False
    try:
        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()
        if speaking_event is not None:
            speaking_event.set()

        while pygame.mixer.music.get_busy():
            if interrupt_event is not None and interrupt_event.is_set():
                interrupted = True
                print("JARVIS speech interrupted.")
                try:
                    pygame.mixer.music.stop()
                except Exception as e:
                    print("Neural TTS stop error:", e)
                break
            time.sleep(0.01)

        return interrupted
    finally:
        if speaking_event is not None:
            speaking_event.clear()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        if interrupt_event is not None:
            interrupt_event.clear()


def _speak_with_kokoro(
    text: str,
    language: str | None,
    interrupt_event=None,
    speaking_event=None,
) -> bool:
    if KPipeline is None:
        raise RuntimeError("Kokoro is not installed.")

    if pygame is None:
        raise RuntimeError("pygame is not installed.")

    language_code, voice = _select_kokoro_voice(
        text,
        language=language,
    )

    output_path = (
        Path(tempfile.gettempdir())
        / f"jarvis_kokoro_{uuid.uuid4().hex}.wav"
    )

    try:
        print(
            "JARVIS local neural TTS voice: "
            f"{voice}"
        )

        _synthesize_kokoro(
            text,
            language_code,
            voice,
            output_path,
        )

        return _play_with_interrupt(
            output_path,
            interrupt_event=interrupt_event,
            speaking_event=speaking_event,
        )

    finally:
        _safe_unlink(output_path)


def _speak_with_sapi(text: str, interrupt_event=None, speaking_event=None) -> bool:
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)
    engine.setProperty("rate", 174)

    if interrupt_event is not None:
        interrupt_event.clear()

    interrupted = False
    loop_started = False
    if speaking_event is not None:
        speaking_event.set()

    try:
        engine.say(text)
        engine.startLoop(False)
        loop_started = True

        while engine.isBusy():
            if interrupt_event is not None and interrupt_event.is_set():
                interrupted = True
                print("JARVIS speech interrupted.")
                try:
                    engine.stop()
                except Exception as e:
                    print("TTS stop error:", e)
                while engine.isBusy():
                    engine.iterate()
                    time.sleep(0.01)
                break
            engine.iterate()
            time.sleep(0.01)
    finally:
        if loop_started:
            try:
                engine.endLoop()
            except Exception:
                pass
        if speaking_event is not None:
            speaking_event.clear()
        if interrupt_event is not None:
            interrupt_event.clear()

    return interrupted


def speak(
    text: str,
    language: str | None = None,
    interrupt_event=None,
    speaking_event=None,
) -> bool:
    """Speak locally with Kokoro and fall back to SAPI5."""
    if not text:
        return False

    spoken_text = _prepare_speech_text(text)

    if not spoken_text:
        return False

    if not _env_flag(
        "JARVIS_TTS_ENABLED",
        True,
    ):
        return False

    engine = os.getenv(
        "JARVIS_TTS_ENGINE",
        "kokoro",
    ).strip().lower()

    if engine == "sapi5":
        return _speak_with_sapi(
            spoken_text,
            interrupt_event,
            speaking_event,
        )

    if engine != "kokoro":
        print(
            "Unknown JARVIS_TTS_ENGINE="
            f"{engine!r}; using Kokoro."
        )

    try:
        return _speak_with_kokoro(
            spoken_text,
            language=language,
            interrupt_event=interrupt_event,
            speaking_event=speaking_event,
        )

    except Exception as exc:
        print(
            "Kokoro TTS unavailable; "
            f"falling back to local SAPI5: {exc}"
        )

        return _speak_with_sapi(
            spoken_text,
            interrupt_event,
            speaking_event,
        )

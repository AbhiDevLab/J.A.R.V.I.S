"""J.A.R.V.I.S. neural TTS with interruptible playback and SAPI5 fallback."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock

import pyttsx3

try:
    import edge_tts  # type: ignore
except Exception:
    edge_tts = None

try:
    import pygame  # type: ignore
except Exception:
    pygame = None

_mixer_lock = Lock()
_mixer_initialized = False


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097F" for char in text)


def _select_voice(text: str, language: str | None = None) -> str:
    detected = (language or "").strip().lower()

    if detected in {"hi", "hi-in", "hindi"}:
        return os.getenv("JARVIS_TTS_HI_VOICE", "hi-IN-MadhurNeural")

    if detected in {"en", "en-in", "en-us", "english"}:
        return os.getenv("JARVIS_TTS_EN_VOICE", "en-US-GuyNeural")

    configured = os.getenv("JARVIS_TTS_LANGUAGE", "auto").strip().lower()

    if configured in {"hi", "hi-in", "hindi"}:
        return os.getenv("JARVIS_TTS_HI_VOICE", "hi-IN-MadhurNeural")

    if configured in {"en", "en-in", "en-us", "english"}:
        return os.getenv("JARVIS_TTS_EN_VOICE", "en-US-GuyNeural")

    if _contains_devanagari(text):
        return os.getenv("JARVIS_TTS_HI_VOICE", "hi-IN-MadhurNeural")

    return os.getenv("JARVIS_TTS_EN_VOICE", "en-US-GuyNeural")


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


async def _synthesize_edge(text: str, output_path: Path, voice: str) -> None:
    communicator = edge_tts.Communicate(
        text,
        voice,
        rate=os.getenv("JARVIS_TTS_RATE", "-5%"),
        volume=os.getenv("JARVIS_TTS_VOLUME", "+0%"),
        pitch=os.getenv("JARVIS_TTS_PITCH", "-2Hz"),
    )
    await communicator.save(str(output_path))


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


def _speak_with_edge(text: str, language: str | None, interrupt_event=None, speaking_event=None) -> bool:
    if edge_tts is None:
        raise RuntimeError("edge-tts is not installed.")
    if pygame is None:
        raise RuntimeError("pygame is not installed.")

    voice = _select_voice(text, language=language)
    output_path = Path(tempfile.gettempdir()) / f"jarvis_tts_{uuid.uuid4().hex}.mp3"

    try:
        print(f"JARVIS neural TTS voice: {voice}")
        asyncio.run(_synthesize_edge(text, output_path, voice))
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


def speak(text: str, language: str | None = None, interrupt_event=None, speaking_event=None) -> bool:
    if not text:
        return False

    if not _env_flag("JARVIS_TTS_ENABLED", True):
        return _speak_with_sapi(text, interrupt_event, speaking_event)

    try:
        return _speak_with_edge(
            text,
            language=language,
            interrupt_event=interrupt_event,
            speaking_event=speaking_event,
        )
    except Exception as e:
        print("Neural TTS unavailable; falling back to SAPI5:", e)
        return _speak_with_sapi(text, interrupt_event, speaking_event)

"""Phase 9.2 regression tests for the TTS interruption contract."""

from __future__ import annotations

import threading

from engine import tts


class FakeMusic:
    def __init__(self, interrupt_event=None, speaking_event=None, interrupt=False):
        self.interrupt_event = interrupt_event
        self.speaking_event = speaking_event
        self.interrupt = interrupt
        self.poll_count = 0
        self.loaded_path = None
        self.play_calls = 0
        self.stop_calls = 0
        self.unload_calls = 0

    def load(self, path):
        self.loaded_path = path

    def play(self):
        self.play_calls += 1

    def get_busy(self):
        self.poll_count += 1
        if self.interrupt:
            assert self.speaking_event.is_set()
            self.interrupt_event.set()
            return True
        return self.poll_count == 1

    def stop(self):
        self.stop_calls += 1

    def unload(self):
        self.unload_calls += 1


class FakeMixer:
    def __init__(self, music):
        self.music = music
        self.init_calls = 0

    def init(self):
        self.init_calls += 1


class FakePygame:
    def __init__(self, music):
        self.mixer = FakeMixer(music)


def configure_fake_audio(monkeypatch, music):
    pygame = FakePygame(music)
    monkeypatch.setattr(tts, "pygame", pygame)
    monkeypatch.setattr(tts, "_mixer_initialized", False)
    monkeypatch.setattr(tts.time, "sleep", lambda _seconds: None)
    return pygame


def test_tts_playback_stops_when_shared_interrupt_event_is_set(monkeypatch):
    interrupt_event = threading.Event()
    speaking_event = threading.Event()
    music = FakeMusic(
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
        interrupt=True,
    )
    pygame = configure_fake_audio(monkeypatch, music)

    interrupted = tts._play_with_interrupt(
        "response.wav",
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
    )

    assert interrupted is True
    assert music.loaded_path == "response.wav"
    assert music.play_calls == 1
    assert music.stop_calls >= 1
    assert music.unload_calls == 1
    assert pygame.mixer.init_calls == 1
    assert speaking_event.is_set() is False
    assert interrupt_event.is_set() is False


def test_tts_playback_finishes_normally_without_interrupt(monkeypatch):
    interrupt_event = threading.Event()
    speaking_event = threading.Event()
    music = FakeMusic(
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
    )
    configure_fake_audio(monkeypatch, music)

    interrupted = tts._play_with_interrupt(
        "response.wav",
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
    )

    assert interrupted is False
    assert music.play_calls == 1
    assert music.unload_calls == 1
    assert speaking_event.is_set() is False
    assert interrupt_event.is_set() is False

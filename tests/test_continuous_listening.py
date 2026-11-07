"""Phase 9.1 tests for opt-in continuous listening controls and ownership."""

from __future__ import annotations

import json
import queue
import threading

from engine import command, settings_store


def test_continuous_listening_preference_defaults_off_and_persists(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "_SETTINGS_PATH", settings_path)

    defaults = settings_store.load_settings()
    assert defaults["continuous_listening"] is False

    enabled = settings_store.update_settings({"continuous_listening": "true"})
    assert enabled["continuous_listening"] is True
    assert json.loads(settings_path.read_text(encoding="utf-8"))["continuous_listening"] is True

    disabled = settings_store.update_settings({"continuous_listening": "false"})
    assert disabled["continuous_listening"] is False


def test_continuous_listening_cannot_start_before_authentication(monkeypatch):
    event = threading.Event()
    monkeypatch.setattr(command, "_continuous_listening_event", event)
    monkeypatch.setattr(command, "_assistant_ready", False)
    monkeypatch.setattr(command, "_continuous_thread", None)

    result = command.setContinuousListening(True)

    assert result["success"] is False
    assert result["enabled"] is False
    assert event.is_set() is False


def test_continuous_listening_starts_and_stops_a_single_background_worker(monkeypatch):
    event = threading.Event()
    started = []

    class FakeThread:
        def __init__(self, *, target, args, name, daemon):
            self.target = target
            self.args = args
            self.name = name
            self.daemon = daemon
            self._alive = False
            self._jarvis_stop_event = None

        def start(self):
            self._alive = True
            started.append(self)

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(command, "_continuous_listening_event", event)
    monkeypatch.setattr(command, "_continuous_thread", None)
    monkeypatch.setattr(command, "_continuous_thread_lock", threading.Lock())
    monkeypatch.setattr(command, "_assistant_ready", True)
    monkeypatch.setattr(command.threading, "Thread", FakeThread)

    enabled = command.setContinuousListening(True)

    assert enabled["success"] is True
    assert enabled["enabled"] is True
    assert event.is_set() is True
    assert len(started) == 1
    assert started[0].name == "jarvis-continuous-listener"
    assert started[0].daemon is True
    assert started[0]._jarvis_stop_event.is_set() is False

    disabled = command.setContinuousListening(False)

    assert disabled["success"] is True
    assert disabled["enabled"] is False
    assert event.is_set() is False
    assert started[0]._jarvis_stop_event.is_set() is True


def test_stop_listening_voice_phrases_are_recognized_exactly():
    for phrase in (
        "stop listening",
        "pause listening",
        "stop continuous listening",
        "pause continuous listening",
        "Jarvis, stop listening!",
    ):
        assert command._is_stop_listening_request(phrase) is True

    assert command._is_stop_listening_request("stop the music") is False
    assert command._is_stop_listening_request("stop deleting the file") is False


def test_typed_requests_are_queued_when_continuous_mode_owns_the_mic(monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(command, "_continuous_listening_event", event)
    monkeypatch.setattr(command, "detect_text_language", lambda _text: "en")
    monkeypatch.setattr(command, "_safe_display", lambda *args, **kwargs: None)

    while True:
        try:
            command._continuous_input_queue.get_nowait()
        except queue.Empty:
            break

    result = command.allCommands("What did we discuss earlier?")

    assert result == {"success": True, "queued": True}

    queued_query, queued_language, is_voice_input = (
        command._continuous_input_queue.get_nowait()
    )
    assert queued_query == "What did we discuss earlier?"
    assert queued_language == "en"
    assert is_voice_input is False

    event.clear()

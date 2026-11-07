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

def test_continuous_recognizer_configures_adaptive_vad_and_clamps_values(monkeypatch):
    class FakeRecognizer:
        pass

    monkeypatch.setenv("JARVIS_CONTINUOUS_PAUSE_THRESHOLD", "99")
    monkeypatch.setenv("JARVIS_CONTINUOUS_PHRASE_LIMIT", "0")
    monkeypatch.setenv("JARVIS_VAD_DYNAMIC_ENERGY", "true")
    monkeypatch.setenv("JARVIS_VAD_ADJUSTMENT_DAMPING", "-5")
    monkeypatch.setenv("JARVIS_VAD_ENERGY_RATIO", "20")
    monkeypatch.setenv("JARVIS_VAD_PHRASE_THRESHOLD", "0.01")
    monkeypatch.setenv("JARVIS_VAD_NON_SPEAKING_DURATION", "9")

    recognizer = FakeRecognizer()
    phrase_limit = command._configure_continuous_recognizer(recognizer)

    assert recognizer.pause_threshold == 2.0
    assert recognizer.dynamic_energy_threshold is True
    assert recognizer.dynamic_energy_adjustment_damping == 0.01
    assert recognizer.dynamic_energy_ratio == 3.0
    assert recognizer.phrase_threshold == 0.1
    assert recognizer.non_speaking_duration == 1.5
    assert phrase_limit == 2.0


def test_continuous_vad_can_disable_dynamic_energy_adjustment(monkeypatch):
    class FakeRecognizer:
        pass

    monkeypatch.setenv("JARVIS_VAD_DYNAMIC_ENERGY", "off")
    recognizer = FakeRecognizer()

    command._configure_continuous_recognizer(recognizer)

    assert recognizer.dynamic_energy_threshold is False


def test_hotword_is_paused_during_continuous_capture_and_processing():
    assert command._should_pause_hotword(
        continuous_mode=True, mic_busy=True, speaking=False
    ) is True
    assert command._should_pause_hotword(
        continuous_mode=True, mic_busy=False, speaking=False
    ) is True


def test_hotword_is_available_only_during_tts_in_continuous_mode():
    assert command._should_pause_hotword(
        continuous_mode=True, mic_busy=False, speaking=True
    ) is False


def test_hotword_keeps_existing_non_continuous_behavior():
    assert command._should_pause_hotword(
        continuous_mode=False, mic_busy=False, speaking=False
    ) is False
    assert command._should_pause_hotword(
        continuous_mode=False, mic_busy=True, speaking=True
    ) is True


def test_wake_word_interrupts_tts_without_launching_a_second_flow():
    interrupt_event = threading.Event()

    decision = command._route_hotword_activation(
        continuous_mode=True,
        speaking=True,
        interrupt_event=interrupt_event,
    )

    assert decision == "interrupted"
    assert interrupt_event.is_set() is True


def test_wake_word_outside_tts_is_ignored_in_continuous_mode():
    interrupt_event = threading.Event()

    decision = command._route_hotword_activation(
        continuous_mode=True,
        speaking=False,
        interrupt_event=interrupt_event,
    )

    assert decision == "ignored"
    assert interrupt_event.is_set() is False


def test_regular_wake_word_activation_is_preserved():
    decision = command._route_hotword_activation(
        continuous_mode=False,
        speaking=False,
        interrupt_event=threading.Event(),
    )

    assert decision == "activate"


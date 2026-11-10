"""Regression tests for the ChatGPT-style continuous-listening voice controls."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_both_composers_have_separate_one_shot_and_continuous_voice_controls():
    html = (ROOT / "www" / "index.html").read_text(encoding="utf-8")

    assert 'id="MicBtn"' in html
    assert 'id="ContinuousListeningBtn"' in html
    assert 'id="ConversationMicBtn"' in html
    assert 'id="ConversationContinuousListeningBtn"' in html

    assert html.count('class="voice-mode-btn"') == 2
    assert html.count('class="voice-mode-waveform"') == 2
    assert html.count('aria-pressed="false"') >= 2


def test_continuous_listening_is_not_exposed_as_a_settings_checkbox():
    html = (ROOT / "www" / "index.html").read_text(encoding="utf-8")
    main_js = (ROOT / "www" / "main.js").read_text(encoding="utf-8")
    controller_js = (ROOT / "www" / "controller.js").read_text(encoding="utf-8")

    assert "SettingsContinuousListening" not in html
    assert "SettingsContinuousListening" not in main_js
    assert "SettingsContinuousListening" not in controller_js
    assert "Use the purple voice-wave button" in html


def test_voice_mode_button_uses_authenticated_backend_and_persists_preference():
    main_js = (ROOT / "www" / "main.js").read_text(encoding="utf-8")
    command_py = (ROOT / "engine" / "command.py").read_text(encoding="utf-8")

    assert 'eel.setContinuousListening(enable)()' in main_js
    assert 'eel.saveSettings({\n                continuous_listening: enable' in main_js
    assert "if (!runtimeResult || !runtimeResult.success)" in main_js
    assert "Complete authentication before enabling continuous listening." in command_py
    assert "name=\"jarvis-continuous-listener\"" in command_py


def test_backend_listener_state_synchronizes_both_voice_mode_buttons():
    controller_js = (ROOT / "www" / "controller.js").read_text(encoding="utf-8")

    assert (
        '#ContinuousListeningBtn, #ConversationContinuousListeningBtn'
        in controller_js
    )
    assert 'button.setAttribute("aria-pressed", String(listening))' in controller_js
    assert 'button.classList.toggle("is-active", listening)' in controller_js
    assert "window.setContinuousListeningStatus = setContinuousListeningStatus" in controller_js


def test_voice_mode_button_has_distinct_active_state_and_reduced_motion_support():
    css = (ROOT / "www" / "style.css").read_text(encoding="utf-8")

    assert ".voice-mode-btn" in css
    assert ".voice-mode-btn.is-active" in css
    assert ".voice-mode-waveform span" in css
    assert "@media (prefers-reduced-motion: reduce)" in css

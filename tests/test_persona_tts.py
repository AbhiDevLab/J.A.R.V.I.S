"""Regression tests for JARVIS persona and speech preparation."""

from unittest.mock import patch

from engine.persona import build_jarvis_prompt
from engine.tts import _prepare_speech_text, _select_kokoro_voice


def test_persona_prompt_has_calm_jarvis_style():
    prompt = build_jarvis_prompt(
        "How are you?",
        "English",
    )

    assert "calm confidence" in prompt
    assert "understated sophistication" in prompt
    assert 'Address the user as "Sir" naturally and sparingly.' in prompt
    assert "Avoid generic filler" in prompt


def test_persona_prompt_preserves_context_and_language():
    prompt = build_jarvis_prompt(
        "What did we just discuss?",
        "English",
        "Previous conversation context:\\nUser: We discussed the server.",
    )

    assert "We discussed the server." in prompt
    assert "The user's detected speech language is: English." in prompt


def test_british_kokoro_voice_uses_british_language_pipeline():
    with patch.dict(
        "os.environ",
        {
            "JARVIS_TTS_EN_VOICE": "bm_george",
            "JARVIS_TTS_LANGUAGE": "auto",
        },
        clear=False,
    ):
        language_code, voice = _select_kokoro_voice(
            "Good evening, Sir.",
            language="en",
        )

    assert language_code == "b"
    assert voice == "bm_george"


def test_hindi_voice_stays_on_hindi_pipeline():
    with patch.dict(
        "os.environ",
        {
            "JARVIS_TTS_HI_VOICE": "hm_omega",
        },
        clear=False,
    ):
        language_code, voice = _select_kokoro_voice(
            "नमस्ते, सर।",
            language="hi",
        )

    assert language_code == "h"
    assert voice == "hm_omega"


def test_speech_preparation_adds_sentence_pauses_without_changing_content():
    with patch.dict(
        "os.environ",
        {"JARVIS_TTS_SENTENCE_PAUSES": "1"},
        clear=False,
    ):
        spoken = _prepare_speech_text(
            "The server is ready. The connection is stable."
        )

    assert "The server is ready." in spoken
    assert "The connection is stable." in spoken
    assert "\n" in spoken

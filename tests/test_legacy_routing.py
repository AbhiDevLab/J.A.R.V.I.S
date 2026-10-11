"""Regression tests for legacy fallback routing in conversational turns."""

from engine.legacy_routing import (
    is_legacy_message_command,
    is_legacy_open_command,
    is_legacy_youtube_command,
)


def test_question_about_opening_a_file_is_not_an_open_command():
    assert is_legacy_open_command("Which file did you just open?") is False
    assert is_legacy_open_command("What did you open?") is False
    assert is_legacy_open_command("Do you know how to open README.md?") is False
    assert is_legacy_open_command("Opening which file did you just?") is False


def test_explicit_open_commands_still_match():
    assert is_legacy_open_command("Open README.md") is True
    assert is_legacy_open_command("please open README.md") is True
    assert is_legacy_open_command("Launch Chrome") is True
    assert is_legacy_open_command("Run Notepad") is True


def test_mentions_of_youtube_do_not_start_playback():
    assert is_legacy_youtube_command("What did you recommend on YouTube?") is False
    assert is_legacy_youtube_command("I watched that on YouTube yesterday") is False
    assert is_legacy_youtube_command("play lo-fi music on YouTube") is True
    assert is_legacy_youtube_command("youtube lo-fi music") is True


def test_mentions_of_messages_or_calls_do_not_start_legacy_contact_flow():
    assert is_legacy_message_command("What should I say in the message?") is False
    assert is_legacy_message_command("We discussed a phone call yesterday") is False
    assert is_legacy_message_command("send message to Alice") is True
    assert is_legacy_message_command("please send a message to Alice") is True
    assert is_legacy_message_command("make a video call to Alice") is True

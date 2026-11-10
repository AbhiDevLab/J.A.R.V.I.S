"""UI lifecycle contracts for system-resource reports."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _section(source: str, section_id: str) -> str:
    start_marker = f'<section id="{section_id}"'
    start = source.find(start_marker)
    assert start >= 0, f"Missing {section_id} section"
    end = source.find("</section>", start)
    assert end >= 0, f"Unclosed {section_id} section"
    return source[start : end + len("</section>")]


def test_resource_report_card_is_in_the_separate_siriwave_view_not_the_oval():
    html = (ROOT / "www" / "index.html").read_text(encoding="utf-8")
    oval = _section(html, "Oval")
    siri_wave = _section(html, "SiriWave")

    assert 'id="HoodResponse"' not in oval
    assert 'id="HoodResponse"' in siri_wave
    assert 'id="HoodResponseBody"' in siri_wave


def test_resource_report_has_a_dedicated_scrollable_siriwave_layout():
    css = (ROOT / "www" / "style.css").read_text(encoding="utf-8")

    assert "#SiriWave .hood-response-shell" in css
    assert "#SiriWave .hood-response-card .jarvis-response-body" in css
    assert "#Oval .hood-response-shell" not in css


def test_resource_response_keeps_the_oval_hidden_after_rendering():
    main_js = (ROOT / "www" / "main.js").read_text(encoding="utf-8")
    controller_js = (ROOT / "www" / "controller.js").read_text(encoding="utf-8")
    command_py = (ROOT / "engine" / "command.py").read_text(encoding="utf-8")

    assert '$("#Oval").attr("hidden", true)' in main_js
    assert '$("#SiriWave").attr("hidden", false)' in main_js
    assert '$("#SiriWave .siri-message").hide()' in controller_js
    assert '$("#SiriWave #siri-container").hide()' in controller_js

    assert "keep_response_view = True" in command_py
    assert '_safe_display("ShowSiriWave")' in command_py
    assert "if not keep_response_view:" in command_py
    assert '            "ShowHood"' in command_py

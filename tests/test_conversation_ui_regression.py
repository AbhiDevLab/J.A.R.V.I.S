"""Regression guards for conversation viewer navigation and HUD recovery."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "www" / "index.html").read_text(encoding="utf-8")
MAIN_JS = (ROOT / "www" / "main.js").read_text(encoding="utf-8")


def test_conversation_viewer_has_history_switch_control():
    assert 'id="ConversationViewerHistory"' in INDEX_HTML
    assert 'aria-label="Switch conversation"' in INDEX_HTML
    assert 'id="ConversationViewerClose"' in INDEX_HTML


def test_history_switch_control_opens_sidebar_from_active_viewer():
    assert '$("#ConversationViewerHistory").on(' in MAIN_JS
    handler = MAIN_JS.split(
        '$("#ConversationViewerHistory").on(', 1
    )[1].split("\\n    );", 1)[0]
    assert "openHistorySidebar();" in handler


def test_closing_viewer_restores_hud_and_hides_siriwave():
    close_start = MAIN_JS.index("function closeConversationViewer()")
    close_end = MAIN_JS.index("window.openConversationViewer", close_start)
    close_handler = MAIN_JS[close_start:close_end]

    assert 'oval.classList.remove(' in close_handler
    assert 'oval.hidden = false;' in close_handler
    assert 'oval.removeAttribute("hidden")' in close_handler
    assert 'siriWave.hidden = true;' in close_handler
    assert 'viewer.classList.remove(' in close_handler
    assert 'viewer.setAttribute(' in close_handler

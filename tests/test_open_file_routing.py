from pathlib import Path

from engine.automation.actions import AutomationAction, RiskLevel
from engine.automation.dialogue import _complete_open_file
from engine.automation.router import route_command


def test_explicit_absolute_file_path_routes_to_open_file():
    command = r"Open file C:\Dev\Web\J.A.R.V.I.S\README.md"

    action = route_command(command)

    assert action is not None
    assert action.action_type == "open_file"
    assert action.parameters["source"] == r"C:\Dev\Web\J.A.R.V.I.S\README.md"


def test_named_file_in_directory_routes_to_open_file():
    command = r"Open the README.md file in C:\Dev\Web\J.A.R.V.I.S"

    action = route_command(command)

    assert action is not None
    assert action.action_type == "open_file"
    assert Path(action.parameters["source"]) == Path(
        r"C:\Dev\Web\J.A.R.V.I.S"
    ) / "README.md"


def test_generic_open_routes_to_matching_file_after_app_lookup(monkeypatch, tmp_path):
    from engine.automation import router

    target = tmp_path / "jarvis-phase85-selection-check-20261011.txt"
    target.write_text("TEST FILE", encoding="utf-8")

    monkeypatch.setattr(router, "resolve_application", lambda _name: None)

    def fake_search_paths(name, expected_type=None, max_results=None):
        if expected_type == "file":
            return [target]
        return []

    monkeypatch.setattr(router, "search_paths", fake_search_paths)

    command = "Open jarvis phase85 selection check 20261011 txt"
    action = route_command(command)

    assert action is not None
    assert action.action_type == "open_file"
    assert action.parameters["source"] == "jarvis phase85 selection check 20261011 txt"


def test_open_file_prefers_an_exact_path_over_fuzzy_search(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("# test", encoding="utf-8")
    action = AutomationAction(
        action_type="open_file",
        parameters={"source": str(target)},
        risk=RiskLevel.LOW,
    )

    completed = _complete_open_file(action)

    assert completed is not None
    assert completed.parameters["path"] == str(target.resolve())

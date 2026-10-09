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

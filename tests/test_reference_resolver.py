"""Phase 8.5 regressions for cross-turn reference context."""

from engine.reference_resolver import (
    assistant_requests_confirmation,
    build_reference_context,
    is_clear_affirmative_confirmation,
    is_clear_negative_confirmation,
)


def test_reference_index_ranks_latest_file_path_and_keeps_distinct_targets():
    messages = [
        {"role": "user", "content": "Open C:\\Archive\\report.pdf"},
        {"role": "assistant", "content": "Opened C:\\Archive\\report.pdf"},
        {"role": "user", "content": "Now use C:\\Current\\report.pdf instead."},
        {"role": "assistant", "content": "I will use C:\\Current\\report.pdf."},
    ]

    context = build_reference_context(messages)

    assert context.index("C:\\Current\\report.pdf") < context.index("C:\\Archive\\report.pdf")
    assert "report.pdf" in context
    assert "Files and paths" in context


def test_reference_index_surfaces_application_and_person_references():
    messages = [
        {"role": "user", "content": "Use VS Code and send a message to Alice."},
        {"role": "assistant", "content": "VS Code is ready. I can message Alice."},
    ]

    context = build_reference_context(messages)

    assert "VS Code" in context
    assert "vscode" in context.casefold()
    assert "Alice" in context


def test_reference_index_includes_recent_tasks_and_answers_but_skips_acknowledgements():
    messages = [
        {"role": "user", "content": "Find my tax report and open it."},
        {"role": "assistant", "content": "I found the tax report in Documents."},
        {"role": "user", "content": "yes"},
        {"role": "assistant", "content": "Understood."},
        {"role": "user", "content": "Move the report to Archive."},
        {"role": "assistant", "content": "The report was moved to Archive."},
    ]

    context = build_reference_context(messages)

    assert "Find my tax report and open it" in context
    assert "Move the report to Archive" in context
    assert "The report was moved to Archive" in context
    assert "- User: yes" not in context


def test_reference_index_is_bounded():
    messages = []
    for index in range(100):
        filename = (
            "quarterly-comprehensive-research-document-with-extensive-"
            f"section-notes-and-decisions-unique-{index}.pdf"
        )
        messages.append({
            "role": "user",
            "content": (
                f"Please inspect C:/Archive/{filename} and preserve the detailed "
                f"project context, the previous comparison, the decision record, "
                f"and the reason for the change made during task {index}."
            ),
        })

    context = build_reference_context(messages, max_chars=600)

    assert len(context) <= 600
    assert context.endswith("[Reference index truncated.]")


def test_confirmation_language_is_conservative():
    assert assistant_requests_confirmation("Would you like me to open report.pdf?") is True
    assert assistant_requests_confirmation("I can open report.pdf.") is False
    assert is_clear_affirmative_confirmation("Yes, go ahead.") is True
    assert is_clear_negative_confirmation("No, cancel that.") is True
    assert is_clear_affirmative_confirmation("Open Chrome") is False
    assert is_clear_negative_confirmation("Open Chrome") is False

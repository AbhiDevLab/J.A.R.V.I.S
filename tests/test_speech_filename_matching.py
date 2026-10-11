"""Regression tests for punctuation-insensitive filename matching from speech transcripts."""

from engine.automation.filesystem import _file_match_rank, search_paths


def test_speech_normalized_filename_matches_hyphens_and_extension_spacing():
    assert (
        _file_match_rank(
            "jarvis-phase85-selection-check-20261011.txt",
            "jarvis phase85 selection check 20261011 txt",
        )
        == 2
    )


def test_literal_filename_and_stem_matches_keep_higher_priority():
    filename = "jarvis-phase85-selection-check-20261011.txt"

    assert _file_match_rank(filename, filename) == 0
    assert _file_match_rank(filename, "jarvis-phase85-selection-check-20261011") == 1
    assert (
        _file_match_rank(
            filename,
            "jarvis phase85 selection check 20261011 txt",
        )
        > 1
    )


def test_normalized_search_still_returns_duplicate_candidates(tmp_path):
    first = tmp_path / "A" / "jarvis-phase85-selection-check-20261011.txt"
    second = tmp_path / "B" / "jarvis-phase85-selection-check-20261011.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("TEST FILE A", encoding="utf-8")
    second.write_text("TEST FILE B", encoding="utf-8")

    results = search_paths(
        "jarvis phase85 selection check 20261011 txt",
        expected_type="file",
        search_roots=[tmp_path],
    )

    assert set(results) == {first.resolve(), second.resolve()}

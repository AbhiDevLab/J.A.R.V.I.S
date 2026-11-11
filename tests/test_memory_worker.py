"""Regression tests for OpenJarvis-inspired asynchronous memory extraction."""
from __future__ import annotations

import threading

from engine.memory_worker import MemoryExtractionWorker


def test_submit_returns_while_memory_processor_is_still_running():
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def processor(user_text, assistant_text, conversation_id):
        started.set()
        release.wait(timeout=2.0)
        finished.set()

    worker = MemoryExtractionWorker(processor, max_queue=2)
    try:
        assert worker.submit(
            "I prefer concise technical answers.",
            "Understood.",
            conversation_id="conversation-1",
        ) is True
        assert started.wait(timeout=1.0)
        # The processor is deliberately blocked, but submit already returned.
        assert finished.is_set() is False
        assert worker.is_running is True
    finally:
        release.set()
        assert worker.stop(timeout=2.0) is True

    assert finished.is_set() is True


def test_queue_is_bounded_and_drops_excess_work_without_blocking():
    started = threading.Event()
    release = threading.Event()
    processed = []

    def processor(user_text, assistant_text, conversation_id):
        if user_text == "first":
            started.set()
            release.wait(timeout=2.0)
        processed.append(user_text)

    worker = MemoryExtractionWorker(processor, max_queue=1)
    try:
        assert worker.submit("first") is True
        assert started.wait(timeout=1.0)
        assert worker.submit("second") is True
        assert worker.submit("third") is False
        assert worker.pending_count == 1
    finally:
        release.set()
        assert worker.stop(timeout=2.0) is True

    assert processed == ["first", "second"]


def test_one_failed_job_does_not_kill_the_worker():
    recovered = threading.Event()
    attempts = []

    def processor(user_text, assistant_text, conversation_id):
        attempts.append(user_text)
        if user_text == "bad":
            raise RuntimeError("simulated provider outage")
        recovered.set()

    worker = MemoryExtractionWorker(processor, max_queue=3)
    try:
        assert worker.submit("bad") is True
        assert worker.submit("good") is True
        assert recovered.wait(timeout=1.0)
        assert worker.is_running is True
    finally:
        assert worker.stop(timeout=2.0) is True

    assert attempts == ["bad", "good"]


def test_empty_exchange_is_rejected_without_starting_worker():
    worker = MemoryExtractionWorker(lambda *_args: None)

    assert worker.submit("   ") is False
    assert worker.is_running is False
    assert worker.pending_count == 0


def test_submit_applies_safe_payload_bounds():
    received = []
    done = threading.Event()

    def processor(user_text, assistant_text, conversation_id):
        received.append((user_text, assistant_text, conversation_id))
        done.set()

    worker = MemoryExtractionWorker(processor, max_queue=1)
    try:
        assert worker.submit(
            "u" * 2500,
            "a" * 2500,
            conversation_id="c" * 200,
        ) is True
        assert done.wait(timeout=1.0)
    finally:
        assert worker.stop(timeout=2.0) is True

    assert received == [("u" * 2000, "a" * 2000, "c" * 160)]

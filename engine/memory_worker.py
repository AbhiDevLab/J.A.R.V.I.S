"""Non-blocking durable-memory extraction worker.

OpenJarvis-inspired adaptation: completed exchanges are queued for one bounded
background worker so memory extraction never holds the live command/microphone
loop. The existing J.A.R.V.I.S extraction policy remains authoritative.
"""
from __future__ import annotations

import atexit
import logging
import queue
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_STOP = object()
_Processor = Callable[[str, str, str], object]


def _extract_memory_job(user_text: str, assistant_text: str, conversation_id: str) -> None:
    """Import the existing extractor only in the worker thread."""
    from engine.memory import extract_memories_from_turn

    extract_memories_from_turn(
        user_text,
        assistant_text,
        conversation_id=conversation_id,
    )


class MemoryExtractionWorker:
    """Bounded, single-threaded, best-effort memory-extraction queue.

    submit() only enqueues a small immutable snapshot and returns immediately.
    If the queue is full or shutdown has begun, the job is dropped rather than
    blocking a user interaction. A failed job cannot terminate the worker.
    """

    def __init__(
        self,
        processor: Optional[_Processor] = None,
        *,
        max_queue: int = 64,
        thread_name: str = "jarvis-memory-extraction",
    ) -> None:
        self._processor = processor or _extract_memory_job
        self._queue: queue.Queue[object] = queue.Queue(maxsize=max(1, int(max_queue)))
        self._thread_name = thread_name
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def submit(
        self,
        user_text: str,
        assistant_text: str = "",
        *,
        conversation_id: str = "",
    ) -> bool:
        """Enqueue one exchange without waiting for the extractor or LLM."""
        user = str(user_text or "").strip()
        if not user:
            return False

        # Match the extractor's prompt bounds and keep queue memory bounded.
        job = (
            user[:2000],
            str(assistant_text or "")[:2000],
            str(conversation_id or "")[:160],
        )

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if not self._running.is_set():
                    return False
            else:
                self._running.set()
                self._thread = threading.Thread(
                    target=self._run,
                    name=self._thread_name,
                    daemon=True,
                )
                self._thread.start()

            try:
                self._queue.put_nowait(job)
                return True
            except queue.Full:
                logger.debug("Background memory queue full; dropping extraction job")
                return False

    def _run(self) -> None:
        while True:
            try:
                job = self._queue.get(timeout=0.25)
            except queue.Empty:
                if not self._running.is_set():
                    return
                continue

            try:
                if job is _STOP:
                    return
                user_text, assistant_text, conversation_id = job
                self._processor(
                    str(user_text),
                    str(assistant_text),
                    str(conversation_id),
                )
            except Exception:
                # Memory is best-effort. Never let one provider/database failure
                # terminate the worker or affect the live assistant response.
                logger.warning(
                    "Background memory extraction job failed (%s)",
                    type(__import__("sys").exc_info()[1]).__name__,
                )
            finally:
                self._queue.task_done()

    def stop(self, timeout: float = 1.0) -> bool:
        """Stop the worker, draining queued jobs when time permits.

        Returns False only when the current processor call outlives the timeout.
        The worker is daemonized, so a slow provider cannot prevent process exit.
        """
        with self._lock:
            thread = self._thread
            if thread is None:
                return True
            self._running.clear()
            try:
                self._queue.put_nowait(_STOP)
            except queue.Full:
                # The worker will drain the bounded queue, then observe the
                # cleared running flag and exit without a sentinel.
                pass

        thread.join(timeout=max(0.0, float(timeout)))
        finished = not thread.is_alive()
        if finished:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return finished


_memory_extraction_worker = MemoryExtractionWorker()
atexit.register(_memory_extraction_worker.stop)


def submit_memory_extraction(
    user_text: str,
    assistant_text: str = "",
    *,
    conversation_id: str = "",
) -> bool:
    """Queue only eligible durable user statements for background extraction.

    The same opt-in, memory-enabled and durable-statement gates used by the
    synchronous extractor are checked before a worker is started.
    """
    try:
        from engine.memory import (
            _env_flag,
            _should_attempt_extraction,
            memory_store,
        )

        if (
            not _env_flag("JARVIS_MEMORY_AUTO_EXTRACT", True)
            or not memory_store.enabled
            or not _should_attempt_extraction(user_text)
        ):
            return False
    except Exception:
        logger.debug("Background memory extraction eligibility check failed")
        return False

    return _memory_extraction_worker.submit(
        user_text,
        assistant_text,
        conversation_id=conversation_id,
    )


def stop_memory_extraction_worker(timeout: float = 1.0) -> bool:
    """Public lifecycle hook for orderly application shutdown and tests."""
    return _memory_extraction_worker.stop(timeout=timeout)


__all__ = [
    "MemoryExtractionWorker",
    "submit_memory_extraction",
    "stop_memory_extraction_worker",
]

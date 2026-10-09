"""Persistent long-term memory for J.A.R.V.I.S (Phase 8.2).

Memory is intentionally separate from conversation history and ephemeral
interaction state. SQLite is used from the Python standard library, so memory
works locally without requiring MongoDB or a vector database.

Stored memory types:
- semantic: durable, non-sensitive user facts/preferences/project context
- episodic: bounded records of meaningful completed interactions/actions

Retrieval is a lightweight lexical ranking pass. This can later be replaced or
augmented by embeddings without changing the memory-record contract.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


_MEMORY_TYPES = {"semantic", "episodic"}
_DEFAULT_EPISODIC_TTL_DAYS = 90
_DEFAULT_CONTEXT_LIMIT = 5
_MAX_CONTENT_LENGTH = 1200
_MAX_KEY_LENGTH = 120
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "here", "hers", "him", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "me", "my", "of", "on",
    "or", "our", "ours", "she", "so", "that", "the", "their", "them",
    "there", "these", "they", "this", "those", "to", "us", "was", "we",
    "were", "what", "when", "where", "which", "who", "why", "will",
    "with", "would", "you", "your", "yours", "jarvis", "please", "tell",
    "about", "remember", "recall", "know", "know", "something",
}
_SENSITIVE_PATTERN = re.compile(
    r"\b(password|passcode|pin code|api[\s_-]*key|access token|secret key|"
    r"private key|recovery code|credit card|debit card|bank account number|"
    r"social security|aadhaar number|passport number|medical diagnosis|"
    r"health condition|medical condition|medical history|medication|diagnosed|"
    r"sexual orientation|ethnicity|racial identity|religion|religious belief|"
    r"political affiliation|political party|political belief|biometric|fingerprint)\b",
    re.IGNORECASE,
)
_DURABLE_SIGNAL_PATTERN = re.compile(
    r"\b(i am|i'm|i prefer|i like|i love|i use|i work|i study|i build|"
    r"i'm building|i am building|my project|my preference|my preferred|"
    r"my goal|my role|my degree|my major|my name|i want you to remember|"
    r"please remember|remember that|from now on|i always|i usually|"
    r"i switched to|i have been working|i've been working|our project|"
    r"the project is|we are building)\b",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.+-]*", re.IGNORECASE)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_PATTERN.findall(str(text or ""))
        if len(token) > 1 and token.lower() not in _STOP_WORDS
    }


def _normalize_key(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return value[:_MAX_KEY_LENGTH]


def _is_sensitive(text: str) -> bool:
    return bool(_SENSITIVE_PATTERN.search(str(text or "")))


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _bounded_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


class MemoryStore:
    """Local persistent memory store with safe, explicit lifecycle methods."""

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        *,
        enabled: Optional[bool] = None,
    ) -> None:
        self._db_path_override = (
            Path(db_path).expanduser() if db_path is not None else None
        )
        self._enabled_override = enabled

    @property
    def db_path(self) -> Path:
        configured_path = self._db_path_override or Path(
            os.getenv("JARVIS_MEMORY_DB_PATH", "data/jarvis_memory.db")
        ).expanduser()
        return configured_path

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return bool(self._enabled_override)
        return _env_flag("JARVIS_MEMORY_ENABLED", True)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not self.enabled:
            raise RuntimeError("J.A.R.V.I.S memory is disabled.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL
                        CHECK (memory_type IN ('semantic', 'episodic')),
                    memory_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user',
                    source_conversation_id TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.8,
                    importance INTEGER NOT NULL DEFAULT 3
                        CHECK (importance BETWEEN 1 AND 5),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    expires_at TEXT,
                    superseded_by TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_memories_active_expiry
                    ON memories(is_active, expires_at);
                CREATE INDEX IF NOT EXISTS idx_memories_type_key
                    ON memories(memory_type, memory_key, is_active);
                CREATE INDEX IF NOT EXISTS idx_memories_updated
                    ON memories(updated_at DESC);
                """
            )
            connection.commit()
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        finally:
            connection.close()

    def _expire_in_connection(self, connection: sqlite3.Connection) -> int:
        now = _iso(_utc_now())
        cursor = connection.execute(
            """
            UPDATE memories
               SET is_active = 0, updated_at = ?
             WHERE is_active = 1
               AND expires_at IS NOT NULL
               AND expires_at <= ?
            """,
            (now, now),
        )
        return int(cursor.rowcount or 0)

    def expire_memories(self) -> int:
        """Deactivate every active memory whose expiry timestamp has passed."""
        with self._connection() as connection:
            return self._expire_in_connection(connection)

    def save_memory(
        self,
        content: str,
        *,
        memory_type: str = "semantic",
        key: str = "",
        source: str = "user",
        conversation_id: str = "",
        confidence: float = 0.8,
        importance: int = 3,
        expires_in_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a memory or supersede the active semantic memory with the same key.

        Semantic keys identify a fact/preference and are updated rather than
        duplicated. Episodic memories are append-only events. Expiry is optional
        for semantic memory and defaults to a bounded retention period for
        episodic memory.
        """
        text = re.sub(r"\s+", " ", str(content or "")).strip()
        kind = str(memory_type or "").strip().lower()
        if not self.enabled or not text or kind not in _MEMORY_TYPES:
            return None
        if len(text) > _MAX_CONTENT_LENGTH or _is_sensitive(text):
            return None

        memory_key = _normalize_key(key)
        if kind == "semantic" and not memory_key:
            memory_key = _normalize_key("fact_" + "_".join(sorted(_tokens(text))[:8]))
        if not memory_key:
            memory_key = "event_" + uuid.uuid4().hex[:12]

        confidence_value = _bounded_float(
            confidence, 0.0, 1.0, 0.8
        )
        try:
            minimum_confidence = float(
                os.getenv("JARVIS_MEMORY_MIN_CONFIDENCE", "0.72")
            )
        except (TypeError, ValueError):
            minimum_confidence = 0.72
        minimum_confidence = max(0.0, min(1.0, minimum_confidence))
        if confidence_value < minimum_confidence:
            return None

        importance_value = _bounded_int(importance, 1, 5, 3)
        now_dt = _utc_now()
        now = _iso(now_dt)
        if expires_in_days is None and kind == "episodic":
            expires_in_days = _bounded_int(
                os.getenv("JARVIS_EPISODIC_MEMORY_TTL_DAYS", "90"),
                1,
                3650,
                _DEFAULT_EPISODIC_TTL_DAYS,
            )
        expires_at = None
        if expires_in_days is not None:
            ttl = _bounded_int(expires_in_days, 1, 36500, 1)
            expires_at = _iso(now_dt + timedelta(days=ttl))

        safe_metadata = metadata if isinstance(metadata, dict) else {}
        try:
            metadata_json = json.dumps(
                safe_metadata, ensure_ascii=False, default=str
            )[:4000]
        except (TypeError, ValueError):
            metadata_json = "{}"

        new_id = str(uuid.uuid4())
        source_value = str(source or "user")[:80]
        conversation_value = str(conversation_id or "")[:160]

        try:
            with self._connection() as connection:
                self._expire_in_connection(connection)

                if kind == "semantic":
                    existing = connection.execute(
                        """
                        SELECT id, content, confidence, importance
                          FROM memories
                         WHERE memory_type = 'semantic'
                           AND memory_key = ?
                           AND is_active = 1
                         ORDER BY updated_at DESC
                         LIMIT 1
                        """,
                        (memory_key,),
                    ).fetchone()

                    if existing and str(existing["content"]).casefold() == text.casefold():
                        connection.execute(
                            """
                            UPDATE memories
                               SET confidence = MAX(confidence, ?),
                                   importance = MAX(importance, ?),
                                   updated_at = ?,
                                   source = ?,
                                   source_conversation_id = ?,
                                   expires_at = ?,
                                   metadata_json = ?
                             WHERE id = ?
                            """,
                            (
                                confidence_value, importance_value, now,
                                source_value, conversation_value, expires_at,
                                metadata_json, existing["id"],
                            ),
                        )
                        row_id = str(existing["id"])
                    else:
                        connection.execute(
                            """
                            INSERT INTO memories (
                                id, memory_type, memory_key, content, source,
                                source_conversation_id, confidence, importance,
                                created_at, updated_at, expires_at, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_id, kind, memory_key, text, source_value,
                                conversation_value, confidence_value,
                                importance_value, now, now, expires_at, metadata_json,
                            ),
                        )
                        if existing:
                            connection.execute(
                                """
                                UPDATE memories
                                   SET is_active = 0, superseded_by = ?, updated_at = ?
                                 WHERE id = ?
                                """,
                                (new_id, now, existing["id"]),
                            )
                        row_id = new_id
                else:
                    duplicate = connection.execute(
                        """
                        SELECT id FROM memories
                         WHERE memory_type = 'episodic'
                           AND memory_key = ?
                           AND content = ?
                           AND source_conversation_id = ?
                           AND is_active = 1
                         LIMIT 1
                        """,
                        (memory_key, text, conversation_value),
                    ).fetchone()
                    if duplicate:
                        row_id = str(duplicate["id"])
                    else:
                        connection.execute(
                            """
                            INSERT INTO memories (
                                id, memory_type, memory_key, content, source,
                                source_conversation_id, confidence, importance,
                                created_at, updated_at, expires_at, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_id, kind, memory_key, text, source_value,
                                conversation_value, confidence_value,
                                importance_value, now, now, expires_at, metadata_json,
                            ),
                        )
                        row_id = new_id

                row = connection.execute(
                    "SELECT * FROM memories WHERE id = ?", (row_id,)
                ).fetchone()
                return self._row_to_dict(row) if row else None
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            print(f"JARVIS memory write unavailable: {exc}")
            return None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
        result = dict(row)
        try:
            result["metadata"] = json.loads(result.pop("metadata_json", "{}") or "{}")
        except (TypeError, ValueError):
            result["metadata"] = {}
        result["is_active"] = bool(result.get("is_active", 0))
        return result

    def retrieve(
        self,
        query: str,
        *,
        limit: int = _DEFAULT_CONTEXT_LIMIT,
        memory_types: Optional[Iterable[str]] = None,
        minimum_score: float = 0.08,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant, non-expired memories using transparent lexical ranking."""
        if not self.enabled:
            return []
        query_text = re.sub(r"\s+", " ", str(query or "")).strip()
        query_tokens = _tokens(query_text)
        if not query_tokens:
            return []
        try:
            limit_value = _bounded_int(limit, 1, 25, _DEFAULT_CONTEXT_LIMIT)
            allowed_types = (
                {str(item).lower() for item in memory_types}
                if memory_types is not None
                else _MEMORY_TYPES
            )
            allowed_types &= _MEMORY_TYPES
            if not allowed_types:
                return []

            with self._connection() as connection:
                self._expire_in_connection(connection)
                placeholders = ",".join("?" for _ in allowed_types)
                rows = connection.execute(
                    f"""
                    SELECT * FROM memories
                     WHERE is_active = 1
                       AND memory_type IN ({placeholders})
                     ORDER BY importance DESC, updated_at DESC
                     LIMIT 2000
                    """,
                    tuple(sorted(allowed_types)),
                ).fetchall()

                ranked: List[tuple[float, sqlite3.Row]] = []
                query_lower = query_text.casefold()
                for row in rows:
                    content = str(row["content"] or "")
                    searchable = f"{row['memory_key']} {content}"
                    memory_tokens = _tokens(searchable)
                    overlap = query_tokens & memory_tokens
                    if not overlap:
                        continue

                    coverage = len(overlap) / max(1, len(query_tokens))
                    precision = len(overlap) / max(1, len(memory_tokens))
                    score = (0.72 * coverage) + (0.28 * precision)
                    if len(query_lower) > 5 and query_lower in content.casefold():
                        score += 0.15
                    score *= 0.85 + (int(row["importance"]) * 0.06)
                    if row["memory_type"] == "semantic":
                        score *= 1.04
                    if score >= minimum_score:
                        ranked.append((score, row))

                ranked.sort(
                    key=lambda pair: (
                        pair[0],
                        int(pair[1]["importance"]),
                        str(pair[1]["updated_at"]),
                    ),
                    reverse=True,
                )
                selected = ranked[:limit_value]
                if selected:
                    now = _iso(_utc_now())
                    connection.executemany(
                        "UPDATE memories SET last_accessed_at = ? WHERE id = ?",
                        [(now, str(row["id"])) for _, row in selected],
                    )
                result = []
                for score, row in selected:
                    item = self._row_to_dict(row)
                    item["relevance_score"] = round(score, 4)
                    result.append(item)
                return result
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            print(f"JARVIS memory retrieval unavailable: {exc}")
            return []

    def list_memories(
        self,
        *,
        memory_type: Optional[str] = None,
        include_inactive: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List saved memories for inspection and user-controlled cleanup."""
        if not self.enabled:
            return []
        try:
            limit_value = _bounded_int(limit, 1, 1000, 100)
            conditions: List[str] = []
            args: List[Any] = []
            if not include_inactive:
                conditions.append("is_active = 1")
            if memory_type:
                kind = str(memory_type).lower()
                if kind not in _MEMORY_TYPES:
                    return []
                conditions.append("memory_type = ?")
                args.append(kind)
            where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            with self._connection() as connection:
                self._expire_in_connection(connection)
                rows = connection.execute(
                    "SELECT * FROM memories" + where
                    + " ORDER BY updated_at DESC LIMIT ?",
                    (*args, limit_value),
                ).fetchall()
                return [self._row_to_dict(row) for row in rows]
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            print(f"JARVIS memory listing unavailable: {exc}")
            return []

    def forget_memory(
        self,
        *,
        memory_id: str = "",
        key: str = "",
    ) -> int:
        """Deactivate memories by id or semantic key; one selector is required."""
        selector = str(memory_id or "").strip()
        normalized_key = _normalize_key(key)
        if not self.enabled or (not selector and not normalized_key):
            return 0
        try:
            now = _iso(_utc_now())
            with self._connection() as connection:
                if selector:
                    cursor = connection.execute(
                        "UPDATE memories SET is_active = 0, updated_at = ? "
                        "WHERE id = ? AND is_active = 1",
                        (now, selector),
                    )
                else:
                    cursor = connection.execute(
                        "UPDATE memories SET is_active = 0, updated_at = ? "
                        "WHERE memory_key = ? AND is_active = 1",
                        (now, normalized_key),
                    )
                return int(cursor.rowcount or 0)
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            print(f"JARVIS memory forget operation unavailable: {exc}")
            return 0

    def clear_memories(self, *, memory_type: Optional[str] = None) -> int:
        """Deactivate all memories, optionally restricted to one memory type."""
        if not self.enabled:
            return 0
        if memory_type and memory_type not in _MEMORY_TYPES:
            return 0
        try:
            now = _iso(_utc_now())
            with self._connection() as connection:
                if memory_type:
                    cursor = connection.execute(
                        "UPDATE memories SET is_active = 0, updated_at = ? "
                        "WHERE is_active = 1 AND memory_type = ?",
                        (now, memory_type),
                    )
                else:
                    cursor = connection.execute(
                        "UPDATE memories SET is_active = 0, updated_at = ? "
                        "WHERE is_active = 1",
                        (now,),
                    )
                return int(cursor.rowcount or 0)
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            print(f"JARVIS memory clear operation unavailable: {exc}")
            return 0


memory_store = MemoryStore()


def remember(
    content: str,
    *,
    memory_type: str = "semantic",
    key: str = "",
    source: str = "user",
    conversation_id: str = "",
    confidence: float = 0.8,
    importance: int = 3,
    expires_in_days: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Public helper for adding/updating a memory."""
    return memory_store.save_memory(
        content,
        memory_type=memory_type,
        key=key,
        source=source,
        conversation_id=conversation_id,
        confidence=confidence,
        importance=importance,
        expires_in_days=expires_in_days,
        metadata=metadata,
    )


def record_episode(
    event: str,
    *,
    outcome: str = "",
    action_type: str = "",
    conversation_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    expires_in_days: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Persist a meaningful interaction event with a bounded retention period."""
    event_text = re.sub(r"\s+", " ", str(event or "")).strip()
    if not event_text:
        return None
    parts = []
    if action_type:
        parts.append(f"Action: {str(action_type).strip()[:100]}")
    parts.append(f"User request: {event_text[:400]}")
    if outcome:
        outcome_text = re.sub(r"\s+", " ", str(outcome)).strip()[:400]
        parts.append(f"Outcome: {outcome_text}")
    key_seed = f"{conversation_id}|{action_type}|{event_text}|{outcome}"
    key = "episode_" + uuid.uuid5(uuid.NAMESPACE_URL, key_seed).hex[:24]
    return remember(
        ". ".join(parts),
        memory_type="episodic",
        key=key,
        source="automation" if action_type else "interaction",
        conversation_id=conversation_id,
        confidence=0.95,
        importance=2 if action_type else 3,
        expires_in_days=expires_in_days,
        metadata=metadata or {},
    )


def build_memory_context(query: str, *, limit: Optional[int] = None) -> str:
    """Format only query-relevant memories for a prompt or contextual interpreter."""
    context_limit = (
        _bounded_int(
            os.getenv("JARVIS_MEMORY_CONTEXT_ITEMS", str(_DEFAULT_CONTEXT_LIMIT)),
            1,
            25,
            _DEFAULT_CONTEXT_LIMIT,
        )
        if limit is None
        else _bounded_int(limit, 1, 25, _DEFAULT_CONTEXT_LIMIT)
    )
    memories = memory_store.retrieve(query, limit=context_limit)
    if not memories:
        return ""
    lines = [
        "Relevant stored memory (may be incomplete or outdated; use only when relevant):"
    ]
    for item in memories:
        kind = str(item["memory_type"])
        lines.append(f"- [{kind}] {item['content']}")
    return "\n".join(lines)


def list_memories(
    *,
    memory_type: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    return memory_store.list_memories(
        memory_type=memory_type,
        include_inactive=include_inactive,
        limit=limit,
    )


def forget_memory(*, memory_id: str = "", key: str = "") -> int:
    return memory_store.forget_memory(memory_id=memory_id, key=key)


def clear_memories(*, memory_type: Optional[str] = None) -> int:
    return memory_store.clear_memories(memory_type=memory_type)


def _should_attempt_extraction(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if len(text) < 12 or len(text) > 2000 or _is_sensitive(text):
        return False
    return bool(_DURABLE_SIGNAL_PATTERN.search(text))


def _parse_memory_candidates(response: str) -> List[Dict[str, Any]]:
    value = str(response or "").strip()
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", value)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = payload.get("memories", [])
    else:
        return []
    return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []


def extract_memories_from_turn(
    user_text: str,
    assistant_text: str = "",
    *,
    conversation_id: str = "",
) -> List[Dict[str, Any]]:
    """Extract only high-confidence, durable, non-sensitive user-stated facts.

    The heuristic gate avoids an additional LLM call for ordinary questions and
    commands. Extraction failure never interrupts the main conversation.
    """
    if (
        not _env_flag("JARVIS_MEMORY_AUTO_EXTRACT", True)
        or not memory_store.enabled
        or not _should_attempt_extraction(user_text)
    ):
        return []

    prompt = f"""
You are the memory-extraction component of a personal desktop assistant.
Extract only durable, useful information explicitly stated by the USER in the
user message below. The assistant response is context only and is not evidence
that the user has a fact or preference.

Persist only:
- stable, non-sensitive facts explicitly stated by the user;
- enduring preferences and communication preferences;
- meaningful project context or ongoing work explicitly described by the user.

Do NOT store credentials, passwords, API keys, access tokens, financial account
details, health/medical information, religion, political affiliation, sexual
orientation, biometric information, secrets, speculation, one-off requests,
ordinary questions, or facts inferred only from the assistant response.
Do not convert a temporary task into a permanent fact. Prefer one concise
atomic memory per fact. Use a stable snake_case key so later statements can
update the same fact (examples: user.preferred_voice, user.response_style,
project.jarvis.stack). Return an empty memories list if nothing qualifies.
Output JSON only with this schema:
{{
  "memories": [
    {{
      "key": "stable_snake_case_key",
      "content": "concise fact phrased without uncertainty",
      "memory_type": "semantic",
      "confidence": 0.0,
      "importance": 1
    }}
  ]
}}
Confidence must be between 0 and 1; only emit facts with confidence >= 0.75.
Memory type must be semantic. Never output episodic entries here.

User message:
{str(user_text)[:2000]}

Assistant response (context only; do not use as evidence):
{str(assistant_text or '')[:2000]}
"""
    try:
        from engine.llm_client import ask_llm
        response = ask_llm(prompt)
        candidates = _parse_memory_candidates(response)
    except Exception as exc:
        print(f"JARVIS memory extraction unavailable: {exc}")
        return []

    saved: List[Dict[str, Any]] = []
    for candidate in candidates[:8]:
        content = str(candidate.get("content", "") or "").strip()
        key = str(candidate.get("key", "") or "").strip()
        kind = str(candidate.get("memory_type", "semantic") or "").lower()
        confidence = _bounded_float(candidate.get("confidence"), 0.0, 1.0, 0.0)
        importance = _bounded_int(candidate.get("importance"), 1, 5, 3)
        if kind != "semantic" or not key or not content or confidence < 0.75:
            continue
        if _is_sensitive(key) or _is_sensitive(content):
            continue
        item = remember(
            content,
            memory_type="semantic",
            key=key,
            source="user_statement",
            conversation_id=conversation_id,
            confidence=confidence,
            importance=importance,
        )
        if item:
            saved.append(item)
    return saved

"""
MongoDB integration for J.A.R.V.I.S. conversation history.

Responsibilities:
- Optional MongoDB integration.
- Discover MongoDB URI from environment or LibreChat/.env.
- Store individual JARVIS conversation turns.
- Associate turns with a conversation_id.
- Retrieve recent turns for conversational context.

MongoDB remains optional. If MongoDB is unavailable, JARVIS can
continue operating with in-memory conversation context.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


_MONGO_AVAILABLE = False
_client = None
_db = None
_collection = None


def _parse_dotenv_file(path: str) -> Dict[str, str]:
    """Parse a simple .env file into a dictionary."""
    env: Dict[str, str] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()

                if not s or s.startswith("#"):
                    continue

                if "=" not in s:
                    continue

                key, val = s.split("=", 1)

                key = key.strip()
                val = val.strip().strip('"').strip("'")

                env[key] = val

    except Exception:
        pass

    return env


def _discover_mongo_uri() -> Optional[str]:
    """Find the MongoDB connection URI."""
    # 1. Environment variables.
    uri = (
        os.environ.get("MONGODB_URI")
        or os.environ.get("MONGO_URI")
    )

    if uri:
        return uri

    # 2. LibreChat/.env in the JARVIS project.
    try:
        engine_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        project_root = os.path.dirname(engine_dir)

        lc_env_path = os.path.join(
            project_root,
            "LibreChat",
            ".env",
        )

        if os.path.isfile(lc_env_path):
            envmap = _parse_dotenv_file(
                lc_env_path
            )

            uri = (
                envmap.get("MONGODB_URI")
                or envmap.get("MONGO_URI")
            )

            if uri:
                return uri

    except Exception:
        pass

    return None


def init_db() -> bool:
    """Initialize the MongoDB connection."""
    global _MONGO_AVAILABLE
    global _client
    global _db
    global _collection

    try:
        from pymongo import MongoClient  # type: ignore
    except Exception:
        _MONGO_AVAILABLE = False
        return False

    uri = _discover_mongo_uri()

    if not uri:
        _MONGO_AVAILABLE = False
        return False

    try:
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=2000,
        )

        # Trigger server selection immediately.
        _client.admin.command("ping")

        # Select database.
        db_name_env = os.environ.get(
            "JARVIS_DB_NAME"
        )

        if db_name_env:
            _db = _client.get_database(
                db_name_env
            )

        else:
            try:
                _db = _client.get_default_database()
            except Exception:
                _db = None

            if _db is None:
                _db = _client.get_database(
                    "jarvis"
                )

        collection_name = os.environ.get(
            "JARVIS_CHAT_COLLECTION",
            "chats",
        )

        _collection = _db.get_collection(
            collection_name
        )

        _MONGO_AVAILABLE = True

        return True

    except Exception:
        _MONGO_AVAILABLE = False
        return False


def save_chat_turn(
    user_text: str,
    assistant_text: str,
    model: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
) -> None:
    """
    Save one user/assistant conversation turn.

    MongoDB remains optional. If it is unavailable, this
    function quietly does nothing so the voice flow is not
    interrupted.
    """

    if not _MONGO_AVAILABLE or _collection is None:
        return

    try:
        doc = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "conversation_id": (
                conversation_id or ""
            ),

            "model": (
                model
                or os.environ.get(
                    "JARVIS_MODEL",
                    "gemini-2.5-flash-lite",
                )
            ),

            "user_text": user_text or "",

            "assistant_text": (
                assistant_text or ""
            ),

            "meta": meta or {},
        }

        _collection.insert_one(doc)

    except Exception:
        # Database failures must never break
        # JARVIS conversational flow.
        pass


def get_chat_turns(
    conversation_id: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent conversation turns.

    Results are returned in chronological order:
    oldest -> newest.

    Only turns belonging to the supplied
    conversation_id are returned.
    """

    if not conversation_id:
        return []

    if not _MONGO_AVAILABLE or _collection is None:
        return []

    try:
        safe_limit = max(1, int(limit))

        documents = list(
            _collection.find(
                {
                    "conversation_id": conversation_id,
                },
                {
                    "_id": 0,
                    "timestamp": 1,
                    "conversation_id": 1,
                    "model": 1,
                    "user_text": 1,
                    "assistant_text": 1,
                    "meta": 1,
                },
            )
            .sort(
                "timestamp",
                -1,
            )
            .limit(safe_limit)
        )

        # MongoDB returns newest first. The LLM
        # needs the conversation in natural order.
        documents.reverse()

        return documents

    except Exception as exc:
        print(
            f"MongoDB history retrieval error: {exc}"
        )

        return []

def get_recent_conversations(
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return recent conversations grouped by conversation_id.

    Each result contains:
    - conversation_id
    - title
    - created_at
    - updated_at
    - message_count

    Conversations are ordered from newest activity to oldest.
    """

    if not _MONGO_AVAILABLE or _collection is None:
        return []

    try:
        safe_limit = max(1, int(limit))

        pipeline = [
            {
                "$match": {
                    "conversation_id": {
                        "$exists": True,
                        "$ne": "",
                    }
                }
            },
            {
                "$sort": {
                    "timestamp": 1,
                }
            },
            {
                "$group": {
                    "_id": "$conversation_id",

                    "created_at": {
                        "$first": "$timestamp",
                    },

                    "updated_at": {
                        "$last": "$timestamp",
                    },

                    "title": {
                        "$first": "$user_text",
                    },

                    "message_count": {
                        "$sum": 1,
                    },
                }
            },
            {
                "$sort": {
                    "updated_at": -1,
                }
            },
            {
                "$limit": safe_limit,
            },
            {
                "$project": {
                    "_id": 0,
                    "conversation_id": "$_id",
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "message_count": 1,
                }
            },
        ]

        return list(
            _collection.aggregate(pipeline)
        )

    except Exception as exc:
        print(
            f"MongoDB conversation listing error: {exc}"
        )
        return []


def get_conversation(
    conversation_id: str,
) -> List[Dict[str, Any]]:
    """
    Retrieve all saved turns belonging to one conversation.

    Results are returned chronologically:
    oldest -> newest.
    """

    if not conversation_id:
        return []

    if not _MONGO_AVAILABLE or _collection is None:
        return []

    try:
        documents = list(
            _collection.find(
                {
                    "conversation_id": conversation_id,
                },
                {
                    "_id": 0,
                    "timestamp": 1,
                    "conversation_id": 1,
                    "model": 1,
                    "user_text": 1,
                    "assistant_text": 1,
                    "meta": 1,
                },
            ).sort(
                "timestamp",
                1,
            )
        )

        return documents

    except Exception as exc:
        print(
            f"MongoDB conversation retrieval error: {exc}"
        )
        return []

# Attempt initialization when imported.
try:
    init_db()
except Exception:
    pass
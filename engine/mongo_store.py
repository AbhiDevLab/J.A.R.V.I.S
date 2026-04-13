"""
Minimal MongoDB integration for JARVIS chat history.

- Safe optional import: if pymongo isn't installed or no URI is found, functions become no-ops.
- Auto-detect MongoDB URI from:
  1) Env: MONGODB_URI or MONGO_URI
  2) LibreChat/.env in this repo (keys: MONGODB_URI or MONGO_URI)
  - librechat.yaml typically doesn't define MongoDB; LibreChat uses .env -> MONGO_URI.
- Collections:
  - db_name: from JARVIS_DB_NAME if set, else default DB from URI, else 'jarvis'
  - collection: from JARVIS_CHAT_COLLECTION (default 'chats')
- Document shape:
  {
    "timestamp": <ISO 8601 string>,
    "model": "mistral",
    "user_text": "...",
    "assistant_text": "...",
    "meta": {...}
  }

Setup:
- Install MongoDB and pymongo: `pip install pymongo` (ideally in your envjarvis)
- Start MongoDB locally or use Atlas; set env var MONGODB_URI accordingly.
  Windows PowerShell example:
  $env:MONGODB_URI = "mongodb://localhost:27017/LibreChat"

"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

_MONGO_AVAILABLE = False
_client = None
_db = None
_collection = None


def _parse_dotenv_file(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if '=' not in s:
                    continue
                key, val = s.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                env[key] = val
    except Exception:
        pass
    return env


def _discover_mongo_uri() -> Optional[str]:
    # 1) Env variables
    uri = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URI')
    if uri:
        return uri

    # 2) LibreChat/.env in repo
    try:
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(engine_dir)
        lc_env_path = os.path.join(project_root, 'LibreChat', '.env')
        if os.path.isfile(lc_env_path):
            envmap = _parse_dotenv_file(lc_env_path)
            uri = envmap.get('MONGODB_URI') or envmap.get('MONGO_URI')
            if uri:
                return uri
    except Exception:
        pass

    return None


def init_db() -> bool:
    global _MONGO_AVAILABLE, _client, _db, _collection
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
        _client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        # Trigger server selection
        _client.admin.command('ping')

        # Choose DB: env overrides URI default, otherwise fallback
        db_name_env = os.environ.get('JARVIS_DB_NAME')
        if db_name_env:
            _db = _client.get_database(db_name_env)
        else:
            try:
                _db = _client.get_default_database()  # type: ignore[attr-defined]
            except Exception:
                _db = None
            if _db is None:
                _db = _client.get_database('jarvis')

        collection_name = os.environ.get('JARVIS_CHAT_COLLECTION', 'chats')
        _collection = _db.get_collection(collection_name)
        _MONGO_AVAILABLE = True
        return True
    except Exception:
        _MONGO_AVAILABLE = False
        return False


def save_chat_turn(user_text: str, assistant_text: str, model: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    """Save a single chat turn. No-op if Mongo is not available."""
    if not (_MONGO_AVAILABLE and _collection):
        return
    try:
        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        # Default model should reflect the project's configured assistant.
        # Prefer explicit JARVIS_MODEL env var; fall back to the Gemini client model name.
        "model": model or os.environ.get("JARVIS_MODEL", "gemini-2.5-flash-lite"),
            "user_text": user_text or "",
            "assistant_text": assistant_text or "",
            "meta": meta or {},
        }
        _collection.insert_one(doc)
    except Exception:
        # Intentionally swallow errors to avoid breaking voice flow
        pass


# Attempt to initialize on import so it's ready if env is configured
try:
    init_db()
except Exception:
    pass

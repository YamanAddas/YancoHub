"""
YancoHub Chat History — Persistent storage for CatByte conversation sessions.
"""

import json
import time
import secrets
import logging
import threading
from pathlib import Path

logger = logging.getLogger('yancohub.chathistory')

DATA_FILE = Path(__file__).parent / 'catbyte_history.json'
MAX_SESSIONS = 50


class ChatHistory:
    def __init__(self, data_file: Path = None):
        self.data_file = data_file or DATA_FILE
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data.setdefault('sessions', {})
                data.setdefault('active_session_id', None)
                return data
            except Exception as e:
                logger.error(f"Failed to load chat history: {e}")
        return {'sessions': {}, 'active_session_id': None}

    def _save(self):
        """Write data to disk. Caller must hold self._lock."""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")

    def _generate_id(self) -> str:
        return f"cb_{int(time.time()):x}_{secrets.token_hex(4)}"

    def _prune_sessions(self):
        """Remove oldest unpinned sessions when over MAX_SESSIONS. Caller must hold lock."""
        sessions = self.data['sessions']
        if len(sessions) <= MAX_SESSIONS:
            return
        unpinned = [
            (sid, s) for sid, s in sessions.items() if not s.get('pinned')
        ]
        unpinned.sort(key=lambda x: x[1].get('updated_at', 0))
        while len(sessions) > MAX_SESSIONS and unpinned:
            sid, _ = unpinned.pop(0)
            del sessions[sid]
            logger.info(f"Pruned old chat session: {sid}")

    # ── Session CRUD ────────────────────────────────────────────────────────

    def create_session(self, game_context: str = '', model: str = '') -> dict:
        session_id = self._generate_id()
        now = time.time()
        title = f"Chat about {game_context}" if game_context else "New conversation"
        session = {
            'id': session_id,
            'title': title,
            'created_at': now,
            'updated_at': now,
            'game_context': game_context,
            'model': model,
            'pinned': False,
            'messages': [],
        }
        with self._lock:
            self.data['sessions'][session_id] = session
            self.data['active_session_id'] = session_id
            self._prune_sessions()
            self._save()
        return dict(session)

    def get_session(self, session_id: str) -> dict | None:
        session = self.data['sessions'].get(session_id)
        if session:
            return dict(session)
        return None

    def list_sessions(self) -> list:
        """Return session summaries (no messages) sorted: pinned first, then by updated_at desc."""
        result = []
        for s in self.data['sessions'].values():
            messages = s.get('messages', [])
            preview = ''
            if messages:
                first_user = next((m['content'] for m in messages if m['role'] == 'user'), '')
                preview = first_user[:60]
            result.append({
                'id': s['id'],
                'title': s.get('title', 'New conversation'),
                'created_at': s.get('created_at', 0),
                'updated_at': s.get('updated_at', 0),
                'preview': preview,
                'pinned': s.get('pinned', False),
                'model': s.get('model', ''),
                'message_count': len(messages),
            })
        result.sort(key=lambda x: (not x['pinned'], -x['updated_at']))
        return result

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self.data['sessions']:
                del self.data['sessions'][session_id]
                if self.data['active_session_id'] == session_id:
                    self.data['active_session_id'] = None
                self._save()
                return True
        return False

    def rename_session(self, session_id: str, title: str) -> bool:
        with self._lock:
            session = self.data['sessions'].get(session_id)
            if session:
                session['title'] = title.strip()[:100]
                self._save()
                return True
        return False

    def toggle_pin(self, session_id: str) -> bool | None:
        with self._lock:
            session = self.data['sessions'].get(session_id)
            if session:
                session['pinned'] = not session.get('pinned', False)
                self._save()
                return session['pinned']
        return None

    # ── Messages ────────────────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> dict | None:
        with self._lock:
            session = self.data['sessions'].get(session_id)
            if not session:
                return None
            msg = {'role': role, 'content': content, 'ts': time.time()}
            session['messages'].append(msg)
            session['updated_at'] = msg['ts']
            self._save()
            return dict(msg)

    def get_messages_for_llm(self, session_id: str, limit: int = 20) -> list:
        """Get recent messages formatted for LLM context (role + content only)."""
        session = self.data['sessions'].get(session_id)
        if not session:
            return []
        messages = session.get('messages', [])
        recent = messages[-limit:] if len(messages) > limit else messages
        return [{'role': m['role'], 'content': m['content']} for m in recent]

    # ── Active Session ──────────────────────────────────────────────────────

    def get_active_session_id(self) -> str | None:
        return self.data.get('active_session_id')

    def set_active_session(self, session_id: str | None):
        with self._lock:
            self.data['active_session_id'] = session_id
            self._save()

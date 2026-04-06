"""Tests for chathistory.py — CatByte conversation session management."""

import time


class TestSessionCRUD:
    def test_create_session(self, chat_history_instance):
        session = chat_history_instance.create_session()
        assert 'id' in session
        assert session['id'].startswith('cb_')
        assert session['messages'] == []
        assert session['pinned'] is False

    def test_create_session_with_context(self, chat_history_instance):
        session = chat_history_instance.create_session(game_context='Hades')
        assert 'Hades' in session['title']

    def test_get_session(self, chat_history_instance):
        created = chat_history_instance.create_session()
        fetched = chat_history_instance.get_session(created['id'])
        assert fetched is not None
        assert fetched['id'] == created['id']

    def test_get_nonexistent_session(self, chat_history_instance):
        assert chat_history_instance.get_session('nonexistent') is None

    def test_delete_session(self, chat_history_instance):
        session = chat_history_instance.create_session()
        assert chat_history_instance.delete_session(session['id']) is True
        assert chat_history_instance.get_session(session['id']) is None

    def test_delete_nonexistent_session(self, chat_history_instance):
        assert chat_history_instance.delete_session('nonexistent') is False

    def test_delete_active_session_clears_active(self, chat_history_instance):
        session = chat_history_instance.create_session()
        assert chat_history_instance.get_active_session_id() == session['id']
        chat_history_instance.delete_session(session['id'])
        assert chat_history_instance.get_active_session_id() is None

    def test_rename_session(self, chat_history_instance):
        session = chat_history_instance.create_session()
        assert chat_history_instance.rename_session(session['id'], 'My Custom Title') is True
        updated = chat_history_instance.get_session(session['id'])
        assert updated['title'] == 'My Custom Title'

    def test_rename_truncates_long_title(self, chat_history_instance):
        session = chat_history_instance.create_session()
        chat_history_instance.rename_session(session['id'], 'A' * 200)
        updated = chat_history_instance.get_session(session['id'])
        assert len(updated['title']) == 100

    def test_rename_nonexistent_returns_false(self, chat_history_instance):
        assert chat_history_instance.rename_session('nope', 'title') is False


class TestSessionPinning:
    def test_toggle_pin(self, chat_history_instance):
        session = chat_history_instance.create_session()
        result = chat_history_instance.toggle_pin(session['id'])
        assert result is True
        result = chat_history_instance.toggle_pin(session['id'])
        assert result is False

    def test_toggle_pin_nonexistent(self, chat_history_instance):
        assert chat_history_instance.toggle_pin('nope') is None


class TestMessages:
    def test_add_message(self, chat_history_instance):
        session = chat_history_instance.create_session()
        msg = chat_history_instance.add_message(session['id'], 'user', 'Hello!')
        assert msg is not None
        assert msg['role'] == 'user'
        assert msg['content'] == 'Hello!'
        assert 'ts' in msg

    def test_add_message_to_nonexistent(self, chat_history_instance):
        assert chat_history_instance.add_message('nope', 'user', 'Hi') is None

    def test_messages_persist_in_session(self, chat_history_instance):
        session = chat_history_instance.create_session()
        chat_history_instance.add_message(session['id'], 'user', 'Hello')
        chat_history_instance.add_message(session['id'], 'assistant', 'Hi there!')
        fetched = chat_history_instance.get_session(session['id'])
        assert len(fetched['messages']) == 2

    def test_add_message_updates_timestamp(self, chat_history_instance):
        session = chat_history_instance.create_session()
        original_time = session['updated_at']
        time.sleep(0.01)
        chat_history_instance.add_message(session['id'], 'user', 'Hello')
        updated = chat_history_instance.get_session(session['id'])
        assert updated['updated_at'] > original_time


class TestGetMessagesForLLM:
    def test_returns_role_content_only(self, chat_history_instance):
        session = chat_history_instance.create_session()
        chat_history_instance.add_message(session['id'], 'user', 'Hello')
        chat_history_instance.add_message(session['id'], 'assistant', 'Hi!')
        messages = chat_history_instance.get_messages_for_llm(session['id'])
        assert len(messages) == 2
        for msg in messages:
            assert set(msg.keys()) == {'role', 'content'}

    def test_respects_limit(self, chat_history_instance):
        session = chat_history_instance.create_session()
        for i in range(30):
            chat_history_instance.add_message(session['id'], 'user', f'msg {i}')
        messages = chat_history_instance.get_messages_for_llm(session['id'], limit=10)
        assert len(messages) == 10
        # Should be the LAST 10 messages
        assert messages[0]['content'] == 'msg 20'

    def test_nonexistent_session_returns_empty(self, chat_history_instance):
        assert chat_history_instance.get_messages_for_llm('nope') == []


class TestListSessions:
    def test_list_empty(self, chat_history_instance):
        assert chat_history_instance.list_sessions() == []

    def test_list_returns_summaries(self, chat_history_instance):
        chat_history_instance.create_session()
        sessions = chat_history_instance.list_sessions()
        assert len(sessions) == 1
        assert 'id' in sessions[0]
        assert 'message_count' in sessions[0]
        # Should NOT include full messages
        assert 'messages' not in sessions[0]

    def test_pinned_sessions_first(self, chat_history_instance):
        s1 = chat_history_instance.create_session()
        time.sleep(0.01)
        s2 = chat_history_instance.create_session()
        chat_history_instance.toggle_pin(s1['id'])
        sessions = chat_history_instance.list_sessions()
        assert sessions[0]['id'] == s1['id']
        assert sessions[0]['pinned'] is True

    def test_preview_from_first_user_message(self, chat_history_instance):
        session = chat_history_instance.create_session()
        chat_history_instance.add_message(session['id'], 'user', 'What is Hades about?')
        sessions = chat_history_instance.list_sessions()
        assert 'Hades' in sessions[0]['preview']


class TestSessionPruning:
    def test_prunes_when_over_max(self, chat_history_instance):
        from chathistory import MAX_SESSIONS
        for i in range(MAX_SESSIONS + 5):
            chat_history_instance.create_session()
        sessions = chat_history_instance.list_sessions()
        assert len(sessions) <= MAX_SESSIONS

    def test_pinned_sessions_survive_pruning(self, chat_history_instance):
        from chathistory import MAX_SESSIONS
        first = chat_history_instance.create_session()
        chat_history_instance.toggle_pin(first['id'])
        for i in range(MAX_SESSIONS + 5):
            chat_history_instance.create_session()
        session = chat_history_instance.get_session(first['id'])
        assert session is not None


class TestActiveSession:
    def test_create_sets_active(self, chat_history_instance):
        session = chat_history_instance.create_session()
        assert chat_history_instance.get_active_session_id() == session['id']

    def test_set_active_session(self, chat_history_instance):
        s1 = chat_history_instance.create_session()
        s2 = chat_history_instance.create_session()
        chat_history_instance.set_active_session(s1['id'])
        assert chat_history_instance.get_active_session_id() == s1['id']

    def test_set_active_none(self, chat_history_instance):
        chat_history_instance.create_session()
        chat_history_instance.set_active_session(None)
        assert chat_history_instance.get_active_session_id() is None

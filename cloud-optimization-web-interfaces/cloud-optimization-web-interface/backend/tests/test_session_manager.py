"""
Tests for the Session Manager.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from ..services.session_manager import SessionManager
from ..models.data_models import ChatMessage, ChatSession


@pytest.fixture
def session_manager():
    """Create SessionManager instance for testing."""
    return SessionManager(session_ttl_hours=1, cleanup_interval_hours=1)


class TestSessionManager:
    """Test cases for SessionManager."""

    def test_init(self):
        """Test SessionManager initialization."""
        manager = SessionManager(session_ttl_hours=2, cleanup_interval_hours=3)
        
        assert manager.session_ttl == timedelta(hours=2)
        assert manager.cleanup_interval == timedelta(hours=3)
        assert manager.sessions == {}

    def test_create_session_new(self, session_manager):
        """Test creating a new session."""
        session = session_manager.create_session("test-session")
        
        assert session.session_id == "test-session"
        assert session.selected_agent is None
        assert session.messages == []
        assert session.context == {}
        assert "test-session" in session_manager.sessions

    def test_create_session_existing(self, session_manager):
        """Test creating session that already exists."""
        # Create first session
        session1 = session_manager.create_session("test-session")
        
        # Try to create same session again
        session2 = session_manager.create_session("test-session")
        
        assert session1 is session2
        assert len(session_manager.sessions) == 1

    def test_create_session_auto_id(self, session_manager):
        """Test creating session with auto-generated ID."""
        session = session_manager.create_session()
        
        assert session.session_id is not None
        assert len(session.session_id) > 10  # UUID should be longer
        assert session.session_id in session_manager.sessions

    def test_get_session_existing(self, session_manager):
        """Test getting an existing session."""
        # Create session
        original_session = session_manager.create_session("test-session")
        
        # Get session
        retrieved_session = session_manager.get_session("test-session")
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == "test-session"
        assert retrieved_session is original_session

    def test_get_session_nonexistent(self, session_manager):
        """Test getting a non-existent session."""
        session = session_manager.get_session("nonexistent")
        
        assert session is None

    def test_get_session_expired(self, session_manager):
        """Test getting an expired session."""
        # Create session
        session = session_manager.create_session("test-session")
        
        # Make session expired
        session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        # Try to get expired session
        retrieved_session = session_manager.get_session("test-session")
        
        assert retrieved_session is None
        assert "test-session" not in session_manager.sessions

    def test_update_session_success(self, session_manager):
        """Test successful session update."""
        # Create session
        session_manager.create_session("test-session")
        
        # Update session
        success = session_manager.update_session(
            "test-session",
            selected_agent="test-agent",
            context={"key": "value"}
        )
        
        assert success is True
        
        session = session_manager.get_session("test-session")
        assert session.selected_agent == "test-agent"
        assert session.context["key"] == "value"

    def test_update_session_nonexistent(self, session_manager):
        """Test updating non-existent session."""
        success = session_manager.update_session("nonexistent", selected_agent="test-agent")
        
        assert success is False

    def test_add_message_success(self, session_manager):
        """Test successfully adding message to session."""
        # Create session
        session_manager.create_session("test-session")
        
        # Add message
        message = ChatMessage(role="user", content="Hello")
        success = session_manager.add_message("test-session", message)
        
        assert success is True
        
        session = session_manager.get_session("test-session")
        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"

    def test_add_message_nonexistent_session(self, session_manager):
        """Test adding message to non-existent session."""
        message = ChatMessage(role="user", content="Hello")
        success = session_manager.add_message("nonexistent", message)
        
        assert success is False

    def test_add_message_limit(self, session_manager):
        """Test message limit enforcement."""
        # Create session
        session_manager.create_session("test-session")
        
        # Add many messages (more than limit)
        for i in range(150):  # More than max_messages (100)
            message = ChatMessage(role="user", content=f"Message {i}")
            session_manager.add_message("test-session", message)
        
        session = session_manager.get_session("test-session")
        assert len(session.messages) <= 100

    def test_get_conversation_history(self, session_manager):
        """Test getting conversation history."""
        # Create session and add messages
        session_manager.create_session("test-session")
        
        messages = [
            ChatMessage(role="system", content="System message"),
            ChatMessage(role="user", content="User message"),
            ChatMessage(role="assistant", content="Assistant message")
        ]
        
        for msg in messages:
            session_manager.add_message("test-session", msg)
        
        # Get all messages
        history = session_manager.get_conversation_history("test-session")
        assert len(history) == 3
        
        # Get limited messages
        history_limited = session_manager.get_conversation_history("test-session", limit=2)
        assert len(history_limited) == 2
        
        # Get without system messages
        history_no_system = session_manager.get_conversation_history(
            "test-session", include_system=False
        )
        assert len(history_no_system) == 2
        assert all(msg.role != "system" for msg in history_no_system)    def 
test_delete_session_success(self, session_manager):
        """Test successful session deletion."""
        # Create session
        session_manager.create_session("test-session")
        
        # Delete session
        success = session_manager.delete_session("test-session")
        
        assert success is True
        assert "test-session" not in session_manager.sessions

    def test_delete_session_nonexistent(self, session_manager):
        """Test deleting non-existent session."""
        success = session_manager.delete_session("nonexistent")
        
        assert success is False

    def test_list_sessions_active_only(self, session_manager):
        """Test listing active sessions only."""
        # Create sessions
        session_manager.create_session("active-session")
        session_manager.create_session("expired-session")
        
        # Make one session expired
        expired_session = session_manager.sessions["expired-session"]
        expired_session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        # List active sessions
        active_sessions = session_manager.list_sessions(active_only=True)
        
        assert "active-session" in active_sessions
        assert "expired-session" not in active_sessions

    def test_list_sessions_all(self, session_manager):
        """Test listing all sessions."""
        # Create sessions
        session_manager.create_session("session1")
        session_manager.create_session("session2")
        
        # List all sessions
        all_sessions = session_manager.list_sessions(active_only=False)
        
        assert len(all_sessions) == 2
        assert "session1" in all_sessions
        assert "session2" in all_sessions

    def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired sessions."""
        # Create sessions
        session_manager.create_session("active-session")
        session_manager.create_session("expired-session1")
        session_manager.create_session("expired-session2")
        
        # Make some sessions expired
        for session_id in ["expired-session1", "expired-session2"]:
            session = session_manager.sessions[session_id]
            session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        # Run cleanup
        cleaned_count = session_manager.cleanup_expired_sessions()
        
        assert cleaned_count == 2
        assert "active-session" in session_manager.sessions
        assert "expired-session1" not in session_manager.sessions
        assert "expired-session2" not in session_manager.sessions

    def test_get_session_stats(self, session_manager):
        """Test getting session statistics."""
        # Create sessions with messages
        session_manager.create_session("session1")
        session_manager.create_session("session2")
        
        # Add messages
        for i in range(5):
            message = ChatMessage(role="user", content=f"Message {i}")
            session_manager.add_message("session1", message)
        
        # Get stats
        stats = session_manager.get_session_stats()
        
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2
        assert stats["total_messages"] == 5
        assert stats["average_messages_per_session"] == 2.5
        assert "session_ttl_hours" in stats

    def test_get_session_context(self, session_manager):
        """Test getting session context."""
        # Create session
        session = session_manager.create_session("test-session")
        session.selected_agent = "test-agent"
        session.context = {"key": "value"}
        
        # Add message
        message = ChatMessage(role="user", content="Hello")
        session_manager.add_message("test-session", message)
        
        # Get context
        context = session_manager.get_session_context("test-session")
        
        assert context["session_id"] == "test-session"
        assert context["selected_agent"] == "test-agent"
        assert context["message_count"] == 1
        assert context["context"]["key"] == "value"
        assert "session_age_minutes" in context
        assert "last_activity_minutes" in context

    def test_get_session_context_nonexistent(self, session_manager):
        """Test getting context for non-existent session."""
        context = session_manager.get_session_context("nonexistent")
        
        assert context == {}

    def test_is_session_expired(self, session_manager):
        """Test session expiration check."""
        # Create session
        session = session_manager.create_session("test-session")
        
        # Fresh session should not be expired
        assert not session_manager._is_session_expired(session)
        
        # Make session expired
        session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        # Expired session should be expired
        assert session_manager._is_session_expired(session)

    def test_maybe_cleanup_sessions(self, session_manager):
        """Test conditional session cleanup."""
        # Set last cleanup to long ago
        session_manager.last_cleanup = datetime.utcnow() - timedelta(hours=2)
        
        # Create expired session
        session_manager.create_session("expired-session")
        expired_session = session_manager.sessions["expired-session"]
        expired_session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        # Trigger cleanup
        session_manager._maybe_cleanup_sessions()
        
        # Expired session should be cleaned up
        assert "expired-session" not in session_manager.sessions
"""
Session Manager for handling chat sessions and conversation context.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.data_models import ChatSession, ChatMessage


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions and conversation context."""
    
    def __init__(self, session_ttl_hours: int = 24, cleanup_interval_hours: int = 6):
        """
        Initialize the Session Manager.
        
        Args:
            session_ttl_hours: Session time-to-live in hours
            cleanup_interval_hours: How often to run cleanup in hours
        """
        self.session_ttl = timedelta(hours=session_ttl_hours)
        self.cleanup_interval = timedelta(hours=cleanup_interval_hours)
        
        # In-memory session storage
        self.sessions: Dict[str, ChatSession] = {}
        self.last_cleanup = datetime.utcnow()
        
        logger.info(f"SessionManager initialized with {session_ttl_hours}h TTL")

    def create_session(self, session_id: Optional[str] = None) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            session_id: Optional session ID, generates UUID if not provided
            
        Returns:
            ChatSession object
        """
        try:
            if session_id is None:
                session_id = str(uuid.uuid4())
            
            # Check if session already exists
            if session_id in self.sessions:
                logger.debug(f"Session {session_id} already exists, returning existing session")
                return self.sessions[session_id]
            
            # Create new session
            session = ChatSession(
                session_id=session_id,
                selected_agent=None,
                messages=[],
                context={},
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
            
            self.sessions[session_id] = session
            logger.debug(f"Created new session: {session_id}")
            
            # Trigger cleanup if needed
            self._maybe_cleanup_sessions()
            
            return session
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get an existing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatSession object or None if not found
        """
        try:
            session = self.sessions.get(session_id)
            
            if session:
                # Check if session is expired
                if self._is_session_expired(session):
                    logger.debug(f"Session {session_id} has expired, removing")
                    del self.sessions[session_id]
                    return None
                
                # Update last activity
                session.last_activity = datetime.utcnow()
                logger.debug(f"Retrieved session: {session_id}")
                return session
            
            logger.debug(f"Session not found: {session_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None

    def update_session(self, session_id: str, **kwargs) -> bool:
        """
        Update session properties.
        
        Args:
            session_id: Session identifier
            **kwargs: Properties to update
            
        Returns:
            True if session was updated, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False
            
            # Update allowed properties
            if 'selected_agent' in kwargs:
                session.selected_agent = kwargs['selected_agent']
            
            if 'context' in kwargs:
                session.context.update(kwargs['context'])
            
            session.last_activity = datetime.utcnow()
            logger.debug(f"Updated session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False

    def add_message(self, session_id: str, message: ChatMessage) -> bool:
        """
        Add a message to session conversation history.
        
        Args:
            session_id: Session identifier
            message: ChatMessage to add
            
        Returns:
            True if message was added, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                logger.warning(f"Cannot add message to non-existent session: {session_id}")
                return False
            
            session.messages.append(message)
            session.last_activity = datetime.utcnow()
            
            # Limit conversation history to prevent memory issues
            max_messages = 100
            if len(session.messages) > max_messages:
                # Keep system messages and recent messages
                system_messages = [msg for msg in session.messages if msg.role == "system"]
                recent_messages = [msg for msg in session.messages if msg.role != "system"][-max_messages:]
                session.messages = system_messages + recent_messages
                logger.debug(f"Trimmed session {session_id} messages to {len(session.messages)}")
            
            logger.debug(f"Added message to session {session_id} (total: {len(session.messages)})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding message to session {session_id}: {e}")
            return False

    def get_conversation_history(
        self, 
        session_id: str, 
        limit: Optional[int] = None,
        include_system: bool = True
    ) -> List[ChatMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            include_system: Whether to include system messages
            
        Returns:
            List of ChatMessage objects
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return []
            
            messages = session.messages
            
            # Filter system messages if requested
            if not include_system:
                messages = [msg for msg in messages if msg.role != "system"]
            
            # Apply limit
            if limit and len(messages) > limit:
                messages = messages[-limit:]
            
            logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error getting conversation history for session {session_id}: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False otherwise
        """
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.debug(f"Deleted session: {session_id}")
                return True
            else:
                logger.debug(f"Session not found for deletion: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def list_sessions(self, active_only: bool = True) -> List[str]:
        """
        List all session IDs.
        
        Args:
            active_only: Only return non-expired sessions
            
        Returns:
            List of session IDs
        """
        try:
            if active_only:
                # Filter out expired sessions
                active_sessions = []
                for session_id, session in self.sessions.items():
                    if not self._is_session_expired(session):
                        active_sessions.append(session_id)
                return active_sessions
            else:
                return list(self.sessions.keys())
                
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                if self._is_session_expired(session):
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                del self.sessions[session_id]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
            self.last_cleanup = datetime.utcnow()
            return len(expired_sessions)
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            return 0

    def get_session_stats(self) -> Dict[str, any]:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            total_sessions = len(self.sessions)
            active_sessions = len(self.list_sessions(active_only=True))
            expired_sessions = total_sessions - active_sessions
            
            # Calculate average messages per session
            total_messages = sum(len(session.messages) for session in self.sessions.values())
            avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
            
            # Find oldest and newest sessions
            if self.sessions:
                oldest_session = min(self.sessions.values(), key=lambda s: s.created_at)
                newest_session = max(self.sessions.values(), key=lambda s: s.created_at)
                oldest_age = (datetime.utcnow() - oldest_session.created_at).total_seconds() / 3600
                newest_age = (datetime.utcnow() - newest_session.created_at).total_seconds() / 3600
            else:
                oldest_age = newest_age = 0
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "expired_sessions": expired_sessions,
                "total_messages": total_messages,
                "average_messages_per_session": round(avg_messages, 1),
                "oldest_session_age_hours": round(oldest_age, 1),
                "newest_session_age_hours": round(newest_age, 1),
                "session_ttl_hours": self.session_ttl.total_seconds() / 3600,
                "last_cleanup": self.last_cleanup.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "expired_sessions": 0,
                "error": str(e)
            }

    def _is_session_expired(self, session: ChatSession) -> bool:
        """Check if a session has expired."""
        return datetime.utcnow() - session.last_activity > self.session_ttl

    def _maybe_cleanup_sessions(self) -> None:
        """Run cleanup if enough time has passed."""
        if datetime.utcnow() - self.last_cleanup > self.cleanup_interval:
            self.cleanup_expired_sessions()

    def get_session_context(self, session_id: str) -> Dict[str, any]:
        """
        Get session context for query processing.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session context
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return {}
            
            return {
                "session_id": session_id,
                "selected_agent": session.selected_agent,
                "message_count": len(session.messages),
                "session_age_minutes": (datetime.utcnow() - session.created_at).total_seconds() / 60,
                "last_activity_minutes": (datetime.utcnow() - session.last_activity).total_seconds() / 60,
                "context": session.context
            }
            
        except Exception as e:
            logger.error(f"Error getting session context for {session_id}: {e}")
            return {}
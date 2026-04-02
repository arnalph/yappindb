"""
Session manager for handling file uploads and temp file lifecycle.
Each session gets a unique ID and associated temp files.
"""

import os
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import threading


class Session:
    """Represents a user session with associated files."""

    def __init__(self, session_id: str, ttl_seconds: int = 3600):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)
        self.files: Dict[str, Path] = {}  # file_id -> file_path
        self.db_type: Optional[str] = None
        self.schema: Optional[List[Dict]] = None  # Cached database schema
        self.last_accessed = datetime.now()
        self.message_count: int = 0
        self.title: Optional[str] = None  # Auto-generated conversation title

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() > self.expires_at

    def extend(self, seconds: int = 3600):
        """Extend session TTL."""
        self.expires_at = datetime.now() + timedelta(seconds=seconds)
        self.last_accessed = datetime.now()

    def add_file(self, file_id: str, file_path: Path):
        """Add a file to the session."""
        self.files[file_id] = file_path
        self.extend()

    def remove_file(self, file_id: str):
        """Remove a file from the session."""
        if file_id in self.files:
            file_path = self.files.pop(file_id)
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        self.extend()

    def get_file(self, file_id: str) -> Optional[Path]:
        """Get file path by ID."""
        self.extend()
        return self.files.get(file_id)

    def set_schema(self, schema: List[Dict]):
        """Cache the database schema."""
        self.schema = schema
        self.extend()

    def get_schema(self) -> Optional[List[Dict]]:
        """Get cached schema."""
        self.extend()
        return self.schema

    def increment_message_count(self):
        """Increment the message count."""
        self.message_count += 1
        self.extend()

    def set_title(self, title: str):
        """Set conversation title (first user message)."""
        if not self.title:
            self.title = title[:50] + "..." if len(title) > 50 else title

    def to_dict(self) -> Dict:
        """Convert session to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "message_count": self.message_count,
            "title": self.title or "New Conversation",
            "file_count": len(self.files),
            "db_type": self.db_type,
        }

    def cleanup(self):
        """Delete all session files."""
        for file_path in self.files.values():
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        self.files.clear()


class SessionManager:
    """
    Manages user sessions and their associated temp files.
    Thread-safe implementation with automatic cleanup.
    """
    
    def __init__(self, temp_dir: Optional[str] = None, default_ttl: int = 3600):
        """
        Initialize session manager.
        
        Args:
            temp_dir: Directory for temp files (default: system temp).
            default_ttl: Default session TTL in seconds (default: 1 hour).
        """
        self.default_ttl = default_ttl
        self.sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        
        # Create temp directory
        if temp_dir:
            self.temp_dir = Path(temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.temp_dir = Path(tempfile.gettempdir()) / "dbarf_sessions"
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def create_session(self) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session = Session(session_id, self.default_ttl)
        
        with self._lock:
            self.sessions[session_id] = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        with self._lock:
            session = self.sessions.get(session_id)
            if session and not session.is_expired():
                session.extend()
                return session
            elif session and session.is_expired():
                # Clean up expired session
                self._remove_session(session_id)
        return None
    
    def remove_session(self, session_id: str):
        """Remove a session and cleanup its files."""
        with self._lock:
            self._remove_session(session_id)
    
    def _remove_session(self, session_id: str):
        """Internal method to remove session (must hold lock)."""
        session = self.sessions.pop(session_id, None)
        if session:
            session.cleanup()
    
    def upload_file(
        self,
        session_id: str,
        file_content: bytes,
        filename: str,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Upload a file to a session.
        
        Args:
            session_id: Session ID.
            file_content: File content as bytes.
            filename: Original filename.
            
        Returns:
            Tuple of (file_id, db_type, error_message).
        """
        session = self.get_session(session_id)
        if not session:
            return None, None, "Session not found or expired"
        
        try:
            # Detect file type from extension
            ext = Path(filename).suffix.lower()
            db_type = self._detect_db_type(ext)
            
            if not db_type:
                return None, None, f"Unsupported file type: {ext}"
            
            # Create unique file ID and path
            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}_{filename}"
            file_path = self.temp_dir / safe_filename
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Add to session
            session.add_file(file_id, file_path)
            session.db_type = db_type
            
            # Extract and cache schema
            try:
                schema = self._extract_schema(str(file_path), db_type)
                session.set_schema(schema)
            except Exception as e:
                print(f"Schema extraction warning: {e}")
                # Continue even if schema extraction fails
            
            return file_id, db_type, None
            
        except Exception as e:
            return None, None, f"Upload failed: {str(e)}"
    
    def _extract_schema(self, file_path: str, db_type: str) -> List[Dict]:
        """
        Extract database schema from file.
        
        Args:
            file_path: Path to the database file.
            db_type: Database type.
            
        Returns:
            List of table definitions with columns and types.
        """
        try:
            from rag_agent.db import DatabaseManager
            
            db_manager = DatabaseManager(file_path, db_type)
            return db_manager.extract_schema()
        except Exception as e:
            raise Exception(f"Schema extraction failed: {str(e)}")
    
    def _detect_db_type(self, ext: str) -> Optional[str]:
        """Detect database type from file extension."""
        mapping = {
            '.db': 'sqlite',
            '.sqlite': 'sqlite',
            '.sqlite3': 'sqlite',
            '.csv': 'csv',
            '.xlsx': 'xlsx',
            '.xls': 'xlsx',
        }
        return mapping.get(ext)
    
    def get_file_path(self, session_id: str, file_id: str) -> Optional[Path]:
        """Get file path for a session's file."""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get_file(file_id)
    
    def get_session_schema(self, session_id: str) -> Optional[List[Dict]]:
        """Get cached schema for a session."""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get_schema()
    
    def _start_cleanup_thread(self):
        """Start background thread for cleaning up expired sessions."""
        def cleanup_loop():
            while True:
                try:
                    self._cleanup_expired()
                except Exception as e:
                    print(f"Cleanup error: {e}")
                # Run cleanup every 5 minutes
                threading.Event().wait(300)
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def _cleanup_expired(self):
        """Remove expired sessions."""
        with self._lock:
            expired = [
                sid for sid, session in self.sessions.items()
                if session.is_expired()
            ]
            for sid in expired:
                self._remove_session(sid)
    
    def get_stats(self) -> dict:
        """Get session manager statistics."""
        with self._lock:
            active_sessions = len([
                s for s in self.sessions.values() if not s.is_expired()
            ])
            total_files = sum(len(s.files) for s in self.sessions.values())
            return {
                "active_sessions": active_sessions,
                "total_files": total_files,
                "temp_dir": str(self.temp_dir),
            }

    def get_all_sessions(self) -> List[Dict]:
        """Get all active sessions with metadata."""
        with self._lock:
            return [
                s.to_dict() for s in self.sessions.values()
                if not s.is_expired()
            ]


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def create_session() -> Session:
    """Create a new session."""
    return get_session_manager().create_session()


def get_session(session_id: str) -> Optional[Session]:
    """Get session by ID."""
    return get_session_manager().get_session(session_id)


def remove_session(session_id: str):
    """Remove a session."""
    get_session_manager().remove_session(session_id)


def upload_file(
    session_id: str,
    file_content: bytes,
    filename: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Upload a file to a session."""
    return get_session_manager().upload_file(session_id, file_content, filename)


def get_session_schema(session_id: str) -> Optional[List[Dict]]:
    """Get cached schema for a session."""
    return get_session_manager().get_session_schema(session_id)

"""Session management for command sequences"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from openrouter_client import Command
from logger import get_logger
from constants import CONFIG_DIR


@dataclass
class Session:
    """Represents a command session"""
    id: str
    name: str
    created_at: str
    updated_at: str
    description: str = ""
    commands: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.commands is None:
            self.commands = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create from dictionary"""
        return cls(**data)


class SessionManager:
    """Manages command sessions"""
    
    def __init__(self, sessions_dir: Optional[str] = None):
        self.logger = get_logger(self.__class__.__name__)
        if sessions_dir is None:
            config_dir = Path.home() / CONFIG_DIR
            sessions_dir = config_dir / "sessions"
        
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Session directory: {self.sessions_dir}")
    
    def create_session(self, name: str, description: str = "") -> Session:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        session = Session(
            id=session_id,
            name=name,
            created_at=now,
            updated_at=now,
            description=description
        )
        
        self._save_session(session)
        self.logger.info(f"Created session '{name}' with ID {session_id}")
        return session
    
    def save_session(self, session: Session):
        """Save session to disk"""
        session.updated_at = datetime.now().isoformat()
        self._save_session(session)
    
    def _save_session(self, session: Session):
        """Internal save method"""
        try:
            session_file = self.sessions_dir / f"{session.id}.json"
            with open(session_file, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
            self.logger.debug(f"Saved session {session.id}")
        except Exception as e:
            self.logger.error(f"Failed to save session {session.id}: {e}")
            raise
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session by ID"""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            if not session_file.exists():
                return None
            
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            session = Session.from_dict(data)
            self.logger.debug(f"Loaded session {session_id}")
            return session
        except Exception as e:
            self.logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(self) -> List[Session]:
        """List all available sessions"""
        sessions = []
        try:
            for session_file in self.sessions_dir.glob("*.json"):
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                session = Session.from_dict(data)
                sessions.append(session)
            
            # Sort by updated time, most recent first
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            self.logger.debug(f"Found {len(sessions)} sessions")
            return sessions
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                self.logger.info(f"Deleted session {session_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def add_commands_to_session(self, session: Session, commands: List[Command]):
        """Add commands to a session"""
        for command in commands:
            command_dict = {
                'command': command.command,
                'description': command.description,
                'working_directory': command.working_directory,
                'requires_confirmation': command.requires_confirmation,
                'added_at': datetime.now().isoformat()
            }
            session.commands.append(command_dict)
        
        self.save_session(session)
        self.logger.debug(f"Added {len(commands)} commands to session {session.id}")
    
    def get_session_commands(self, session: Session) -> List[Command]:
        """Get commands from a session as Command objects"""
        commands = []
        for cmd_dict in session.commands:
            command = Command(
                command=cmd_dict['command'],
                description=cmd_dict['description'],
                working_directory=cmd_dict.get('working_directory'),
                requires_confirmation=cmd_dict.get('requires_confirmation', True)
            )
            commands.append(command)
        
        return commands
    
    def find_sessions_by_name(self, name_pattern: str) -> List[Session]:
        """Find sessions by name pattern"""
        sessions = self.list_sessions()
        matching = [
            session for session in sessions 
            if name_pattern.lower() in session.name.lower()
        ]
        return matching
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about sessions"""
        sessions = self.list_sessions()
        total_commands = sum(len(session.commands) for session in sessions)
        
        return {
            'total_sessions': len(sessions),
            'total_commands': total_commands,
            'average_commands_per_session': total_commands / len(sessions) if sessions else 0
        }

"""Command execution history management"""

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from logger import get_logger
from constants import CONFIG_DIR


@dataclass
class HistoryEntry:
    """Represents a command execution history entry"""
    id: Optional[int] = None
    timestamp: str = ""
    query: str = ""
    command: str = ""
    description: str = ""
    success: bool = False
    output: str = ""
    execution_time: float = 0.0
    working_directory: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoryEntry':
        """Create from dictionary"""
        return cls(**data)


class CommandHistory:
    """Manages command execution history with SQLite storage"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.logger = get_logger(self.__class__.__name__)
        if db_path is None:
            config_dir = Path.home() / CONFIG_DIR
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / "history.db"
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS command_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        query TEXT NOT NULL,
                        command TEXT NOT NULL,
                        description TEXT,
                        success BOOLEAN NOT NULL,
                        output TEXT,
                        execution_time REAL,
                        working_directory TEXT
                    )
                """)
                
                # Create index for faster searches
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON command_history(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query 
                    ON command_history(query)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_command 
                    ON command_history(command)
                """)
                
                conn.commit()
                self.logger.debug(f"Initialized history database at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize history database: {e}")
            raise
    
    def add_entry(self, entry: HistoryEntry) -> int:
        """Add a new history entry and return its ID"""
        if not entry.timestamp:
            entry.timestamp = datetime.now().isoformat()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO command_history 
                    (timestamp, query, command, description, success, output, execution_time, working_directory)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp, entry.query, entry.command, entry.description,
                    entry.success, entry.output, entry.execution_time, entry.working_directory
                ))
                entry_id = cursor.lastrowid
                conn.commit()
                self.logger.debug(f"Added history entry {entry_id}")
                return entry_id
        except Exception as e:
            self.logger.error(f"Failed to add history entry: {e}")
            raise
    
    def search(self, query: Optional[str] = None, limit: int = 50, 
               successful_only: bool = False) -> List[HistoryEntry]:
        """Search command history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                sql = "SELECT * FROM command_history WHERE 1=1"
                params = []
                
                if query:
                    sql += " AND (query LIKE ? OR command LIKE ? OR description LIKE ?)"
                    search_term = f"%{query}%"
                    params.extend([search_term, search_term, search_term])
                
                if successful_only:
                    sql += " AND success = 1"
                
                sql += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                
                entries = []
                for row in rows:
                    entry = HistoryEntry(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        query=row['query'],
                        command=row['command'],
                        description=row['description'] or '',
                        success=bool(row['success']),
                        output=row['output'] or '',
                        execution_time=row['execution_time'] or 0.0,
                        working_directory=row['working_directory'] or ''
                    )
                    entries.append(entry)
                
                self.logger.debug(f"Found {len(entries)} history entries")
                return entries
                
        except Exception as e:
            self.logger.error(f"Failed to search history: {e}")
            return []
    
    def get_recent(self, limit: int = 10) -> List[HistoryEntry]:
        """Get recent command history"""
        return self.search(limit=limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get history statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) as total FROM command_history")
                total = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) as successful FROM command_history WHERE success = 1")
                successful = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT AVG(execution_time) as avg_time FROM command_history WHERE execution_time > 0")
                avg_time = cursor.fetchone()[0] or 0.0
                
                return {
                    'total_commands': total,
                    'successful_commands': successful,
                    'success_rate': (successful / total * 100) if total > 0 else 0.0,
                    'average_execution_time': avg_time
                }
        except Exception as e:
            self.logger.error(f"Failed to get history stats: {e}")
            return {}
    
    def clear_old_entries(self, days: int = 30):
        """Clear history entries older than specified days"""
        try:
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
            cutoff_str = cutoff_date.isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM command_history WHERE timestamp < ?", (cutoff_str,))
                deleted = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Deleted {deleted} old history entries")
                return deleted
        except Exception as e:
            self.logger.error(f"Failed to clear old entries: {e}")
            return 0
    
    def export_to_json(self, filepath: str, limit: Optional[int] = None):
        """Export history to JSON file"""
        try:
            entries = self.search(limit=limit or 1000)
            data = [entry.to_dict() for entry in entries]
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.logger.info(f"Exported {len(entries)} entries to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to export history: {e}")
            raise

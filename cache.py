"""Caching system for API responses and command results"""

import json
import hashlib
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from openrouter_client import Command
from logger import get_logger
from constants import CONFIG_DIR


class QueryCache:
    """Caches LLM responses for similar queries"""
    
    def __init__(self, db_path: Optional[str] = None, ttl_hours: int = 24):
        self.logger = get_logger(self.__class__.__name__)
        self.ttl_hours = ttl_hours
        
        if db_path is None:
            config_dir = Path.home() / CONFIG_DIR
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / "cache.db"
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite cache database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_hash TEXT UNIQUE NOT NULL,
                        query_text TEXT NOT NULL,
                        context TEXT,
                        model TEXT NOT NULL,
                        response_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        access_count INTEGER DEFAULT 0,
                        last_accessed TEXT
                    )
                """)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_query_hash ON query_cache(query_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON query_cache(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON query_cache(model)")
                
                conn.commit()
                self.logger.debug(f"Initialized cache database at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize cache database: {e}")
            raise
    
    def _generate_cache_key(self, query: str, context: Optional[str], model: str) -> str:
        """Generate a cache key for the query"""
        # Normalize query and context
        normalized_query = query.lower().strip()
        normalized_context = (context or "").lower().strip()
        
        # Create hash from query, context, and model
        key_data = f"{normalized_query}||{normalized_context}||{model}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, query: str, context: Optional[str], model: str) -> Optional[List[Command]]:
        """Get cached response for query"""
        cache_key = self._generate_cache_key(query, context, model)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT response_data, created_at FROM query_cache 
                    WHERE query_hash = ?
                """, (cache_key,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Check if cache entry is still valid
                created_at = datetime.fromisoformat(row['created_at'])
                if datetime.now() - created_at > timedelta(hours=self.ttl_hours):
                    self.logger.debug(f"Cache entry expired for key {cache_key[:8]}...")
                    # Delete expired entry
                    conn.execute("DELETE FROM query_cache WHERE query_hash = ?", (cache_key,))
                    conn.commit()
                    return None
                
                # Update access statistics
                conn.execute("""
                    UPDATE query_cache 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE query_hash = ?
                """, (datetime.now().isoformat(), cache_key))
                conn.commit()
                
                # Deserialize commands
                response_data = json.loads(row['response_data'])
                commands = [
                    Command(
                        command=cmd['command'],
                        description=cmd['description'],
                        working_directory=cmd.get('working_directory'),
                        requires_confirmation=cmd.get('requires_confirmation', True)
                    )
                    for cmd in response_data
                ]
                
                self.logger.debug(f"Cache hit for query: {query[:50]}...")
                return commands
                
        except Exception as e:
            self.logger.error(f"Error retrieving from cache: {e}")
            return None
    
    def put(self, query: str, context: Optional[str], model: str, commands: List[Command]):
        """Cache response for query"""
        cache_key = self._generate_cache_key(query, context, model)
        
        try:
            # Serialize commands
            command_data = [
                {
                    'command': cmd.command,
                    'description': cmd.description,
                    'working_directory': cmd.working_directory,
                    'requires_confirmation': cmd.requires_confirmation
                }
                for cmd in commands
            ]
            
            response_json = json.dumps(command_data)
            now = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO query_cache
                    (query_hash, query_text, context, model, response_data, created_at, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (cache_key, query, context or "", model, response_json, now, now))
                
                conn.commit()
                
            self.logger.debug(f"Cached response for query: {query[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Error caching response: {e}")
    
    def clear_expired(self) -> int:
        """Clear expired cache entries"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.ttl_hours)
            cutoff_str = cutoff_time.isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM query_cache WHERE created_at < ?", (cutoff_str,))
                deleted = cursor.rowcount
                conn.commit()
                
            self.logger.info(f"Cleared {deleted} expired cache entries")
            return deleted
            
        except Exception as e:
            self.logger.error(f"Error clearing expired cache: {e}")
            return 0
    
    def clear_all(self) -> int:
        """Clear all cache entries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM query_cache")
                deleted = cursor.rowcount
                conn.commit()
                
            self.logger.info(f"Cleared all {deleted} cache entries")
            return deleted
            
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Total entries
                cursor = conn.execute("SELECT COUNT(*) as total FROM query_cache")
                total = cursor.fetchone()['total']
                
                # Entries by age
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
                one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
                
                cursor = conn.execute("SELECT COUNT(*) as recent FROM query_cache WHERE created_at > ?", (one_hour_ago,))
                recent = cursor.fetchone()['recent']
                
                cursor = conn.execute("SELECT COUNT(*) as today FROM query_cache WHERE created_at > ?", (one_day_ago,))
                today = cursor.fetchone()['today']
                
                # Most accessed
                cursor = conn.execute("""
                    SELECT query_text, access_count FROM query_cache 
                    ORDER BY access_count DESC LIMIT 5
                """)
                popular = [{'query': row['query_text'][:50], 'hits': row['access_count']} 
                          for row in cursor.fetchall()]
                
                return {
                    'total_entries': total,
                    'entries_last_hour': recent,
                    'entries_today': today,
                    'cache_size_mb': self._get_db_size_mb(),
                    'popular_queries': popular
                }
                
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def _get_db_size_mb(self) -> float:
        """Get database file size in MB"""
        try:
            size_bytes = Path(self.db_path).stat().st_size
            return round(size_bytes / (1024 * 1024), 2)
        except Exception:
            return 0.0
    
    def search_similar_queries(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar cached queries"""
        try:
            query_lower = query.lower()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT query_text, access_count, created_at
                    FROM query_cache 
                    WHERE LOWER(query_text) LIKE ?
                    ORDER BY access_count DESC, created_at DESC
                    LIMIT ?
                """, (f"%{query_lower}%", limit))
                
                similar = []
                for row in cursor.fetchall():
                    similar.append({
                        'query': row['query_text'],
                        'access_count': row['access_count'],
                        'created_at': row['created_at']
                    })
                
                return similar
                
        except Exception as e:
            self.logger.error(f"Error searching similar queries: {e}")
            return []

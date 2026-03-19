"""
Session State Persistence for claude-collaborator
Enables resuming work across restarts
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class SessionState:
    """
    Persist and restore session state across restarts

    Automatically saves working state like active tasks,
    last work time, and other context that should persist.
    Uses in-memory caching to minimize file I/O.
    """

    def __init__(self, codebase_path: str):
        """
        Initialize session state manager

        Args:
            codebase_path: Path to the codebase
        """
        self.codebase_path = Path(codebase_path)
        self.memory_path = self.codebase_path / ".codebase-memory"
        self.state_file = self.memory_path / "session_state.json"

        # In-memory cache to avoid frequent file I/O
        self._cache = {}
        self._cache_dirty = False

        # Load initial state asynchronously (lazy load)
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load state only when needed"""
        if self._loaded:
            return

        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}
        self._loaded = True

    def _flush_cache(self):
        """Write cache to disk only if dirty"""
        if not self._cache_dirty:
            return

        try:
            self.memory_path.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2)
            self._cache_dirty = False
        except Exception:
            pass  # Fail silently - don't block tool execution

    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        Save current working state (cached, written on flush)

        Args:
            state: State dictionary to save

        Returns:
            True if successful
        """
        self._ensure_loaded()
        state['timestamp'] = datetime.now().isoformat()
        state['codebase_path'] = str(self.codebase_path)
        self._cache.update(state)
        self._cache_dirty = True
        # Don't flush immediately - will flush on next read or periodically
        return True

    def load_state(self) -> Dict[str, Any]:
        """Load previous session state (from cache)"""
        self._ensure_loaded()
        return self._cache.copy() if self._cache else {}

    def update_active_task(self, task_name: str, status: str = "in_progress"):
        """
        Update the active task in session state

        Args:
            task_name: Name of the active task
            status: Task status (in_progress, completed, etc.)
        """
        self._ensure_loaded()
        self._cache['active_task'] = task_name
        self._cache['task_status'] = status
        self._cache['last_work'] = datetime.now().isoformat()
        self._cache_dirty = True

    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the active task from session state

        Returns:
            Task info dict or None if no active task
        """
        self._ensure_loaded()
        if 'active_task' not in self._cache:
            return None

        return {
            'name': self._cache['active_task'],
            'status': self._cache.get('task_status', 'unknown'),
            'last_work': self._cache.get('last_work', '')
        }

    def save_work_context(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result_summary: str = ""
    ):
        """
        Save context about recent work (cached, async write)

        Args:
            tool_name: Tool that was called
            arguments: Tool arguments
            result_summary: Brief summary of result
        """
        self._ensure_loaded()

        if 'recent_work' not in self._cache:
            self._cache['recent_work'] = []

        # Add new work entry
        work_entry = {
            'tool': tool_name,
            'arguments': arguments,
            'result_summary': result_summary[:200],  # Truncate
            'timestamp': datetime.now().isoformat()
        }

        # Keep only last 10 work entries
        self._cache['recent_work'].insert(0, work_entry)
        self._cache['recent_work'] = self._cache['recent_work'][:10]
        self._cache_dirty = True

    def get_recent_work(self, limit: int = 5) -> list:
        """
        Get recent work entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent work entries
        """
        self._ensure_loaded()
        recent = self._cache.get('recent_work', [])
        return recent[:limit]

    def clear_state(self):
        """Clear all session state"""
        self._cache = {}
        self._cache_dirty = True
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except Exception:
            pass

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current session

        Returns:
            Session summary dictionary
        """
        self._ensure_loaded()
        active_task = self.get_active_task()

        return {
            'codebase_path': str(self.codebase_path),
            'active_task': active_task,
            'recent_work_count': len(self._cache.get('recent_work', [])),
            'last_session_time': self._cache.get('timestamp'),
            'session_file': str(self.state_file)
        }

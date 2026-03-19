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

    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        Save current working state

        Args:
            state: State dictionary to save

        Returns:
            True if successful
        """
        try:
            self.memory_path.mkdir(parents=True, exist_ok=True)

            state['timestamp'] = datetime.now().isoformat()
            state['codebase_path'] = str(self.codebase_path)

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)

            return True
        except (IOError, OSError):
            return False

    def load_state(self) -> Dict[str, Any]:
        """
        Load previous session state

        Returns:
            Previous state dictionary, or empty dict if not found
        """
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def update_active_task(self, task_name: str, status: str = "in_progress"):
        """
        Update the active task in session state

        Args:
            task_name: Name of the active task
            status: Task status (in_progress, completed, etc.)
        """
        state = self.load_state()
        state['active_task'] = task_name
        state['task_status'] = status
        state['last_work'] = datetime.now().isoformat()
        self.save_state(state)

    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the active task from session state

        Returns:
            Task info dict or None if no active task
        """
        state = self.load_state()
        if 'active_task' not in state:
            return None

        return {
            'name': state['active_task'],
            'status': state.get('task_status', 'unknown'),
            'last_work': state.get('last_work', '')
        }

    def save_work_context(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result_summary: str = ""
    ):
        """
        Save context about recent work

        Args:
            tool_name: Tool that was called
            arguments: Tool arguments
            result_summary: Brief summary of result
        """
        state = self.load_state()

        if 'recent_work' not in state:
            state['recent_work'] = []

        # Add new work entry
        work_entry = {
            'tool': tool_name,
            'arguments': arguments,
            'result_summary': result_summary[:200],  # Truncate
            'timestamp': datetime.now().isoformat()
        }

        # Keep only last 10 work entries
        state['recent_work'].insert(0, work_entry)
        state['recent_work'] = state['recent_work'][:10]

        self.save_state(state)

    def get_recent_work(self, limit: int = 5) -> list:
        """
        Get recent work entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent work entries
        """
        state = self.load_state()
        recent = state.get('recent_work', [])
        return recent[:limit]

    def clear_state(self):
        """Clear all session state"""
        if self.state_file.exists():
            self.state_file.unlink()

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current session

        Returns:
            Session summary dictionary
        """
        state = self.load_state()
        active_task = self.get_active_task()

        return {
            'codebase_path': str(self.codebase_path),
            'active_task': active_task,
            'recent_work_count': len(state.get('recent_work', [])),
            'last_session_time': state.get('timestamp'),
            'session_file': str(self.state_file)
        }

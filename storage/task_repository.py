
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from storage.state_manager import StateManager


BASE_DIR = Path(__file__).resolve().parents[1]
APPROVAL_DB = BASE_DIR / "data" / "omniweave_approvals.db"


class TaskRepository:
    def __init__(self, state_manager=None, db_path=None):
        self.state_manager = state_manager or StateManager()
        self.db_path = Path(db_path) if db_path else APPROVAL_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS task_approvals (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)

    def create_task(self, plan):
        task_id = self.state_manager.create_task(plan)

        with self._connect() as connection:
            connection.execute("""
                INSERT OR REPLACE INTO task_approvals
                    (task_id, status, reason, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                str(task_id),
                "pending",
                "",
                datetime.now(timezone.utc).isoformat()
            ))

        return str(task_id)

    def get_approval(self, task_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_approvals WHERE task_id = ?",
                (str(task_id),)
            ).fetchone()

        return dict(row) if row else None

    def set_approval(self, task_id, status, reason=""):
        if status not in ("approved", "rejected"):
            raise ValueError("Invalid approval status.")

        if self.state_manager.get_task(task_id) is None:
            return None

        with self._connect() as connection:
            connection.execute("""
                INSERT INTO task_approvals
                    (task_id, status, reason, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    updated_at = excluded.updated_at
            """, (
                str(task_id),
                status,
                reason,
                datetime.now(timezone.utc).isoformat()
            ))

        return self.get_approval(task_id)

    def get_task(self, task_id):
        task = self.state_manager.get_task(task_id)

        if task is None:
            return None

        result = dict(task)
        result["steps"] = self.state_manager.get_steps(task_id)
        result["events"] = self.state_manager.get_events(task_id)
        result["approval"] = self.get_approval(task_id)

        return result

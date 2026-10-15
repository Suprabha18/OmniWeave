
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "omniweave.db"


def current_time():
    return datetime.now(timezone.utc).isoformat()


class StateManager:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DEFAULT_DB).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    @contextmanager
    def _connect(self):
        """Open a database connection and always close it."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS steps (
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    description TEXT,
                    tool_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, step_id),
                    FOREIGN KEY (task_id)
                        REFERENCES tasks(task_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    arguments_json TEXT,
                    result_json TEXT,
                    success INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id)
                        REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id)
                        REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_id TEXT,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id)
                        REFERENCES tasks(task_id)
                );
            """)

    def create_task(self, plan, task_id=None):
        task_id = task_id or str(uuid.uuid4())
        now = current_time()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT task_id FROM tasks WHERE task_id = ?",
                (task_id,)
            ).fetchone()

            if existing:
                raise ValueError(f"Task already exists: {task_id}")

            conn.execute("""
                INSERT INTO tasks (
                    task_id, goal, plan_json, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                plan.get("goal", ""),
                json.dumps(plan, default=str),
                "pending",
                now,
                now
            ))

            for step in plan.get("steps", []):
                conn.execute("""
                    INSERT INTO steps (
                        task_id, step_id, description,
                        tool_name, status, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    step["id"],
                    step.get("description", ""),
                    step.get("tool_name", ""),
                    "pending",
                    now
                ))

        self.audit(
            task_id, None, "task_created", "Task created"
        )
        return task_id

    def get_task(self, task_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            ).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["plan"] = json.loads(result.pop("plan_json"))
        return result

    def get_steps(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM steps
                WHERE task_id = ?
                ORDER BY rowid
            """, (task_id,)).fetchall()

        result = []

        for row in rows:
            item = dict(row)
            item["result"] = (
                json.loads(item["result_json"])
                if item["result_json"] else None
            )
            result.append(item)

        return result

    def get_completed_step_ids(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT step_id FROM steps
                WHERE task_id = ? AND status = 'completed'
            """, (task_id,)).fetchall()

        return {row["step_id"] for row in rows}

    def update_step(
        self,
        task_id,
        step_id,
        status,
        attempts=None,
        result=None,
        error=None
    ):
        now = current_time()

        with self._connect() as conn:
            fields = ["status = ?", "updated_at = ?"]
            values = [status, now]

            if attempts is not None:
                fields.append("attempts = ?")
                values.append(attempts)

            if result is not None:
                fields.append("result_json = ?")
                values.append(json.dumps(result, default=str))

            if error is not None or status in ("completed", "running"):
                fields.append("error = ?")
                values.append(error)

            values.extend([task_id, step_id])

            cursor = conn.execute(
                f"UPDATE steps SET {', '.join(fields)} "
                "WHERE task_id = ? AND step_id = ?",
                values
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    f"Step not found: {step_id} in task {task_id}"
                )

    def record_tool_call(
        self,
        task_id,
        step_id,
        tool_name,
        attempt,
        arguments,
        result
    ):
        success = bool(result.get("success", False))
        error = result.get("error")

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO tool_calls (
                    task_id, step_id, tool_name, attempt,
                    arguments_json, result_json, success,
                    error, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                step_id,
                tool_name,
                attempt,
                json.dumps(arguments, default=str),
                json.dumps(result, default=str),
                int(success),
                error,
                current_time()
            ))

    def save_checkpoint(self, task_id, step_id, state):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO checkpoints (
                    task_id, step_id, state_json, created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                task_id,
                step_id,
                json.dumps(state, default=str),
                current_time()
            ))

    def audit(
        self,
        task_id,
        step_id,
        event_type,
        message,
        details=None
    ):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO audit_events (
                    task_id, step_id, event_type,
                    message, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                step_id,
                event_type,
                message,
                (
                    json.dumps(details, default=str)
                    if details is not None else None
                ),
                current_time()
            ))

    def set_task_status(self, task_id, status, error=None):
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE tasks
                SET status = ?, error = ?, updated_at = ?
                WHERE task_id = ?
            """, (
                status,
                error,
                current_time(),
                task_id
            ))

            if cursor.rowcount == 0:
                raise ValueError(f"Task not found: {task_id}")

    def get_events(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_events
                WHERE task_id = ?
                ORDER BY id
            """, (task_id,)).fetchall()

        return [dict(row) for row in rows]

    def get_tool_calls(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM tool_calls
                WHERE task_id = ?
                ORDER BY id
            """, (task_id,)).fetchall()

        return [dict(row) for row in rows]

    def get_checkpoints(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM checkpoints
                WHERE task_id = ?
                ORDER BY id
            """, (task_id,)).fetchall()

        result = []

        for row in rows:
            item = dict(row)
            item["state"] = json.loads(item.pop("state_json"))
            result.append(item)

        return result

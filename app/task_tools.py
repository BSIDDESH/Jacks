"""Task tools: persistent to-do list per student."""
from app.db import get_conn


def add_task(student_id: str, title: str, due: str | None = None):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM tasks WHERE student_id = ? AND lower(title) = lower(?) "
            "AND done = 0 AND ((due IS NULL AND ? IS NULL) OR due = ?)",
            (student_id, title, due, due),
        ).fetchone()
        if existing:
            return {
                "added": False,
                "duplicate": True,
                "task_id": existing["id"],
                "message": "An identical pending task already exists, so nothing new was added.",
            }
        cur = conn.execute(
            "INSERT INTO tasks (student_id, title, due) VALUES (?, ?, ?)",
            (student_id, title, due),
        )
        return {"added": True, "task_id": cur.lastrowid, "title": title, "due": due}


def list_tasks(student_id: str, include_done: bool = False):
    query = "SELECT id, title, due, done FROM tasks WHERE student_id = ?"
    if not include_done:
        query += " AND done = 0"
    query += " ORDER BY (due IS NULL), due, id"
    with get_conn() as conn:
        rows = conn.execute(query, (student_id,)).fetchall()
    return {"tasks": [dict(r) for r in rows]}


def complete_task(student_id: str, task_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE tasks SET done = 1 WHERE id = ? AND student_id = ?",
            (task_id, student_id),
        )
        if cur.rowcount == 0:
            return {"error": f"No task with id {task_id}"}
        return {"completed": True, "task_id": task_id}


TASK_FUNCTIONS = {
    "add_task": add_task,
    "list_tasks": list_tasks,
    "complete_task": complete_task,
}

TASK_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a to-do item for the student. Convert relative dates "
            "like 'Friday' into YYYY-MM-DD using today's date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "title": {"type": "string"},
                    "due": {"type": "string", "description": "Optional, YYYY-MM-DD"},
                },
                "required": ["student_id", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List the student's pending tasks (set include_done to also see finished ones).",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "include_done": {"type": "boolean"},
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as done. Call list_tasks first if you don't know the task id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "task_id": {"type": "integer"},
                },
                "required": ["student_id", "task_id"],
            },
        },
    },
]

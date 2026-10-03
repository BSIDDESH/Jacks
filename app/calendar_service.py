"""Calendar layer. Today: a local table. Later: Google Calendar API.
Everything else in the app only talks to these functions."""
from app.db import get_conn


def create_event(student_id, title, start, end, notes=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO calendar_events (student_id, title, start, end, notes) VALUES (?, ?, ?, ?, ?)",
            (student_id, title, start, end, notes),
        )
        return cur.lastrowid


def event_exists(event_id):
    """Read the event back to verify it was really created."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
    return row is not None


def list_events(student_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_events WHERE student_id = ? ORDER BY start",
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]

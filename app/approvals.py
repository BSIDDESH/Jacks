"""Approval gate. The model can only PROPOSE. Execution happens only in
decide(), which is reachable only from the human-facing /approve endpoint."""
from datetime import datetime
from app.db import get_conn
from app import calendar_service


def _valid(ts):
    try:
        datetime.fromisoformat(ts)
        return True
    except (ValueError, TypeError):
        return False


def propose_calendar_event(student_id: str, title: str, start: str, end: str, notes: str | None = None):
    if not (_valid(start) and _valid(end)):
        return {"error": "start and end must look like 2026-10-03T18:00"}
    if datetime.fromisoformat(end) <= datetime.fromisoformat(start):
        return {"error": "end must be after start"}
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (student_id, title, start, end, notes) VALUES (?, ?, ?, ?, ?)",
            (student_id, title, start, end, notes),
        )
        pid = cur.lastrowid
    return {
        "proposal_id": pid,
        "status": "pending_approval",
        "message": "Saved as a proposal. Nothing was added to the calendar; the student must approve it.",
    }


def list_proposals(student_id: str, status: str | None = None):
    query = "SELECT * FROM proposals WHERE student_id = ?"
    params = [student_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def decide(proposal_id: int, approve: bool):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            return {"error": f"No proposal with id {proposal_id}"}
        if row["status"] != "pending":
            return {"error": f"Proposal is already {row['status']}"}
        if not approve:
            conn.execute("UPDATE proposals SET status = 'rejected' WHERE id = ?", (proposal_id,))
            return {"proposal_id": proposal_id, "status": "rejected"}

    # Approved: create the event, then verify it really exists.
    try:
        event_id = calendar_service.create_event(
            row["student_id"], row["title"], row["start"], row["end"], row["notes"]
        )
        verified = calendar_service.event_exists(event_id)
        status, error = ("executed", None) if verified else ("failed", "event not found after creation")
    except Exception as e:
        event_id, status, error = None, "failed", str(e)

    with get_conn() as conn:
        conn.execute(
            "UPDATE proposals SET status = ?, calendar_event_id = ?, error = ? WHERE id = ?",
            (status, event_id, error, proposal_id),
        )
    return {"proposal_id": proposal_id, "status": status, "calendar_event_id": event_id, "error": error}


PROPOSAL_FUNCTIONS = {"propose_calendar_event": propose_calendar_event}

PROPOSAL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "propose_calendar_event",
            "description": "Propose a calendar event (study session, deadline block). "
            "This only saves a proposal for the student to approve; it never edits the calendar. "
            "Times are India time, formatted YYYY-MM-DDTHH:MM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "title": {"type": "string"},
                    "start": {"type": "string", "description": "e.g. 2026-10-03T18:00"},
                    "end": {"type": "string", "description": "e.g. 2026-10-03T20:00"},
                    "notes": {"type": "string"},
                },
                "required": ["student_id", "title", "start", "end"],
            },
        },
    }
]

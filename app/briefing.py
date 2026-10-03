"""Risk briefing: combines attendance, the latest circular and pending tasks.
The risk logic is plain Python so the numbers are always exact; the model only
explains the result."""
import math
from datetime import date

from app.circular_tools import get_circular_events
from app.task_tools import list_tasks

REQUIRED = 75
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _classes_to_recover(attended: int, total: int) -> int:
    """Consecutive classes the student must attend to reach the minimum."""
    need = (REQUIRED / 100 * total - attended) / (1 - REQUIRED / 100)
    return max(0, math.ceil(need - 1e-9))


def _match_subject(subject, attendance):
    if not subject:
        return None
    s = subject.strip().lower()
    for name, data in attendance.items():
        n = name.lower()
        if n == s or s.startswith(n) or n.startswith(s):
            return name, data
    return None


def get_risk_briefing(student_id: str):
    # Imported here to avoid a circular import with app.tools
    from app.tools import get_attendance

    today = date.today()
    attendance = get_attendance(student_id)
    if "error" in attendance:
        return attendance

    circular = get_circular_events(student_id)
    has_circular = "error" not in circular

    risks = []
    subjects = {}
    for name, d in attendance.items():
        entry = {
            "attended": d["attended"],
            "total": d["total"],
            "percent": d["percent"],
            "status": d["status"],
        }
        if d["percent"] < REQUIRED:
            n = _classes_to_recover(d["attended"], d["total"])
            entry["classes_to_attend_in_a_row_to_reach_minimum"] = n
            risks.append(
                {
                    "severity": "high",
                    "message": f"{name} attendance is {d['percent']}%, below the {REQUIRED}% minimum. "
                    f"Attending the next {n} classes in a row brings it back to {REQUIRED}%.",
                }
            )
        subjects[name] = entry

    exams, deadlines, condonation = [], [], []
    if has_circular:
        for e in circular["events"]:
            try:
                d = date.fromisoformat(e["date"])
            except ValueError:
                continue
            days = (d - today).days
            if days < 0:
                continue
            item = {
                "title": e["title"],
                "subject": e.get("subject"),
                "date": e["date"],
                "days_left": days,
                "start_time": e.get("start_time"),
                "end_time": e.get("end_time"),
                "details": e.get("details"),
            }
            if e["kind"] == "exam":
                match = _match_subject(e.get("subject"), attendance)
                if match:
                    name, ad = match
                    item["attendance_percent"] = ad["percent"]
                    item["eligible_at_current_attendance"] = ad["percent"] >= REQUIRED
                    if ad["percent"] < REQUIRED:
                        risks.append(
                            {
                                "severity": "high",
                                "message": f"{name} exam on {e['date']} ({days} days away): attendance is "
                                f"{ad['percent']}%, so you may not be allowed to sit it unless a "
                                f"condonation request is approved.",
                            }
                        )
                exams.append(item)
            else:
                deadlines.append(item)
                text = (e["title"] + " " + (e.get("details") or "")).lower()
                if "condonation" in text:
                    condonation.append(item)
                elif days <= 7:
                    risks.append(
                        {
                            "severity": "medium",
                            "message": f"{e['title']} is due {e['date']} ({days} days away).",
                        }
                    )

        if condonation and any(v["percent"] < REQUIRED for v in subjects.values()):
            for c in condonation:
                risks.append(
                    {
                        "severity": "high",
                        "message": f"Condonation request deadline: {c['date']} ({c['days_left']} days away).",
                    }
                )

    pending = list_tasks(student_id)["tasks"]
    for t in pending:
        if not t.get("due"):
            continue
        try:
            days = (date.fromisoformat(t["due"]) - today).days
        except ValueError:
            continue
        if days < 0:
            when = f"overdue by {-days} day(s)"
        elif days == 0:
            when = "due today"
        elif days <= 3:
            when = f"due in {days} day(s)"
        else:
            continue
        risks.append({"severity": "medium", "message": f"Task '{t['title']}' is {when}."})

    risks.sort(key=lambda r: SEVERITY_ORDER[r["severity"]])

    result = {
        "today": today.isoformat(),
        "minimum_attendance_percent": REQUIRED,
        "attendance": subjects,
        "exams": exams,
        "deadlines": deadlines,
        "pending_tasks": pending,
        "rules": circular.get("rules", []) if has_circular else [],
        "risks": risks,
        "circular_loaded": has_circular,
    }
    if not has_circular:
        result["note"] = "No circular uploaded yet, so exam dates and deadlines are unknown."
    return result


BRIEFING_FUNCTIONS = {"get_risk_briefing": get_risk_briefing}

BRIEFING_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_risk_briefing",
            "description": "Get a complete academic risk briefing: attendance problems, how many "
            "classes to attend to recover, exam dates and eligibility, upcoming deadlines, "
            "overdue tasks and college rules. Use this once for questions like 'what should I "
            "worry about', 'what is at risk', or before building a study plan.",
            "parameters": {
                "type": "object",
                "properties": {"student_id": {"type": "string"}},
                "required": ["student_id"],
            },
        },
    }
]

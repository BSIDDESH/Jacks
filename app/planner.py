"""Study planner: turns exam dates into study sessions saved as proposals.
Scheduling is plain Python, so it is exact and repeatable. The model only
explains the result. Nothing here touches the calendar: every session is a
pending proposal that the student must approve.

Sessions for each subject are spread evenly across the free slots before its
exam (spaced revision, not one big cram), and re-running the planner only tops
up sessions that are missing instead of adding a whole new plan."""
from datetime import date, datetime, timedelta

from app import calendar_service
from app.approvals import list_proposals, propose_calendar_event
from app.briefing import get_risk_briefing

# Assumed study windows (there is no timetable upload yet). Edit these to change the plan.
WEEKDAY_WINDOWS = [("18:00", "20:00")]
WEEKEND_WINDOWS = [("10:00", "12:00"), ("16:00", "18:00")]
DEFAULT_SESSIONS = 4

ASSUMPTIONS = (
    "Study windows are assumed because there is no timetable yet: weekdays 18:00-20:00, "
    "weekends 10:00-12:00 and 16:00-18:00 (India time). Slots that overlap existing "
    "calendar events or pending proposals are skipped."
)


def _dt(d: date, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(d.year, d.month, d.day, int(h), int(m))


def _busy(student_id: str):
    busy = []
    for ev in calendar_service.list_events(student_id):
        busy.append((datetime.fromisoformat(ev["start"]), datetime.fromisoformat(ev["end"])))
    for p in list_proposals(student_id, "pending"):
        busy.append((datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"])))
    return busy


def _existing_sessions(student_id: str):
    """Study sessions already on the calendar, per subject: list of dates."""
    found = {}
    for ev in calendar_service.list_events(student_id):
        if ev["title"].startswith("Study: "):
            subject = ev["title"][len("Study: "):]
            found.setdefault(subject, []).append(datetime.fromisoformat(ev["start"]).date())
    return found


def _label(st: datetime, en: datetime) -> str:
    return f"{st.strftime('%a %d %b')}, {st.strftime('%H:%M')}-{en.strftime('%H:%M')}"


def build_plan(student_id: str, sessions_per_subject: int):
    briefing = get_risk_briefing(student_id)
    if "error" in briefing:
        return briefing

    today = date.today()
    exams = {}
    for ex in briefing["exams"]:
        name = ex.get("subject") or ex["title"]
        exams[name] = {"date": date.fromisoformat(ex["date"]), "details": ex.get("details")}
    if not exams:
        return {"error": "No upcoming exams found. Upload a circular first."}

    # Top up: count sessions already planned before each exam
    existing = _existing_sessions(student_id)
    quota = {}
    for name, info in exams.items():
        have = sum(1 for d in existing.get(name, []) if today <= d < info["date"])
        quota[name] = max(0, sessions_per_subject - have)
    if all(q == 0 for q in quota.values()):
        return {"already_planned": True}

    busy = _busy(student_id)
    last_exam = max(v["date"] for v in exams.values())
    free = []
    day = today + timedelta(days=1)
    while day < last_exam:
        windows = WEEKEND_WINDOWS if day.weekday() >= 5 else WEEKDAY_WINDOWS
        for a, b in windows:
            st, en = _dt(day, a), _dt(day, b)
            if not any(st < be and bs < en for bs, be in busy):
                free.append((st, en))
        day += timedelta(days=1)

    sessions, unscheduled = [], {}
    for name in sorted(exams, key=lambda n: exams[n]["date"]):
        want = quota[name]
        if want == 0:
            continue
        eligible = [s for s in free if s[0].date() < exams[name]["date"]]
        take = min(want, len(eligible))
        if take < want:
            unscheduled[name] = want - take
        if take == 0:
            continue
        # Evenly spaced picks across everything free before this exam
        picks = [eligible[int((i + 0.5) * len(eligible) / take)] for i in range(take)]
        for st, en in picks:
            free.remove((st, en))
            sessions.append(
                {
                    "subject": name,
                    "start": st.strftime("%Y-%m-%dT%H:%M"),
                    "end": en.strftime("%Y-%m-%dT%H:%M"),
                    "label": _label(st, en),
                    "details": exams[name]["details"],
                }
            )
    sessions.sort(key=lambda s: s["start"])
    return {"sessions": sessions, "unscheduled": unscheduled}


def propose_study_plan(student_id: str, sessions_per_subject: int = DEFAULT_SESSIONS):
    try:
        n = max(1, min(int(sessions_per_subject), 8))
    except (TypeError, ValueError):
        n = DEFAULT_SESSIONS

    waiting = [p for p in list_proposals(student_id, "pending") if p["title"].startswith("Study:")]
    if waiting:
        return {
            "error": f"{len(waiting)} study sessions are already waiting for approval. "
            "Approve or reject them first."
        }

    plan = build_plan(student_id, n)
    if "error" in plan:
        return plan
    if plan.get("already_planned"):
        return {
            "sessions_proposed": 0,
            "message": f"Every exam already has {n} study sessions on the calendar, so nothing new was proposed.",
        }
    if not plan["sessions"]:
        return {"error": "No free study slots were found before the exams."}

    by_subject = {}
    for s in plan["sessions"]:
        result = propose_calendar_event(
            student_id, f"Study: {s['subject']}", s["start"], s["end"], s["details"]
        )
        if "error" in result:
            continue
        by_subject.setdefault(s["subject"], []).append(s["label"])

    return {
        "sessions_proposed": sum(len(v) for v in by_subject.values()),
        "hours_per_session": 2,
        "sessions_by_subject": by_subject,
        "not_scheduled": plan["unscheduled"],
        "assumptions": ASSUMPTIONS,
        "message": "All sessions are saved as proposals. Nothing was added to the calendar; "
        "the student must approve them on the dashboard.",
    }


PLANNER_FUNCTIONS = {"propose_study_plan": propose_study_plan}

PLANNER_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "propose_study_plan",
            "description": "Build a study plan for the upcoming exams from the uploaded circular "
            "and save every session as a proposal waiting for the student's approval. "
            "Sessions already on the calendar count toward the total, so re-running only tops up. "
            "Call it once when the student asks for a study plan or schedule for their exams.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "sessions_per_subject": {
                        "type": "integer",
                        "description": "Optional. 2-hour sessions per subject (default 4, max 8).",
                    },
                },
                "required": ["student_id"],
            },
        },
    }
]

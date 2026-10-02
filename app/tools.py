"""Tools JACK's can call. Each tool has a schema (what the model sees)
and a Python function (what actually runs)."""

# Seeded fake data for the demo. Later this is replaced by a database.
STUDENTS = {
    "S101": {
        "name": "Demo Student",
        "attendance": {
            "Math": {"attended": 34, "total": 50},
            "OS": {"attended": 41, "total": 50},
            "DBMS": {"attended": 37, "total": 50},
        },
    }
}

REQUIRED_PERCENT = 75


def get_attendance(student_id: str, subject: str | None = None):
    student = STUDENTS.get(student_id)
    if not student:
        return {"error": f"Unknown student_id {student_id}"}

    available = list(student["attendance"].keys())

    # Treat missing / "all" style values as "every subject"
    if subject is not None and subject.strip().lower() in ("", "all", "any", "everything"):
        subject = None

    result = {}
    for subj, d in student["attendance"].items():
        if subject and subj.lower() != subject.lower():
            continue
        attended, total = d["attended"], d["total"]
        percent = round(100 * attended / total, 1)
        # Classes the student can still miss while staying at/above 75%
        can_miss = 0
        while attended / (total + can_miss + 1) * 100 >= REQUIRED_PERCENT:
            can_miss += 1
        result[subj] = {
            "attended": attended,
            "total": total,
            "percent": percent,
            "classes_can_miss": can_miss if percent >= REQUIRED_PERCENT else 0,
            "status": "safe" if percent >= REQUIRED_PERCENT else "critical",
        }
    if not result:
        return {
            "error": f"No attendance data for subject '{subject}'",
            "available_subjects": available,
        }
    return result


TOOL_FUNCTIONS = {"get_attendance": get_attendance}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_attendance",
            "description": "Get attendance numbers and risk status for a student. "
            "Omit 'subject' to get ALL subjects in one call. "
            "Always use this for attendance questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "subject": {
                        "type": "string",
                        "description": "Optional. One subject name, e.g. Math. Leave out for all subjects.",
                    },
                },
                "required": ["student_id"],
            },
        },
    }
]

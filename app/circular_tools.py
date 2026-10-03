"""Exam circular reading: PDF text -> structured events saved in the database."""
import os
import json
from datetime import date

import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI

from app.db import get_conn

load_dotenv()

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY"),
)
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
FAST = {"chat_template_kwargs": {"enable_thinking": False}}

with get_conn() as _conn:
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS circulars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            filename TEXT,
            title TEXT,
            extracted_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

EXTRACT_PROMPT = """You read official college circulars and return structured data.
Return ONLY one JSON object, with no commentary and no markdown fences.

Schema:
{{
  "title": "short title of the circular",
  "circular_no": "circular number or null",
  "events": [
    {{
      "kind": "exam" or "deadline" or "other",
      "title": "what happens, e.g. 'Math IA-2' or 'OS lab record submission'",
      "subject": "subject name as written in the table (e.g. Math, OS, DBMS) or null",
      "date": "YYYY-MM-DD",
      "start_time": "HH:MM in 24-hour time or null",
      "end_time": "HH:MM in 24-hour time or null",
      "details": "syllabus covered or other useful detail, or null"
    }}
  ],
  "rules": ["each important rule or instruction as one short sentence"]
}}

Rules for you:
- Use only information that is in the text. Never invent dates, subjects or rules.
- Every date must be written as YYYY-MM-DD. Today is {today}.
- Include every exam date and every submission deadline you can find.
- For an exam, set subject to the short subject name used in the timetable.
"""


def extract_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc).strip()
    finally:
        doc.close()


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The model did not return JSON.")
    return json.loads(raw[start : end + 1])


def extract_structured(text: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT.format(today=date.today().isoformat())},
            {"role": "user", "content": "Circular text:\n\n" + text},
        ],
        max_tokens=2500,
        temperature=0,
        extra_body=FAST,
    )
    return _parse_json(resp.choices[0].message.content or "")


def _clean(data: dict):
    events, warnings = [], []
    for e in data.get("events") or []:
        try:
            date.fromisoformat(str(e.get("date")))
        except ValueError:
            warnings.append(f"Skipped an event with an invalid date: {e.get('title')}")
            continue
        kind = e.get("kind") if e.get("kind") in ("exam", "deadline", "other") else "other"
        events.append(
            {
                "kind": kind,
                "title": e.get("title") or "Untitled",
                "subject": e.get("subject"),
                "date": e["date"],
                "start_time": e.get("start_time"),
                "end_time": e.get("end_time"),
                "details": e.get("details"),
            }
        )
    events.sort(key=lambda x: x["date"])
    rules = [str(r) for r in (data.get("rules") or []) if r]
    return events, rules, warnings


def process_circular(student_id: str, filename: str, pdf_bytes: bytes) -> dict:
    text = extract_text(pdf_bytes)
    if len(text) < 30:
        raise ValueError(
            "No readable text found. Scanned image PDFs are not supported yet; upload a text-based PDF."
        )
    data = extract_structured(text[:12000])
    events, rules, warnings = _clean(data)
    if not events:
        raise ValueError("No dates were found in this document.")
    record = {
        "title": data.get("title") or filename,
        "circular_no": data.get("circular_no"),
        "events": events,
        "rules": rules,
    }
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO circulars (student_id, filename, title, extracted_json) VALUES (?, ?, ?, ?)",
            (student_id, filename, record["title"], json.dumps(record)),
        )
        cid = cur.lastrowid
    return {"circular_id": cid, "warnings": warnings, **record}


def get_circular_events(student_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, extracted_json FROM circulars WHERE student_id = ? ORDER BY id DESC LIMIT 1",
            (student_id,),
        ).fetchone()
    if not row:
        return {"error": "No circular has been uploaded yet."}
    return {"circular_id": row["id"], **json.loads(row["extracted_json"])}


CIRCULAR_FUNCTIONS = {"get_circular_events": get_circular_events}

CIRCULAR_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_circular_events",
            "description": "Get the exam dates, submission deadlines and rules from the "
            "student's most recently uploaded college circular. Use this for any question "
            "about exams, deadlines or college rules. Never guess these.",
            "parameters": {
                "type": "object",
                "properties": {"student_id": {"type": "string"}},
                "required": ["student_id"],
            },
        },
    }
]

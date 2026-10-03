from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import run_agent
from app.approvals import list_proposals, decide
from app import calendar_service
from app.tools import get_attendance as _get_attendance
from app.task_tools import list_tasks as _list_tasks
from app.circular_tools import process_circular, get_circular_events

app = FastAPI(title="JACK's API")

# Allow the Next.js frontend (running on localhost:3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    student_id: str = "S101"


@app.get("/")
def root():
    return {"name": "JACKs API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    answer, trace = run_agent(req.message, student_id=req.student_id)
    return {"answer": answer, "trace": trace}


# ---- Data endpoints for the dashboard (no model call) ----

@app.get("/attendance")
def attendance(student_id: str = "S101"):
    return _get_attendance(student_id)


@app.get("/tasks")
def tasks(student_id: str = "S101"):
    return _list_tasks(student_id)


@app.get("/calendar")
def get_calendar(student_id: str = "S101"):
    return {"events": calendar_service.list_events(student_id)}


# ---- Circulars ----

@app.post("/upload-circular")
async def upload_circular(student_id: str = "S101", file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(status_code=400, detail="That PDF is larger than 5 MB.")
    try:
        return process_circular(student_id, file.filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Could not read this circular. Please try again.",
        )


@app.get("/circulars/latest")
def latest_circular(student_id: str = "S101"):
    return get_circular_events(student_id)


# ---- Human-facing approval endpoints (the agent has NO tool for these) ----

@app.get("/proposals")
def get_proposals(student_id: str = "S101", status: str | None = None):
    return {"proposals": list_proposals(student_id, status)}


@app.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: int):
    result = decide(proposal_id, True)
    if "error" in result and "status" not in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: int):
    result = decide(proposal_id, False)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

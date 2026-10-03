from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.agent import run_agent
from app.approvals import list_proposals, decide
from app import calendar_service

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


@app.get("/calendar")
def get_calendar(student_id: str = "S101"):
    return {"events": calendar_service.list_events(student_id)}

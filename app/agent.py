"""The JACK's agent loop."""
import os
import json
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from app.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

load_dotenv()

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY"),
)

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
FAST = {"chat_template_kwargs": {"enable_thinking": False}}
THINK = {"chat_template_kwargs": {"enable_thinking": True}}
MAX_STEPS = 6

SYSTEM_PROMPT = """You are JACK's, a personal academic assistant for one college student.
You help with attendance, study planning, deadlines and tasks.

Rules:
- The current student's id is {student_id}. Use it when calling tools.
- Today is {today}.
- Turn words like 'Friday' or 'tomorrow' into dates by picking from that list. If today already is that weekday, use the same weekday next week unless the student says 'today'.
- For any attendance, timetable or deadline fact, call a tool. Never guess numbers.
- Answer only from tool results. If data is missing, say so plainly.
- Your name is JACK's. Always write it exactly like that.
- The student id is already known, so never ask the student for it.
- To check every subject, call get_attendance once with no subject.
- Include the actual percentages when you answer about attendance.
- To schedule anything, call propose_calendar_event. It only creates a proposal. Tell the student it is waiting for their approval; never say it was added to the calendar.
- Times are India time (IST). Use the format YYYY-MM-DDTHH:MM.
- To change a task, call list_tasks first, then use complete_task with the matching id. Never ask the student for a task id.
- If two tasks have the same title, complete the one with the higher id and say you removed the duplicate.
- For exam dates, submission deadlines or college rules, call get_circular_events. Never guess them.
- When asked what to worry about, what is at risk, or for a plan, call get_risk_briefing once and base the whole answer on it. List the risks from most to least severe, naming subjects, numbers and dates exactly as given.
- To build a study plan, call propose_study_plan once. It saves sessions as proposals waiting for approval. Summarise it by subject with first and last dates, mention the assumed study windows, and say it is waiting for approval; never say it was added to the calendar.
- When listing study sessions, copy the exact dates and times from the tool result. Never state a time that is not in the result.
- Keep replies short, friendly and practical (a few sentences).
- You cannot change the student's calendar directly; you can only propose actions
  for the student to approve.
"""


def today_text():
    """Today plus the next 14 days with weekdays, so the model never does date math."""
    d = date.today()
    days = [(d + timedelta(days=i)).strftime("%a %Y-%m-%d") for i in range(15)]
    return d.strftime("%A %Y-%m-%d") + ". Upcoming dates: " + ", ".join(days)


def run_agent(user_message: str, student_id: str = "S101", history=None, think=False):
    """Run the agent until it gives a final answer. Returns (answer, trace)."""
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(student_id=student_id, today=today_text()),
        }
    ]
    messages += history or []
    messages.append({"role": "user", "content": user_message})

    trace = []  # a log of every tool call, useful for the demo's activity panel

    for step in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            max_tokens=2000,
            extra_body=THINK if think else FAST,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content, trace

        messages.append(msg)
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments)
                func = TOOL_FUNCTIONS[name]
                result = func(**args)
            except Exception as e:
                args, result = {}, {"error": str(e)}
            trace.append({"tool": name, "args": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    return "Sorry, I couldn't finish that. Please try again.", trace







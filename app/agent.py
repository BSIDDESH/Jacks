"""The JACK's agent loop."""
import os
import json
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
- For any attendance, timetable or deadline fact, call a tool. Never guess numbers.
- Answer only from tool results. If data is missing, say so plainly.
- Your name is JACK's. Always write it exactly like that.
- The student id is already known, so never ask the student for it.
- To check every subject, call get_attendance once with no subject.
- Include the actual percentages when you answer about attendance.
- Keep replies short, friendly and practical (a few sentences).
- You cannot change the student's calendar directly; you can only propose actions
  for the student to approve.
"""


def run_agent(user_message: str, student_id: str = "S101", history=None, think=False):
    """Run the agent until it gives a final answer. Returns (answer, trace)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(student_id=student_id)}
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


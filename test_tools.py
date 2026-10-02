import os, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY"),
)
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
FAST = {"chat_template_kwargs": {"enable_thinking": False}}

SYSTEM = (
    "You are JACK's, an academic assistant for college students. "
    "Use the provided tools to get real data. Never invent attendance numbers."
)

tools = [{
    "type": "function",
    "function": {
        "name": "get_attendance",
        "description": "Get a student's attendance percentage for a subject.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "subject": {"type": "string"},
            },
            "required": ["student_id", "subject"],
        },
    },
}]

def get_attendance(student_id, subject):
    return {"subject": subject, "attendance_percent": 68, "classes_can_miss": 2}

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "How is my Math attendance? My student id is S101."},
]

resp = client.chat.completions.create(
    model=MODEL, messages=messages, tools=tools, max_tokens=1500, extra_body=FAST
)
msg = resp.choices[0].message
print("TOOL CALLS:", msg.tool_calls)

if msg.tool_calls:
    messages.append(msg)
    for call in msg.tool_calls:
        args = json.loads(call.function.arguments)
        result = get_attendance(**args)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result),
        })
    final = client.chat.completions.create(
        model=MODEL, messages=messages, tools=tools, max_tokens=1500, extra_body=FAST
    )
    print("FINAL ANSWER:", final.choices[0].message.content)

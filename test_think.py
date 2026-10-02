import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY"),
)
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
msgs = [{"role": "user", "content": "Say hello from JACK's in one sentence."}]

def run(label, **extra):
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=MODEL, messages=msgs, max_tokens=1500, **extra
        )
        print(f"{label}: {time.time()-t:.1f}s -> {r.choices[0].message.content!r}")
        print("   tokens used:", r.usage.completion_tokens)
    except Exception as e:
        print(f"{label}: ERROR {e}")

run("default")
run("no-think", extra_body={"chat_template_kwargs": {"enable_thinking": False}})

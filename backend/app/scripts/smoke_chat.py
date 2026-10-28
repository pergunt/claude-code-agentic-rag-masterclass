"""Smoke-test the Chat Completions stream without the web app.

Usage: venv/bin/python -m app.scripts.smoke_chat "question"
       venv/bin/python -m app.scripts.smoke_chat --memory   (checks the model reads the history it is sent)
"""

import asyncio
import sys

from app.config import get_settings
from app.services import llm

MEMORY_HISTORY = [
    {"role": "user", "content": "My favourite colour is teal. Just reply OK."},
    {"role": "assistant", "content": "OK."},
    {"role": "user", "content": "What is my favourite colour? One word."},
]


async def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--memory"]:
        history = MEMORY_HISTORY
    else:
        question = " ".join(args) or "What documents do you have access to?"
        history = [{"role": "user", "content": question}]
    settings = get_settings()
    print(f"base_url: {settings.llm_base_url}\nmodel: {settings.llm_model}\n")
    async for event in llm.stream_reply(history):
        match event["type"]:
            case "delta":
                print(event["delta"], end="", flush=True)
            case "tool":
                print(f"\n[{event['name']}: {event['status']}]", flush=True)
            case "done":
                print("\n\n[done]")
            case "error":
                print(f"\n[error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())

"""Smoke-test the Chat Completions stream without the web app.

Usage: venv/bin/python -m app.scripts.smoke_chat "question"
       venv/bin/python -m app.scripts.smoke_chat --memory   (checks the model reads the history it is sent)
       venv/bin/python -m app.scripts.smoke_chat --as rag-test-a@example.com "question"
           (signs in as that user so the model can call search_documents over their documents)
"""

import asyncio
import sys

from app.db import create_user_client
from app.scripts.dev_tokens import sign_in
from app.services import llm
from app.services.app_settings import get_runtime_config
from app.services.tools import ToolContext

MEMORY_HISTORY = [
    {"role": "user", "content": "My favourite colour is teal. Just reply OK."},
    {"role": "assistant", "content": "OK."},
    {"role": "user", "content": "What is my favourite colour? One word."},
]


async def main() -> None:
    args = sys.argv[1:]
    ctx = None
    if args[:1] == ["--as"]:
        token, user_id = sign_in(args[1])
        ctx = ToolContext(db=create_user_client(token), user_id=user_id)
        args = args[2:]
    if args[:1] == ["--memory"]:
        history = MEMORY_HISTORY
    else:
        question = " ".join(args) or "What documents do you have access to?"
        history = [{"role": "user", "content": question}]
    cfg = get_runtime_config()
    print(f"base_url: {cfg.llm_base_url}\nmodel: {cfg.llm_model}\n")
    async for event in llm.stream_reply(history, ctx, cfg):
        match event["type"]:
            case "delta":
                print(event["delta"], end="", flush=True)
            case "tool":
                if event["status"] == "searching":
                    print(f"\n[{event['name']}: searching \"{event.get('query')}\"]", flush=True)
                else:
                    count = len(event.get("sources", []))
                    print(f"[{event['status']}: {count} sources]", flush=True)
            case "done":
                print("\n\n[done]")
            case "error":
                print(f"\n[error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())

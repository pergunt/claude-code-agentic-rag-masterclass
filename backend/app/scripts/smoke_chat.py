"""Smoke-test the Responses API stream without the web app.

Usage: venv/bin/python -m app.scripts.smoke_chat "question about your docs"
"""

import asyncio
import sys

from app.services import llm


async def main() -> None:
    question = " ".join(sys.argv[1:]) or "What documents do you have access to?"
    conversation_id = llm.create_conversation()
    print(f"conversation: {conversation_id}\n")
    try:
        async for event in llm.stream_reply(conversation_id, question):
            match event["type"]:
                case "delta":
                    print(event["delta"], end="", flush=True)
                case "tool":
                    print(f"\n[{event['name']}: {event['status']}]", flush=True)
                case "done":
                    print("\n\n[done]")
                case "error":
                    print(f"\n[error] {event['message']}")
    finally:
        llm.delete_conversation(conversation_id)


if __name__ == "__main__":
    asyncio.run(main())

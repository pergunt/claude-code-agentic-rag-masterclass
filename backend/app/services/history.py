from supabase import Client

from app.config import get_settings


def trim_history(messages: list[dict], max_messages: int, max_chars: int) -> list[dict]:
    """Window the stored history: last N messages, within a character budget, starting on a user turn.

    The newest message (the current user turn) is always kept, even if it alone exceeds the budget.
    """
    window = messages[-max_messages:]
    total = sum(len(m["content"]) for m in window)
    while len(window) > 1 and total > max_chars:
        total -= len(window[0]["content"])
        window = window[1:]
    while len(window) > 1 and window[0]["role"] == "assistant":
        window = window[1:]
    return [{"role": m["role"], "content": m["content"]} for m in window]


def load_history(db: Client, thread_id: str) -> list[dict]:
    """Load the thread's recent messages (oldest first), trimmed to the configured window."""
    settings = get_settings()
    rows = (
        db.table("messages")
        .select("role,content")
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .limit(settings.chat_history_max_messages)
        .execute()
        .data
    )
    rows.reverse()
    return trim_history(rows, settings.chat_history_max_messages, settings.chat_history_max_chars)

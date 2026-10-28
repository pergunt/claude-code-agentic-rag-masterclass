from app.services.history import trim_history


def msgs(*pairs):
    return [{"role": r, "content": c} for r, c in pairs]


def test_CHAT_05_keeps_last_n_messages():
    m = msgs(*[("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(10)])
    out = trim_history(m, 4, 10_000)
    # last 4 are m6(user) m7 m8(user) m9
    assert [x["content"] for x in out] == ["m6", "m7", "m8", "m9"]


def test_CHAT_05_char_budget_drops_oldest():
    m = msgs(("user", "a" * 50), ("assistant", "b" * 50), ("user", "c" * 10))
    out = trim_history(m, 10, 70)
    assert [x["content"][0] for x in out] == ["b", "c"] or [x["content"][0] for x in out] == ["c"]
    assert out[-1]["content"] == "c" * 10
    assert sum(len(x["content"]) for x in out) <= 70


def test_CHAT_05_window_starts_on_user_turn():
    m = msgs(("assistant", "a1"), ("assistant", "a2"), ("user", "u"), ("assistant", "a3"), ("user", "u2"))
    out = trim_history(m, 10, 10_000)
    assert out[0]["role"] == "user"
    assert [x["content"] for x in out] == ["u", "a3", "u2"]


def test_CHAT_05_keeps_newest_message_when_oversize():
    m = msgs(("user", "old"), ("assistant", "reply"), ("user", "x" * 500))
    out = trim_history(m, 10, 100)
    assert out == [{"role": "user", "content": "x" * 500}]


def test_CHAT_05_output_only_role_and_content():
    m = [{"role": "user", "content": "hi", "id": 1, "created_at": "t"}]
    assert trim_history(m, 5, 100) == [{"role": "user", "content": "hi"}]

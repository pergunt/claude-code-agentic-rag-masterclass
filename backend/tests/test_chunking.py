from app.services.chunking import chunk_text

SIZE, OVERLAP = 1500, 200


def prose(n):
    return " ".join(f"Sentence number {i} talks about lake sampling at depth {i % 13}." for i in range(n))


def test_ING_09_chunks_never_exceed_size():
    chunks = chunk_text(prose(200), SIZE, OVERLAP)
    assert len(chunks) > 1
    assert all(len(c) <= SIZE for c in chunks)
    hard = chunk_text("x" * 10000, SIZE, OVERLAP)
    assert all(len(c) <= SIZE for c in hard)


def test_ING_09_consecutive_chunks_overlap():
    chunks = chunk_text(prose(200), SIZE, OVERLAP)
    for a, b in zip(chunks, chunks[1:]):
        assert b[:30] in a, "start of next chunk should reappear in previous chunk"


def test_ING_09_empty_or_whitespace_gives_no_chunks():
    assert chunk_text("", SIZE, OVERLAP) == []
    assert chunk_text("  \n\r\n\t ", SIZE, OVERLAP) == []


def test_ING_09_short_text_is_single_chunk():
    assert chunk_text("x" * 100, SIZE, OVERLAP) == ["x" * 100]


def test_ING_09_chunking_is_deterministic():
    t = prose(100)
    assert chunk_text(t, SIZE, OVERLAP) == chunk_text(t, SIZE, OVERLAP)

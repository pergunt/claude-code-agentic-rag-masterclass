SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split(text: str, size: int, separators: list[str]) -> list[str]:
    """Split text into pieces of at most `size` chars, keeping each separator attached to its piece."""
    if len(text) <= size:
        return [text]
    if not separators:  # last resort: hard cut
        return [text[i : i + size] for i in range(0, len(text), size)]
    sep, rest = separators[0], separators[1:]
    parts = text.split(sep)
    if len(parts) == 1:
        return _split(text, size, rest)
    pieces: list[str] = []
    for i, part in enumerate(parts):
        piece = part + sep if i < len(parts) - 1 else part
        if piece:
            pieces.extend(_split(piece, size, rest))
    return pieces


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Recursive character splitter: chunks of at most `size` chars, consecutive ones sharing up to `overlap`."""
    assert 0 <= overlap < size, "overlap must satisfy 0 <= overlap < size"
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for piece in _split(text, size, SEPARATORS):
        if current and current_len + len(piece) > size:
            chunks.append("".join(current))
            # Seed the next chunk with the trailing pieces, up to `overlap` chars.
            seed: list[str] = []
            seed_len = 0
            for prev in reversed(current):
                if seed_len + len(prev) > overlap:
                    break
                seed.insert(0, prev)
                seed_len += len(prev)
            if seed_len + len(piece) > size:
                seed, seed_len = [], 0
            current, current_len = seed, seed_len
        current.append(piece)
        current_len += len(piece)
    if current:
        chunks.append("".join(current))
    return [c for c in (chunk.strip() for chunk in chunks) if c]

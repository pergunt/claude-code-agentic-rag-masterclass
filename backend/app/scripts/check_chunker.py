"""Plain-assert checks for the chunker. Run: venv/bin/python -m app.scripts.check_chunker"""

import math
import re
from pathlib import Path

from app.services.chunking import chunk_text

SIZE, OVERLAP = 1500, 200
SAMPLE = Path(__file__).resolve().parents[3] / "test-data" / "ingestion" / "velmora-station.md"


def prose(n_sentences: int) -> str:
    return " ".join(f"Sentence number {i} talks about lake sampling at depth {i % 13}." for i in range(n_sentences))


def main() -> None:
    assert chunk_text("", SIZE, OVERLAP) == []
    assert chunk_text("  \n\r\n\t ", SIZE, OVERLAP) == []
    assert len(chunk_text("x" * 100, SIZE, OVERLAP)) == 1

    sample = SAMPLE.read_text()
    sample_chunks = chunk_text(sample, SIZE, OVERLAP)
    assert all(len(c) <= SIZE for c in sample_chunks)
    assert 2 <= len(sample_chunks) <= 3, len(sample_chunks)

    text = prose(200)
    chunks = chunk_text(text, SIZE, OVERLAP)
    assert len(chunks) > 1
    assert all(len(c) <= SIZE for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        # The start of each chunk reappears at the end of the previous one.
        assert b[:30] in a, "consecutive chunks do not overlap"

    hard = chunk_text("x" * 10000, SIZE, OVERLAP)
    assert len(hard) == math.ceil(10000 / SIZE), len(hard)
    assert all(len(c) <= SIZE for c in hard)

    for source in (text, sample):
        for sentence in re.split(r"(?<=\.)\s+", source.strip()):
            if len(sentence) <= SIZE:
                assert any(sentence.strip() in c for c in chunk_text(source, SIZE, OVERLAP)), sentence[:40]

    assert chunk_text(text, SIZE, OVERLAP) == chunks

    print("sample chunk count:", len(sample_chunks), "lengths:", [len(c) for c in sample_chunks])
    print("OK")


if __name__ == "__main__":
    main()

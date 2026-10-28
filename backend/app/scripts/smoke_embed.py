"""Embed a few strings and print sizes and similarities. Run: venv/bin/python -m app.scripts.smoke_embed"""

import math

from app.services.embeddings import embed_texts


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main() -> None:
    cat, kitten, tax = embed_texts(["A cat sat on the mat.", "A kitten rested on the rug.", "Quarterly corporate tax filing deadlines."])
    print(len(cat), len(kitten))
    print("related:", round(cosine(cat, kitten), 3))
    print("unrelated:", round(cosine(cat, tax), 3))
    assert cosine(cat, kitten) > cosine(cat, tax)


if __name__ == "__main__":
    main()

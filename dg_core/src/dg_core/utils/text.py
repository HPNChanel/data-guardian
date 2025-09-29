"""Text normalization helpers shared across modules."""
from __future__ import annotations

from typing import List, Sequence, Tuple


def to_text(data: str | bytes) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="surrogatepass")
    return data


def byte_offsets(text: str) -> List[int]:
    offsets: List[int] = [0]
    byte_index = 0
    for char in text:
        encoded = char.encode("utf-8", errors="surrogatepass")
        byte_index += len(encoded)
        offsets.append(byte_index)
    return offsets


def normalize(data: str | bytes) -> Tuple[str, Sequence[int]]:
    text = to_text(data)
    return text, byte_offsets(text)


__all__ = ["normalize", "byte_offsets", "to_text"]
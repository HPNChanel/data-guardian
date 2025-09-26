
from __future__ import annotations

import contextlib
import struct
from pathlib import Path
from typing import BinaryIO, Iterator, Tuple

from ..utils.errors import InvalidHeader
from .header import FileHeader

HEADER_SEPARATOR = b"\n\n"
CHUNK_STRUCT = struct.Struct(">II")


@contextlib.contextmanager
def open_encrypted_reader(path: Path) -> Iterator[Tuple[FileHeader, BinaryIO]]:
    with path.open("rb") as handle:
        header_line = handle.readline()
        if not header_line:
            raise InvalidHeader("Missing envelope header")
        header_json = header_line.rstrip(b"\r\n")
        separator = handle.readline()
        if separator not in (b"", b"\n", b"\r\n"):
            raise InvalidHeader("Malformed header separator")
        header = FileHeader.from_json(header_json.decode("utf-8"))
        yield header, handle

@contextlib.contextmanager
def open_encrypted_writer(path: Path, header: FileHeader) -> Iterator[BinaryIO]:
    with path.open("wb") as handle:
        handle.write(header.to_json().encode("utf-8"))
        handle.write(HEADER_SEPARATOR)
        yield handle


def iter_chunks(handle: BinaryIO) -> Iterator[Tuple[int, bytes]]:
    while True:
        chunk_header = handle.read(CHUNK_STRUCT.size)
        if not chunk_header:
            return
        if len(chunk_header) != CHUNK_STRUCT.size:
            raise InvalidHeader("Truncated chunk header")
        length, index = CHUNK_STRUCT.unpack(chunk_header)
        payload = handle.read(length)
        if len(payload) != length:
            raise InvalidHeader("Truncated ciphertext chunk")
        yield index, payload

def write_chunk(handle: BinaryIO, index: int, payload: bytes) -> None:
    if index < 0 or index >= 2**32:
        raise ValueError("Chunk index out of range")
    handle.write(CHUNK_STRUCT.pack(len(payload), index))
    handle.write(payload)


__all__ = ["HEADER_SEPARATOR", "iter_chunks", "open_encrypted_reader", "open_encrypted_writer", "write_chunk"]

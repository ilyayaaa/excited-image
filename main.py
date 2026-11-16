"""Validate the entry image and copy it byte for byte to /output/entry.png."""

import hashlib
import struct
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "assets" / "orca-dream.jpg"
DST = Path("/output/entry.png")
MAX_BYTES = 1_048_576
MAX_DIM = 1024

# Markers with no length field (standalone).
STANDALONE = {0x01, *range(0xD0, 0xD8)}
SOF_MARKERS = {0xC0: "SOF0", 0xC2: "SOF2"}


class InvalidImage(Exception):
    pass


def jpeg_dimensions(data: bytes) -> tuple[int, int, str]:
    """Walk JPEG segments until SOF0/SOF2; return (width, height, marker)."""
    pos = 2  # skip SOI
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise InvalidImage(f"expected marker at offset {pos}, found 0x{data[pos]:02X}")
        while pos < n and data[pos] == 0xFF:  # skip fill bytes
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1
        if marker in STANDALONE:
            continue
        if marker in (0xD9, 0xDA):  # EOI or SOS before any frame header
            break
        if pos + 2 > n:
            raise InvalidImage("truncated segment length")
        (length,) = struct.unpack(">H", data[pos:pos + 2])
        if length < 2 or pos + length > n:
            raise InvalidImage(f"bad segment length {length} at offset {pos}")
        if marker in SOF_MARKERS:
            if length < 7:
                raise InvalidImage("SOF segment too short")
            _precision, height, width = struct.unpack(">BHH", data[pos + 2:pos + 7])
            return width, height, SOF_MARKERS[marker]
        pos += length
    raise InvalidImage("no SOF0/SOF2 marker found")


def validate(data: bytes) -> tuple[int, int, str]:
    if len(data) > MAX_BYTES:
        raise InvalidImage(f"file is {len(data)} bytes, limit is {MAX_BYTES}")
    if data[:2] != b"\xff\xd8":
        raise InvalidImage("missing JPEG SOI (FF D8) at start")
    if data[-2:] != b"\xff\xd9":
        raise InvalidImage("missing JPEG EOI (FF D9) at end")
    width, height, sof = jpeg_dimensions(data)
    if width == 0 or height == 0:
        raise InvalidImage(f"invalid dimensions {width}x{height}")
    if width > MAX_DIM or height > MAX_DIM:
        raise InvalidImage(f"dimensions {width}x{height} exceed {MAX_DIM}x{MAX_DIM}")
    return width, height, sof


def main() -> int:
    try:
        data = SRC.read_bytes()
    except OSError as e:
        print(f"error: cannot read {SRC}: {e}", file=sys.stderr)
        return 1
    try:
        width, height, sof = validate(data)
    except InvalidImage as e:
        print(f"error: {SRC.name} is not a valid entry image: {e}", file=sys.stderr)
        return 1
    try:
        DST.parent.mkdir(parents=True, exist_ok=True)
        DST.write_bytes(data)
    except OSError as e:
        print(f"error: cannot write {DST}: {e}", file=sys.stderr)
        return 1
    print(f"OK: {SRC.name} {len(data)} bytes, {width}x{height} ({sof})")
    print(f"Wrote {DST} sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

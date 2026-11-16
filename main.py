"""make.fun ai-excited-01 entry: "The Whale Walked Out of the Museum".

Validates assets/whale-escape.jpg and copies it byte for byte to
/output/entry.png. Python 3 standard library only, no network.

Usage: python3 main.py [destination]   (default: /output/entry.png)
"""

import struct
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "assets" / "whale-escape.jpg"
DEFAULT_DST = Path("/output/entry.png")
MAX_BYTES = 1_048_576
MAX_SIDE = 1024

# Markers that stand alone, with no length field.
STANDALONE = {0x01, *range(0xD0, 0xD8)}  # TEM, RST0-RST7


class InvalidImage(Exception):
    pass


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Walk the JPEG segments and return (width, height) from SOF0/SOF2."""
    pos = 2  # skip SOI
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise InvalidImage(f"expected marker at offset {pos}, found 0x{data[pos]:02X}")
        # Skip fill bytes (0xFF padding before a marker).
        while pos < n and data[pos] == 0xFF:
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
            raise InvalidImage(f"bad segment length {length} for marker 0xFF{marker:02X}")
        if marker in (0xC0, 0xC2):  # SOF0 baseline, SOF2 progressive
            if length < 7:
                raise InvalidImage("SOF segment too short")
            _precision, height, width = struct.unpack(">BHH", data[pos + 2:pos + 7])
            return width, height
        pos += length
    raise InvalidImage("no SOF0/SOF2 frame header found")


def validate(data: bytes) -> tuple[int, int]:
    if len(data) > MAX_BYTES:
        raise InvalidImage(f"file is {len(data):,} bytes, limit is {MAX_BYTES:,}")
    if not data.startswith(b"\xFF\xD8"):
        raise InvalidImage("missing JPEG SOI marker (FF D8) at start")
    if not data.endswith(b"\xFF\xD9"):
        raise InvalidImage("missing JPEG EOI marker (FF D9) at end")
    width, height = jpeg_dimensions(data)
    if width == 0 or height == 0:
        raise InvalidImage(f"invalid dimensions {width}x{height}")
    if width > MAX_SIDE or height > MAX_SIDE:
        raise InvalidImage(f"dimensions {width}x{height} exceed {MAX_SIDE}x{MAX_SIDE}")
    return width, height


def main() -> int:
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DST
    try:
        data = SRC.read_bytes()
    except OSError as exc:
        print(f"error: cannot read {SRC}: {exc}", file=sys.stderr)
        return 1
    try:
        width, height = validate(data)
    except InvalidImage as exc:
        print(f"error: {SRC.name} is not a valid entry image: {exc}", file=sys.stderr)
        return 1
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    except OSError as exc:
        print(f"error: cannot write {dst}: {exc}", file=sys.stderr)
        return 1
    print(f"OK {SRC.name}: {len(data):,} bytes, {width}x{height} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

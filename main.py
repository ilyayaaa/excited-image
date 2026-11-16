"""Validate and copy the entry image to /output/entry.png (make.fun ai-excited-01).

Standard library only, no network. Exits non-zero with a clear message if the
image is not a valid-looking JPEG within the bounty limits.
"""

import struct
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "assets" / "orca-dream.jpg"
DST = Path("/output/entry.png")

MAX_BYTES = 1_048_576
MAX_SIDE = 1024

SOF_MARKERS = {0xC0: "SOF0 (baseline)", 0xC2: "SOF2 (progressive)"}
# Markers that carry no length field.
STANDALONE = {0x01, *range(0xD0, 0xD8)}


class ImageError(Exception):
    pass


def jpeg_dimensions(data: bytes) -> tuple[int, int, str]:
    """Walk JPEG segments and return (width, height, sof_name) from SOF0/SOF2."""
    pos = 2  # skip SOI
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise ImageError(f"expected marker at offset {pos}, found 0x{data[pos]:02X}")
        # Skip any fill bytes (0xFF padding).
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
            raise ImageError("truncated segment length")
        (length,) = struct.unpack(">H", data[pos : pos + 2])
        if length < 2 or pos + length > n:
            raise ImageError(f"bad segment length {length} at offset {pos}")
        if marker in SOF_MARKERS:
            if length < 7:
                raise ImageError("SOF segment too short")
            _precision, height, width = struct.unpack(">BHH", data[pos + 2 : pos + 7])
            return width, height, SOF_MARKERS[marker]
        pos += length
    raise ImageError("no SOF0/SOF2 frame header found")


def validate(data: bytes) -> tuple[int, int, str]:
    size = len(data)
    if size > MAX_BYTES:
        raise ImageError(f"file is {size:,} bytes, limit is {MAX_BYTES:,}")
    if data[:2] != b"\xFF\xD8":
        raise ImageError("missing JPEG SOI marker (FF D8) at start of file")
    if data[-2:] != b"\xFF\xD9":
        raise ImageError("missing JPEG EOI marker (FF D9) at end of file")
    width, height, sof = jpeg_dimensions(data)
    if width == 0 or height == 0:
        raise ImageError(f"invalid dimensions {width}x{height}")
    if width > MAX_SIDE or height > MAX_SIDE:
        raise ImageError(f"dimensions {width}x{height} exceed {MAX_SIDE}x{MAX_SIDE}")
    return width, height, sof


def main() -> int:
    try:
        data = SRC.read_bytes()
    except OSError as exc:
        print(f"error: cannot read {SRC}: {exc}", file=sys.stderr)
        return 1
    try:
        width, height, sof = validate(data)
    except ImageError as exc:
        print(f"error: {SRC.name} failed validation: {exc}", file=sys.stderr)
        return 2
    try:
        DST.parent.mkdir(parents=True, exist_ok=True)
        DST.write_bytes(data)
    except OSError as exc:
        print(f"error: cannot write {DST}: {exc}", file=sys.stderr)
        return 3
    print(f"OK {SRC.name}: {len(data):,} bytes, {width}x{height} ({sof})")
    print(f"Copied -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import re
import zlib


def decompressed_streams(pdf_bytes: bytes) -> list[bytes]:
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        try:
            streams.append(zlib.decompress(match.group(1).rstrip(b"\r\n")))
        except zlib.error:
            continue
    return streams


def glyph_to_text_maps(streams: list[bytes]) -> list[dict[int, str]]:
    maps = []
    for stream in streams:
        if b"beginbfchar" not in stream and b"beginbfrange" not in stream:
            continue
        mapping: dict[int, str] = {}
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", stream, re.DOTALL):
            for source_hex, target_hex in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
            ):
                mapping[int(source_hex, 16)] = bytes.fromhex(
                    target_hex.decode("ascii")
                ).decode("utf-16-be")
        for block in re.findall(rb"beginbfrange(.*?)endbfrange", stream, re.DOTALL):
            for low_hex, high_hex, target_hex in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
            ):
                for offset in range(int(high_hex, 16) - int(low_hex, 16) + 1):
                    mapping[int(low_hex, 16) + offset] = chr(int(target_hex, 16) + offset)
        if mapping:
            maps.append(mapping)
    return maps


_LITERAL_STRING_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


def shown_string_bytes(stream: bytes) -> list[bytes]:
    strings = []
    position = 0
    while position < len(stream):
        if stream[position : position + 1] == b"(":
            literal, position = _scanned_literal_string(stream, position + 1)
            strings.append(literal)
        elif stream[position : position + 1] == b"<" and stream[
            position + 1 : position + 2
        ] != b"<":
            hex_match = re.match(rb"<([0-9A-Fa-f\s]*)>", stream[position:], re.DOTALL)
            if hex_match is None:
                position += 1
                continue
            hex_digits = re.sub(rb"\s", b"", hex_match.group(1)).decode("ascii")
            strings.append(bytes.fromhex(hex_digits))
            position += len(hex_match.group(0))
        else:
            position += 1
    return strings


def _scanned_literal_string(stream: bytes, position: int) -> tuple[bytes, int]:
    decoded = bytearray()
    depth = 1
    while position < len(stream) and depth > 0:
        character = stream[position : position + 1]
        if character == b"\\":
            octal_digits = re.match(rb"\\([0-7]{1,3})", stream[position:])
            if octal_digits is not None:
                decoded.append(int(octal_digits.group(1), 8))
                position += len(octal_digits.group(0))
                continue
            escape_character = stream[position + 1 : position + 2]
            decoded += _LITERAL_STRING_ESCAPES.get(escape_character, escape_character)
            position += 2
            continue
        if character == b"(":
            depth += 1
        elif character == b")":
            depth -= 1
            if depth == 0:
                position += 1
                break
        decoded += character
        position += 1
    return bytes(decoded), position


def shown_glyph_ids(stream: bytes) -> list[int]:
    glyph_ids = []
    for glyph_bytes in shown_string_bytes(stream):
        for position in range(0, len(glyph_bytes) - 1, 2):
            glyph_ids.append(int.from_bytes(glyph_bytes[position : position + 2], "big"))
    return glyph_ids


def extracted_text_variants(pdf_bytes: bytes) -> list[str]:
    streams = decompressed_streams(pdf_bytes)
    content_streams = [stream for stream in streams if b"TJ" in stream or b"Tj" in stream]
    variants = []
    for mapping in glyph_to_text_maps(streams):
        for stream in content_streams:
            variants.append(
                "".join(mapping.get(glyph_id, "") for glyph_id in shown_glyph_ids(stream))
            )
    return variants


def page_count(pdf_bytes: bytes) -> int:
    searchable_chunks = [pdf_bytes, *decompressed_streams(pdf_bytes)]
    return sum(
        len(re.findall(rb"/Type\s*/Page[^s]", chunk)) for chunk in searchable_chunks
    )

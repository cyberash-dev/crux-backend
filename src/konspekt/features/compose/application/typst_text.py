_TYPST_SPECIAL_CHARACTERS = "\\#*_@$<>[]"


def escaped(text: str) -> str:
    return "".join(
        f"\\{character}" if character in _TYPST_SPECIAL_CHARACTERS else character
        for character in text
    )


def string_literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

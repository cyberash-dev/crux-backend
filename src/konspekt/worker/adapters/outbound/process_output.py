_TAIL_LINE_COUNT = 5
_TAIL_MAX_CHARACTERS = 2000


def error_tail(stderr: str) -> str:
    non_empty_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return "\n".join(non_empty_lines[-_TAIL_LINE_COUNT:])[-_TAIL_MAX_CHARACTERS:]

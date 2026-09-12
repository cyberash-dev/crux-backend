def duration_label(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def coverage_percent_label(coverage_ratio: float) -> str:
    return f"{coverage_ratio * 100:.1f}%"

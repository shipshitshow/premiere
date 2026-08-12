"""Pure audio-effect name matching. Import-safe without FastMCP."""

DEFAULT_AUDIO_CLEANUP = ["DeNoise", "DeReverb"]


def resolve_audio_effect_labels(labels: list, available: list) -> tuple[list, list]:
    """Fuzzy-match requested labels against live Premiere effect names.

    Precedence: exact, then prefix, then the requested label is a substring
    of an available name. We deliberately do NOT match when an available
    name is a substring of the requested label — that turned "DeReverb"
    into "Reverb", the opposite effect.

    Returns (resolved_names, unmatched_labels).
    """
    lower_available = [(name, name.lower()) for name in available]
    resolved = []
    unmatched = []
    for label in labels:
        needle = label.lower()
        match = (
            next((name for name, low in lower_available if low == needle), None)
            or next((name for name, low in lower_available if low.startswith(needle)), None)
            or next((name for name, low in lower_available if needle in low), None)
        )
        if match:
            resolved.append(match)
        else:
            unmatched.append(label)
    return resolved, unmatched

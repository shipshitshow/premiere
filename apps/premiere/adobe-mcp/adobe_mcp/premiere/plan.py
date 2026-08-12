"""Pure cut-planning helpers.

Validate and frame-snap removal ranges without talking to Premiere.
"""

import math

from .constants import TICKS_PER_SECOND
from .layout import clips_from_layout


def sec_to_ticks(seconds: float) -> int:
    """Convert timeline seconds to Premiere ticks (truncating, sub-frame exact)."""
    return int(seconds * TICKS_PER_SECOND)


def snap_to_frame(ticks: int, frame_ticks_value: int, mode: str = "round") -> int:
    """Snap a tick value to a whole-frame boundary."""
    if not frame_ticks_value or frame_ticks_value <= 0:
        return int(ticks)
    q = ticks / frame_ticks_value
    if mode == "floor":
        frames = math.floor(q)
    elif mode == "ceil":
        frames = math.ceil(q)
    else:
        frames = round(q)
    return int(frames * frame_ticks_value)


def validate_segments(silence_segments: list):
    """Type/shape/order-check every segment BEFORE anything is cut.

    A malformed segment used to raise mid-batch, after earlier segments had
    already been extracted, leaving the timeline half-cut with no verification.
    Returns (parsed, errors); a non-empty errors list must refuse the batch.
    """
    parsed, errors = [], []
    for i, seg in enumerate(silence_segments):
        if not isinstance(seg, dict):
            errors.append(
                {
                    "index": i,
                    "segment": seg,
                    "error": "Segment must be a dict {'start': sec, 'end': sec}.",
                }
            )
            continue
        start, end = seg.get("start"), seg.get("end")
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or not math.isfinite(start)
            or not math.isfinite(end)
        ):
            errors.append(
                {
                    "index": i,
                    "segment": seg,
                    "error": "'start' and 'end' must be finite numbers (timeline seconds).",
                }
            )
            continue
        if start < 0:
            errors.append({"index": i, "segment": seg, "error": "'start' must be >= 0."})
            continue
        if end <= start:
            errors.append(
                {
                    "index": i,
                    "segment": seg,
                    "error": "'end' must be greater than 'start' (swapped range?).",
                }
            )
            continue
        parsed.append({"index": i, "start": float(start), "end": float(end)})
    return parsed, errors


def plan_cuts(parsed: list, frame_ticks_value, duration_ticks, frame_snap: bool):
    """Turn validated segments into an executable cut plan.

    Frame-snaps (when possible), merges overlapping/touching ranges so
    expected-removal math cannot double-count, and bounds-checks against the
    sequence duration. Returns (cuts sorted end->start, errors, warnings).
    A range that starts beyond the sequence end is an ERROR (the removal list
    belongs to a different timeline state), not a silent drop.
    """
    errors, warnings = [], []
    cuts = []
    for seg in parsed:
        in_ticks = sec_to_ticks(seg["start"])
        out_ticks = sec_to_ticks(seg["end"])
        if frame_snap and frame_ticks_value:
            in_ticks = snap_to_frame(in_ticks, frame_ticks_value, "round")
            out_ticks = snap_to_frame(out_ticks, frame_ticks_value, "round")
            if out_ticks <= in_ticks:
                out_ticks = in_ticks + frame_ticks_value  # never collapse to zero length
                warnings.append(
                    f"Segment {seg['start']}-{seg['end']}s collapsed to zero frames "
                    "after snapping; widened to one frame."
                )
        cuts.append({"sources": [dict(seg)], "inTicks": in_ticks, "outTicks": out_ticks})

    cuts.sort(key=lambda c: c["inTicks"])
    merged = []
    for c in cuts:
        if merged and c["inTicks"] <= merged[-1]["outTicks"]:
            prev = merged[-1]
            prev["outTicks"] = max(prev["outTicks"], c["outTicks"])
            prev["sources"].extend(c["sources"])
            warnings.append(
                f"Overlapping/touching segments merged into one cut at "
                f"{prev['inTicks'] / TICKS_PER_SECOND:.3f}-"
                f"{prev['outTicks'] / TICKS_PER_SECOND:.3f}s."
            )
        else:
            merged.append(c)

    if duration_ticks:
        overshoot_tol = max(frame_ticks_value or 0, sec_to_ticks(0.1))
        for c in merged:
            if c["inTicks"] >= duration_ticks:
                errors.append(
                    {
                        "segment": c["sources"],
                        "error": (
                            f"Range starts at {c['inTicks'] / TICKS_PER_SECOND:.3f}s but the "
                            f"sequence ends at {duration_ticks / TICKS_PER_SECOND:.3f}s — the "
                            "removal list does not match this timeline."
                        ),
                    }
                )
            elif c["outTicks"] > duration_ticks:
                overshoot = c["outTicks"] - duration_ticks
                if overshoot <= overshoot_tol:
                    c["outTicks"] = duration_ticks
                    warnings.append(
                        f"Cut ending at {(duration_ticks + overshoot) / TICKS_PER_SECOND:.3f}s "
                        "clamped to the sequence end."
                    )
                else:
                    errors.append(
                        {
                            "segment": c["sources"],
                            "error": (
                                f"Range ends {overshoot / TICKS_PER_SECOND:.3f}s past the sequence "
                                "end — the removal list does not match this timeline."
                            ),
                        }
                    )

    for c in merged:
        c["lengthTicks"] = c["outTicks"] - c["inTicks"]
        c["inSeconds"] = round(c["inTicks"] / TICKS_PER_SECOND, 4)
        c["outSeconds"] = round(c["outTicks"] / TICKS_PER_SECOND, 4)
        c["lengthSeconds"] = round(c["lengthTicks"] / TICKS_PER_SECOND, 4)
        if frame_ticks_value:
            c["lengthFrames"] = round(c["lengthTicks"] / frame_ticks_value, 2)

    merged.sort(key=lambda c: c["inTicks"], reverse=True)  # process end -> start
    return merged, errors, warnings


def probe_from_layout(layout: dict) -> dict:
    """Snapshot of the numbers an Extract changes: duration + PER-LANE content.

    Content is tracked per (kind, trackIndex) lane, not summed per kind: an
    Extract removes the range from EVERY targeted track, so on a timeline with
    two mic tracks a per-kind sum would drop by twice the cut length and a
    correct cut would read as a mismatch.
    """
    video, audio = clips_from_layout(layout)
    lanes = {}
    for c in video + audio:
        key = (c["kind"], c["trackIndex"])
        lanes[key] = lanes.get(key, 0) + (c["end"] - c["start"])
    duration = max(
        max((c["end"] for c in video), default=0),
        max((c["end"] for c in audio), default=0),
    )
    return {"durationTicks": duration, "lanes": lanes}


def removed_since(before: dict, after: dict) -> int:
    """Largest single-lane removal signal (or duration change).

    Duration alone can miss a landed Extract when an untargeted track (music
    bed, full-length title) still ends at the old timecode; the per-lane
    content deltas catch that case. The MAX single-lane delta — not a sum —
    approximates the cut length: a targeted lane fully covered by the range
    loses exactly the cut length, and each lane can lose at most that much.
    """
    lane_deltas = [
        before["lanes"].get(key, 0) - after["lanes"].get(key, 0) for key in before["lanes"]
    ]
    return max([before["durationTicks"] - after["durationTicks"]] + lane_deltas)

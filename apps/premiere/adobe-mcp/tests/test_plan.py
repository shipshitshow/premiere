"""Cut planner: validation, snap, merge, bounds."""

import math

from adobe_mcp.premiere.constants import TICKS_PER_SECOND
from adobe_mcp.premiere.plan import plan_cuts, validate_segments


FT = int(TICKS_PER_SECOND / 24)


def test_rejects_bool_as_number():
    parsed, errors = validate_segments([{"start": True, "end": 2}])
    assert parsed == []
    assert errors and "finite" in errors[0]["error"]


def test_rejects_nan_and_swapped():
    _, nan_errors = validate_segments([{"start": 1, "end": math.nan}])
    assert nan_errors
    _, swap_errors = validate_segments([{"start": 5, "end": 1}])
    assert swap_errors and "greater" in swap_errors[0]["error"]


def test_rejects_non_dict():
    _, errors = validate_segments(["10-12"])
    assert errors


def test_merges_overlapping_ranges():
    parsed, errors = validate_segments(
        [{"start": 10, "end": 12}, {"start": 11.5, "end": 14}]
    )
    assert not errors
    cuts, plan_errors, warnings = plan_cuts(parsed, FT, 100 * TICKS_PER_SECOND, True)
    assert not plan_errors
    assert len(cuts) == 1
    assert any("merged" in w.lower() for w in warnings)
    assert cuts[0]["lengthSeconds"] == 4.0


def test_overshoot_clamp_vs_error():
    parsed, _ = validate_segments([{"start": 9.0, "end": 10.05}])
    cuts, errors, warnings = plan_cuts(parsed, FT, 10 * TICKS_PER_SECOND, True)
    assert not errors
    assert cuts[0]["outTicks"] == 10 * TICKS_PER_SECOND
    assert any("clamped" in w for w in warnings)

    parsed, _ = validate_segments([{"start": 8, "end": 12}])
    _, errors, _ = plan_cuts(parsed, FT, 10 * TICKS_PER_SECOND, True)
    assert errors


def test_range_past_end_is_error():
    parsed, _ = validate_segments([{"start": 20, "end": 22}])
    _, errors, _ = plan_cuts(parsed, FT, 10 * TICKS_PER_SECOND, True)
    assert errors


def test_snap_to_zero_width_widens_one_frame():
    # A tiny range that snaps both ends to the same frame.
    parsed, _ = validate_segments([{"start": 1.001, "end": 1.002}])
    cuts, errors, warnings = plan_cuts(parsed, FT, 10 * TICKS_PER_SECOND, True)
    assert not errors
    assert cuts[0]["lengthTicks"] == FT
    assert any("widened" in w for w in warnings)

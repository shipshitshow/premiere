"""Gap detection, lane roles, A/V junctions."""

from adobe_mcp.premiere.constants import TICKS_PER_SECOND
from adobe_mcp.premiere.layout import (
    av_misalignments,
    clips_from_layout,
    detect_gaps,
    frame_ticks,
    lane_roles,
    summarize_layout,
)

from helpers import make_layout, ticks

FT = int(TICKS_PER_SECOND / 24)


def test_ntsc_frame_ticks_uses_exact_rational():
    layout = make_layout([[(0, 10)]], [[(0, 10)]], fps=29.97)
    # Override with the float Premiere actually returns, no ticksPerFrame.
    layout["ticksPerFrame"] = None
    layout["frameRateValue"] = 29.97
    tpf = frame_ticks(layout)
    expected = int(round(TICKS_PER_SECOND * 1001 / (30 * 1000)))
    assert tpf == expected


def test_packed_program_bed_zero_gaps():
    layout = make_layout([[(0, 5), (5, 10)]], [[(0, 5), (5, 10)]])
    summary = summarize_layout(layout)
    assert summary["gapCount"] == 0
    assert summary["overlayGapCount"] == 0
    assert summary["laneRoles"] == {"a0": "program", "v0": "program"}


def test_overlay_stinger_does_not_fail_packed():
    # Program bed packed; V1/A1 hold two late stingers with holes.
    layout = make_layout(
        [[(0, 20)], [(2, 3), (10, 11)]],
        [[(0, 20)], [(2, 3), (10, 11)]],
    )
    summary = summarize_layout(layout)
    assert summary["laneRoles"]["v0"] == "program"
    assert summary["laneRoles"]["v1"] == "overlay"
    assert summary["gapCount"] == 0
    assert summary["overlayGapCount"] > 0
    assert summary["allLaneGapCount"] > 0


def test_broken_program_bed_with_leading_gap_stays_program():
    # Failed extract: 2s hole at the head, remaining clips still most of the seq.
    layout = make_layout([[(2, 20)]], [[(2, 20)]])
    summary = summarize_layout(layout)
    assert summary["laneRoles"]["v0"] == "program"
    assert summary["laneRoles"]["a0"] == "program"
    assert summary["gapCount"] == 2
    assert all(g["leading"] for g in summary["gaps"] if g["lane"] == "program")


def test_late_contiguous_multi_clip_bed_is_program():
    # Leading hole + two packed clips covering < 50% of duration.
    layout = make_layout([[(12, 14), (14, 16)]], [[(12, 14), (14, 16)]])
    # Sequence duration is 16s; content is 4s (< 50%) but 2 contiguous clips.
    summary = summarize_layout(layout)
    assert summary["laneRoles"]["v0"] == "program"
    assert summary["gapCount"] == 2


def test_single_late_stinger_is_overlay():
    layout = make_layout([[(0, 20)], [(15, 16)]], [[(0, 20)]])
    summary = summarize_layout(layout)
    assert summary["laneRoles"]["v1"] == "overlay"
    assert summary["gapCount"] == 0


def test_one_frame_drift_is_misalignment():
    video, audio = clips_from_layout(
        make_layout([[(0, 5), (5, 10)]], [[(0, 5), (5 + FT / TICKS_PER_SECOND, 10)]])
    )
    # Force the audio second clip to start exactly one frame late.
    audio[1]["start"] = ticks(5) + FT
    misses = av_misalignments(video, audio, FT)
    assert misses
    assert any(m["side"] == "audio" for m in misses)


def test_subframe_offset_is_not_misalignment():
    video, audio = clips_from_layout(make_layout([[(0, 5), (5, 10)]], [[(0, 5), (5, 10)]]))
    audio[1]["start"] = ticks(5) + FT // 4
    misses = av_misalignments(video, audio, FT)
    assert misses == []


def test_detect_gaps_reports_leading_and_inter():
    clips, _ = clips_from_layout(make_layout([[(1, 3), (5, 7)]], []))
    gaps = detect_gaps(clips, FT)
    kinds = {(g["leading"], round(g["gapSeconds"], 2)) for g in gaps}
    assert (True, 1.0) in kinds
    assert (False, 2.0) in kinds

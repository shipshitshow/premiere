"""Cut verification math and next-step copy."""

from adobe_mcp.premiere.constants import TICKS_PER_SECOND
from adobe_mcp.premiere.layout import summarize_layout
from adobe_mcp.premiere.plan import probe_from_layout, removed_since
from adobe_mcp.premiere.audio_effects import resolve_audio_effect_labels
from adobe_mcp.premiere.verify import cut_next_steps, verify_cut

from helpers import make_layout

FT = int(TICKS_PER_SECOND / 24)


def test_removed_since_uses_max_lane_not_sum():
    # 1 video + 2 audio tracks, each lose 10s.
    before = probe_from_layout(
        make_layout([[(0, 30)]], [[(0, 30)], [(0, 30)]])
    )
    after = probe_from_layout(
        make_layout([[(0, 20)]], [[(0, 20)], [(0, 20)]])
    )
    assert removed_since(before, after) == 10 * TICKS_PER_SECOND


def test_verify_cut_does_not_double_count_two_audio_tracks():
    before = summarize_layout(make_layout([[(0, 30)]], [[(0, 30)], [(0, 30)]]))
    after_layout = make_layout([[(0, 20)]], [[(0, 20)], [(0, 20)]])
    result = verify_cut(before, after_layout, 10 * TICKS_PER_SECOND, FT, cut_count=1)
    assert result["verified"] is True
    assert result["packed"] is True
    assert abs(result["actualRemovedSeconds"] - 10.0) < 0.05


def test_verify_cut_kind_sum_would_have_failed():
    """Guard the old bug: kind-sum audio removal is 20s, expected is 10s."""
    before = summarize_layout(make_layout([[(0, 30)]], [[(0, 30)], [(0, 30)]]))
    after = summarize_layout(make_layout([[(0, 20)]], [[(0, 20)], [(0, 20)]]))
    kind_sum = before["audioContentTicks"] - after["audioContentTicks"]
    assert kind_sum == 20 * TICKS_PER_SECOND
    result = verify_cut(before, make_layout([[(0, 20)]], [[(0, 20)], [(0, 20)]]),
                        10 * TICKS_PER_SECOND, FT, cut_count=1)
    assert result["actualRemovedSeconds"] != 20.0
    assert result["verified"] is True


def test_cut_next_steps_never_recommends_unsafe_tools():
    verification = {
        "verified": False,
        "packed": False,
        "avSynced": True,
        "newGapsIntroduced": 0,
    }
    steps = cut_next_steps(verification, "seq-1")
    blob = " ".join(steps).lower()
    assert "click into it and ripple-delete" not in blob
    assert "do not ripple-delete" in blob
    assert "set_clip_position" in blob
    assert "close_gap_recovery" in blob


def test_cut_next_steps_clean_cut():
    steps = cut_next_steps(
        {"verified": True, "packed": True, "avSynced": True}, "seq-1"
    )
    assert any("verified" in s.lower() for s in steps)


def test_dereverb_does_not_match_reverb():
    resolved, unmatched = resolve_audio_effect_labels(
        ["DeReverb", "DeNoise"],
        ["Reverb", "DeReverb", "DeNoise", "Echo"],
    )
    assert resolved == ["DeReverb", "DeNoise"]
    assert unmatched == []


def test_unmatched_audio_label():
    resolved, unmatched = resolve_audio_effect_labels(["Vocal Enhancer"], ["DeNoise"])
    assert resolved == []
    assert unmatched == ["Vocal Enhancer"]

"""Pure cut-verification helpers.

Compare a pre-cut layout summary to a post-cut layout without talking
to Premiere. The live wrapper in server.py fetches the after-layout
and then calls these.
"""

from .constants import TICKS_PER_SECOND
from .layout import (
    av_misalignments,
    clips_from_layout,
    gaps_by_lane,
    lane_roles,
    program_clips,
    summarize_layout,
)


def _actual_removed_ticks(before: dict, after: dict) -> int:
    """Per-lane max removal, matching ``removed_since``.

    Kind-summed videoContentTicks / audioContentTicks double-count a
    correct Extract on 1 video + 2 targeted audio tracks. Per-lane max
    is the cut length on every targeted lane.
    """
    before_lanes = before.get("laneContent") or {}
    after_lanes = after.get("laneContent") or {}
    if before_lanes:
        lane_deltas = [
            before_lanes.get(key, 0) - after_lanes.get(key, 0) for key in before_lanes
        ]
        duration_delta = (before.get("durationTicks") or 0) - after.get("durationTicks", 0)
        return max([duration_delta, *lane_deltas])

    # Older summaries without laneContent: fall back to the kind-sum max.
    v_removed = before.get("videoContentTicks", 0) - after.get("videoContentTicks", 0)
    a_removed = before.get("audioContentTicks", 0) - after.get("audioContentTicks", 0)
    return max(v_removed, a_removed)


def verify_cut(
    before: dict,
    after_layout: dict,
    expected_removed_ticks: int,
    frame_ticks_value,
    cut_count=1,
):
    """Compare the post-cut layout to the pre-cut baseline.

    Returns {verified, packed, avSynced, ...}. ``verified`` is True only when the
    right amount of content was removed, the cut introduced no new gaps, and
    video/audio still cut at the same timecodes (frame-accurate sync). It is None
    when no usable baseline was captured (cannot confirm a delta), and False when
    any of those checks fail.

    The two halves the user cares about are surfaced explicitly:
      - ``packed``   — True when the PROGRAM bed is back to back (zero program
        gaps). Overlay-lane gaps are reported separately and do not fail this.
      - ``avSynced`` — True when every PROGRAM cut lands on the same frame for
        V and A.
    """
    after = summarize_layout(after_layout)
    a_video, a_audio = clips_from_layout(after_layout)

    if not before or before.get("error") or before.get("durationTicks") is None:
        return {
            "verified": None,
            "reason": "No usable pre-cut baseline; cannot confirm the change.",
            "packed": after["gapCount"] == 0,
            "after": {
                k: after.get(k)
                for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")
            },
        }

    ft = frame_ticks_value or after.get("frameTicks") or int(TICKS_PER_SECOND / 24)

    v_removed = before.get("videoContentTicks", 0) - after.get("videoContentTicks", 0)
    a_removed = before.get("audioContentTicks", 0) - after.get("audioContentTicks", 0)
    actual_removed = _actual_removed_ticks(before, after)

    # Slack scales with the NUMBER of cuts: frame-snapping each of a cut's two
    # boundaries by up to half a frame moves the removed length by at most one
    # whole frame per cut. The tolerance is exactly that budget (with a 2-frame
    # floor for a single cut) — it never balloons on a large batch and so cannot
    # silently confirm a partial cut. Because removed_close is bounded by this on
    # BOTH sides, an under-removal beyond the budget already fails removed_close.
    removed_tol = max(2 * ft, cut_count * ft)
    duration_changed = actual_removed >= ft
    removed_close = abs(actual_removed - expected_removed_ticks) <= removed_tol
    under_removed = (expected_removed_ticks - actual_removed) > removed_tol

    packed = after["gapCount"] == 0
    before_lanes = gaps_by_lane(before.get("gaps", []))
    after_lanes = gaps_by_lane(after["gaps"])
    new_gap_lanes = [lane for lane, n in after_lanes.items() if n > before_lanes.get(lane, 0)]
    new_gap_count = sum(
        n - before_lanes.get(lane, 0)
        for lane, n in after_lanes.items()
        if n > before_lanes.get(lane, 0)
    )
    no_new_gaps = not new_gap_lanes

    a_roles = lane_roles(a_video + a_audio, after.get("durationTicks", 0), ft)
    pv, pa = program_clips(a_video, a_roles), program_clips(a_audio, a_roles)
    av_applicable = bool(pv) and bool(pa)
    misalignments = av_misalignments(pv, pa, ft) if av_applicable else []
    if before.get("videoClipCount") and before.get("audioClipCount") and a_video and a_audio:
        end_skew = abs(
            (before["videoEndTicks"] - after["videoEndTicks"])
            - (before["audioEndTicks"] - after["audioEndTicks"])
        )
        end_skew_ok = end_skew <= 2 * ft
    else:
        end_skew_ok = True
    av_synced = (not misalignments) and end_skew_ok

    verified = bool(duration_changed and removed_close and no_new_gaps and av_synced)

    warnings = []
    if not duration_changed:
        warnings.append(
            "Sequence duration did not change — the Extract keystroke likely did not land, "
            "or a DIFFERENT sequence is the active/focused Timeline. Confirm the target "
            "sequence is the active one and Premiere is frontmost with the Timeline focused."
        )
    if not no_new_gaps:
        lanes = ", ".join(f"{k}{ti}" for (k, ti) in new_gap_lanes)
        warnings.append(
            f"The cut INTRODUCED {new_gap_count} new gap(s) on lane(s) {lanes} — clips are "
            "not back to back (a track was likely not targeted). Do not close them with "
            "set_clip_position/split/trim; report for manual packing."
        )
    elif not packed:
        warnings.append(
            f"{after['gapCount']} pre-existing program-bed gap(s) remain elsewhere on the "
            "timeline (not introduced by this cut). The sequence is not fully back to back."
        )
    if duration_changed and not removed_close:
        warnings.append(
            f"Removed ~{actual_removed / TICKS_PER_SECOND:.2f}s but expected "
            f"~{expected_removed_ticks / TICKS_PER_SECOND:.2f}s."
        )
    elif under_removed:
        warnings.append(
            f"Removed ~{actual_removed / TICKS_PER_SECOND:.2f}s, ~"
            f"{(expected_removed_ticks - actual_removed) / TICKS_PER_SECOND:.2f}s short of expected — "
            "some segments may not have been extracted."
        )
    if misalignments:
        spots = ", ".join(f"{m['side']}@{m['seconds']}s" for m in misalignments[:6])
        warnings.append(
            f"AUDIO/VIDEO OUT OF SYNC at {len(misalignments)} cut point(s): {spots}. "
            "A cut landed on a different frame for video vs audio."
        )
    elif not end_skew_ok:
        warnings.append(
            "Video and audio ends shifted by different amounts — possible A/V desync; "
            "check that every track you meant to cut was targeted."
        )

    return {
        "verified": verified,
        "packed": packed,
        "avSynced": av_synced,
        "expectedRemovedSeconds": round(expected_removed_ticks / TICKS_PER_SECOND, 4),
        "actualRemovedSeconds": round(actual_removed / TICKS_PER_SECOND, 4),
        "expectedRemovedFrames": round(expected_removed_ticks / ft, 2) if ft else None,
        "actualRemovedFrames": round(actual_removed / ft, 2) if ft else None,
        "videoRemovedSeconds": round(v_removed / TICKS_PER_SECOND, 4),
        "audioRemovedSeconds": round(a_removed / TICKS_PER_SECOND, 4),
        "newGapsIntroduced": new_gap_count,
        "residualGaps": after["gaps"],
        "avMisalignments": misalignments,
        "before": {
            k: before.get(k)
            for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")
        },
        "after": {
            k: after.get(k)
            for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")
        },
        "warnings": warnings,
    }


def cut_next_steps(verification: dict, sequence_id: str) -> list:
    """Plain next-step instructions for the user, derived from verification.

    Never recommends ripple-delete, set_clip_position, split, or trim.
    Tiny native Extract gaps point at close_gap_recovery; anything else stops.
    """
    if not verification:
        return []
    if (
        verification.get("verified")
        and verification.get("packed")
        and verification.get("avSynced")
    ):
        return [
            "Cut verified: back to back, audio in sync, expected amount removed.",
            "Finish the edit in Premiere (color, audio polish, b-roll). Save when done.",
        ]
    steps = []
    if verification.get("verified") is None:
        steps.append(
            "Verification could not read the layout back — re-run "
            f"verify_sequence_layout('{sequence_id}') and inspect manually before trusting the cut."
        )
        return steps
    if verification.get("avSynced") is False:
        steps.append(
            "AUDIO/VIDEO OUT OF SYNC. In Premiere, undo the last Extract (Cmd+Z), confirm "
            "Linked Selection is ON and that BOTH the video and its audio track are targeted, "
            "then re-run the cut. Do not close gaps with move/trim."
        )
    if verification.get("newGapsIntroduced"):
        steps.append(
            "A gap opened (clips not back to back). Undo (Cmd+Z) and re-cut with Extract "
            "(not Lift/Delete); do not patch the gap with set_clip_position/trim."
        )
    elif verification.get("packed") is False:
        steps.append(
            "A program-bed gap remains. If these are tiny native Extract gaps "
            "(about 0.03-0.07s) after a cut that could not frame-snap, run "
            f"close_gap_recovery('{sequence_id}'). Otherwise stop and report the "
            "residualGaps for manual packing. Do not ripple-delete or use "
            "set_clip_position / split / trim."
        )
    if verification.get("verified") is False and not steps:
        steps.append(
            f"Cut not confirmed — run verify_sequence_layout('{sequence_id}') and inspect "
            "the warnings before continuing."
        )
    steps.append(f"After fixing, re-run verify_sequence_layout('{sequence_id}') to re-validate.")
    return steps

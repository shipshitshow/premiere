"""Pure sequence-layout math.

These helpers never talk to Premiere or the proxy. They take a
``getSequenceLayout`` payload (or flattened clips) and report gaps,
lane roles, and A/V junctions. Kept import-safe so unit tests can
exercise the verification contract without starting the MCP server.
"""

from .constants import TICKS_PER_SECOND


def frame_ticks(layout: dict):
    """Ticks per video frame from a layout, or None if unavailable."""
    tpf = layout.get("ticksPerFrame")
    if tpf:
        try:
            return int(tpf)
        except (TypeError, ValueError):
            pass
    fr = layout.get("frameRateValue")
    if fr:
        try:
            fr = float(fr)
            if fr > 0:
                # NTSC rates are k*1000/1001 (29.97, 23.976, 59.94...). Snap to the
                # exact rational so ticks-per-frame doesn't drift over a long
                # sequence. (Fallback only — ticksPerFrame above is exact when
                # present.) Integer rates like 24/25/30 fail the proximity test
                # and use the plain division.
                k = round(fr * 1001 / 1000)
                if k > 0 and abs(fr - k * 1000.0 / 1001.0) < 0.01:
                    return int(round(TICKS_PER_SECOND * 1001 / (k * 1000)))
                return int(round(TICKS_PER_SECOND / fr))
        except (TypeError, ValueError):
            pass
    return None


def clips_from_layout(layout: dict):
    """Flatten a layout into (video_clips, audio_clips).

    Each clip: {kind: "v"|"a", trackIndex, start, end} in integer ticks. The
    media kind matters because a video track and an audio track both report
    index 0 — without the kind tag they would collide in a single bucket and a
    video clip could hide an audio gap (or fabricate one). See detect_gaps.
    """

    def collect(tracks, kind):
        out = []
        for track in tracks or []:
            t_index = track.get("index", 0)
            for clip in track.get("tracks", []):
                try:
                    start = int(clip["startTimeTicks"])
                    end = int(clip["endTimeTicks"])
                except (KeyError, TypeError, ValueError):
                    continue
                out.append({"kind": kind, "trackIndex": t_index, "start": start, "end": end})
        return out

    video = collect(layout.get("videoTracks"), "v")
    audio = collect(layout.get("audioTracks"), "a")
    return video, audio


def _gap_record(kind, t_index, start, end, frame_ticks_value, leading=False):
    gap = end - start
    return {
        "kind": kind,
        "trackIndex": t_index,
        "leading": leading,
        "startTicks": start,
        "endTicks": end,
        "gapTicks": gap,
        "gapSeconds": round(gap / TICKS_PER_SECOND, 4),
        "gapFrames": round(gap / frame_ticks_value, 2) if frame_ticks_value else None,
    }


def detect_gaps(clips: list, frame_ticks_value):
    """Detect gaps on each (kind, trackIndex) lane — including a leading gap.

    A "back to back" track has its first clip at tick 0 and every later clip
    starting exactly where the previous one ends. We report:
      - a LEADING gap when the first clip does not start at tick 0, and
      - an inter-clip gap whenever clip[i+1].start > clip[i].end.
    Video and audio are kept on separate lanes (keyed by media kind AND track
    index) so a clip on one never masks or fabricates a gap on the other.

    Gaps smaller than half a frame (or ~1ms when the frame rate is unknown) are
    ignored as sub-frame rounding noise.
    """
    tol = (frame_ticks_value // 2) if frame_ticks_value else int(TICKS_PER_SECOND * 0.001)
    by_lane = {}
    for c in clips:
        by_lane.setdefault((c.get("kind", "?"), c["trackIndex"]), []).append(c)

    gaps = []
    for (kind, t_index), lane in by_lane.items():
        lane.sort(key=lambda c: c["start"])
        if lane and lane[0]["start"] > tol:
            gaps.append(
                _gap_record(kind, t_index, 0, lane[0]["start"], frame_ticks_value, leading=True)
            )
        for i in range(len(lane) - 1):
            gap = lane[i + 1]["start"] - lane[i]["end"]
            if gap > tol:
                gaps.append(
                    _gap_record(
                        kind, t_index, lane[i]["end"], lane[i + 1]["start"], frame_ticks_value
                    )
                )
    return gaps


def lane_roles(clips: list, duration_ticks: int, frame_ticks_value) -> dict:
    """Classify each (kind, trackIndex) lane as "program" or "overlay".

    A finished sequence has PROGRAM lanes — the base video/audio bed the edit
    runs on, which must be back to back — and OVERLAY lanes carrying b-roll,
    titles, transition stingers or SFX, which are sparse BY DESIGN. Treating
    every lane as if it must be packed reports a stinger lane's 20 dead spots as
    20 "gaps" and calls a perfectly clean timeline broken.

    A lane is program when ANY of:
      - it starts at tick 0 (the bed always does), or
      - its summed content covers at least half the sequence, or
      - it is a single contiguous block of 2+ clips that starts late.

    The second clause is the original safety net: a program bed BROKEN by a bad
    cut (leading gap, so it no longer starts at 0) still covers most of the
    sequence. The third clause covers the remaining case — a failed Extract that
    left a leading hole AND less than half the duration — without promoting a
    single late stinger (one isolated clip) to program.
    """
    tol = (frame_ticks_value // 2) if frame_ticks_value else int(TICKS_PER_SECOND * 0.001)
    by_lane = {}
    for c in clips:
        by_lane.setdefault((c.get("kind", "?"), c["trackIndex"]), []).append(c)

    roles = {}
    for key, lane in by_lane.items():
        lane.sort(key=lambda c: c["start"])
        starts_at_zero = min(c["start"] for c in lane) <= tol
        content = sum((c["end"] - c["start"]) for c in lane)
        dense = bool(duration_ticks) and content * 2 >= duration_ticks
        contiguous = all(
            lane[i + 1]["start"] - lane[i]["end"] <= tol for i in range(len(lane) - 1)
        )
        late_bed = (not starts_at_zero) and contiguous and len(lane) >= 2
        roles[key] = "program" if (starts_at_zero or dense or late_bed) else "overlay"
    return roles


def tag_gap_lanes(gaps: list, roles: dict) -> list:
    """Stamp each gap with the role of the lane it sits on."""
    for g in gaps or []:
        g["lane"] = roles.get((g.get("kind", "?"), g.get("trackIndex")), "program")
    return gaps


def program_clips(clips: list, roles: dict) -> list:
    return [c for c in clips if roles.get((c.get("kind", "?"), c["trackIndex"])) == "program"]


def gaps_by_lane(gaps: list) -> dict:
    """Count gaps per (kind, trackIndex) lane.

    Comparing per-lane counts (not one global total) is what lets us catch a NEW
    gap that is masked by a pre-existing gap closing elsewhere: the global count
    can stay flat (one closes, one opens) while a lane that had zero gaps now has
    one — the untargeted-track failure. Counts are used instead of absolute
    positions because an Extract shifts every later clip left, so a surviving
    gap's start tick changes; its lane and existence do not.
    """
    out = {}
    for g in gaps or []:
        key = (g.get("kind", "?"), g.get("trackIndex"))
        out[key] = out.get(key, 0) + 1
    return out


def av_misalignments(video: list, audio: list, frame_ticks_value):
    """Cut junctions where video and audio do NOT line up to the frame.

    After a clean Extract, every internal cut produces a clip boundary at the
    SAME timecode on the video and the audio lane. If a cut shifted one but not
    the other, their junctions diverge — that is the "audio drifted a frame off
    the video" failure. We collect each lane's junctions (clip starts past the
    head) and report any junction on one side with no partner on the other within
    HALF a frame. The match tolerance is sub-frame on purpose: a frame-snapped
    Extract lands V and A on the EXACT same tick, so a full one-frame offset is a
    real desync and must be flagged — matching within a whole frame would hide
    exactly the 1-frame drift the user reports. Empty list == frame-accurate
    sync. Returns [] when either side has no clips (sync is undefined for a
    single-media sequence).
    """
    if not video or not audio:
        return []
    ft = frame_ticks_value or int(TICKS_PER_SECOND / 24)
    thr = max(ft // 2, 1)
    match_tol = thr
    v_junctions = sorted({c["start"] for c in video if c["start"] > thr})
    a_junctions = sorted({c["start"] for c in audio if c["start"] > thr})

    def unmatched(points, others, side):
        out = []
        for t in points:
            nearest = min((abs(t - o) for o in others), default=None)
            if nearest is None or nearest > match_tol:
                out.append(
                    {
                        "side": side,
                        "tick": t,
                        "seconds": round(t / TICKS_PER_SECOND, 4),
                        "frame": round(t / ft, 2),
                        "offsetFrames": round(nearest / ft, 2) if nearest is not None else None,
                    }
                )
        return out

    return unmatched(v_junctions, a_junctions, "video") + unmatched(
        a_junctions, v_junctions, "audio"
    )


def _lane_content(clips: list) -> dict:
    """Summed content ticks per (kind, trackIndex), keyed as 'v0' / 'a1'."""
    lanes = {}
    for c in clips:
        key = f"{c['kind']}{c['trackIndex']}"
        lanes[key] = lanes.get(key, 0) + (c["end"] - c["start"])
    return lanes


def summarize_layout(layout: dict) -> dict:
    """Reduce a raw layout to the numbers we verify against."""
    ticks = frame_ticks(layout)
    video, audio = clips_from_layout(layout)

    video_end = max((c["end"] for c in video), default=0)
    audio_end = max((c["end"] for c in audio), default=0)
    duration_ticks = max(video_end, audio_end)

    # Content = summed clip durations per media kind. Removal is measured against
    # this (not the global end) so an untouched longer track — a music bed or a
    # full-length title — cannot mask how much was actually cut. Kind sums stay
    # for Close Gap's "did content change?" check; per-lane content is what
    # _verify_cut uses so two targeted mic tracks cannot double-count.
    video_content = sum((c["end"] - c["start"]) for c in video)
    audio_content = sum((c["end"] - c["start"]) for c in audio)
    lane_content = _lane_content(video + audio)

    roles = lane_roles(video + audio, duration_ticks, ticks)
    gaps = tag_gap_lanes(detect_gaps(video + audio, ticks), roles)
    program_gaps = [g for g in gaps if g["lane"] == "program"]

    return {
        "videoClipCount": len(video),
        "audioClipCount": len(audio),
        "durationTicks": duration_ticks,
        "durationSeconds": round(duration_ticks / TICKS_PER_SECOND, 4),
        "videoEndTicks": video_end,
        "audioEndTicks": audio_end,
        "videoContentTicks": video_content,
        "audioContentTicks": audio_content,
        "laneContent": lane_content,
        "gaps": gaps,
        "gapCount": len(program_gaps),
        "allLaneGapCount": len(gaps),
        "overlayGapCount": len(gaps) - len(program_gaps),
        "laneRoles": {f"{kind}{idx}": role for (kind, idx), role in sorted(roles.items())},
        "frameTicks": ticks,
        "frameRateError": layout.get("frameRateError"),
    }

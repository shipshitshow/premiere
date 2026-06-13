# MIT License
#
# Copyright (c) 2025 Mike Chambers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from mcp.server.fastmcp import FastMCP
from ..shared import init, sendCommand, createCommand, socket_client
import sys
import os
import subprocess
import time
import math

# Premiere uses 254016000000 ticks per second internally.
TICKS_PER_SECOND = 254016000000

# Name of the Premiere Pro application as macOS sees it (used by AppleScript).
# Override with PREMIERE_APP_NAME when targeting a different version, e.g.
# "Adobe Premiere Pro 2025". This avoids a yearly hard-coded breakage.
PREMIERE_APP_NAME = os.environ.get("PREMIERE_APP_NAME", "Adobe Premiere Pro 2026")


def send_keystroke_to_premiere(key: str, modifiers: list = None, retries: int = 2):
    """Send a keystroke to Premiere Pro using AppleScript.

    Includes retry logic for -1712 timeout errors.
    """
    if modifiers is None:
        modifiers = []

    # Build modifier string for AppleScript
    if modifiers:
        modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    else:
        modifier_str = ""

    script = f'''
    tell application "{PREMIERE_APP_NAME}" to activate
    delay 0.1
    tell application "System Events"
        keystroke "{key}"{modifier_str}
    end tell
    '''

    last_error = None
    for attempt in range(retries + 1):
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True

        last_error = result.stderr
        # Retry on -1712 timeout errors
        if "-1712" in result.stderr and attempt < retries:
            time.sleep(0.3 * (attempt + 1))
            continue
        break

    raise Exception(f"AppleScript error: {last_error}")


def send_key_code_to_premiere(key_code: int, modifiers: list = None, retries: int = 2):
    """Send a key code to Premiere Pro using AppleScript (for special keys).

    Includes retry logic for -1712 timeout errors.
    """
    if modifiers is None:
        modifiers = []

    if modifiers:
        modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    else:
        modifier_str = ""

    script = f'''
    tell application "{PREMIERE_APP_NAME}" to activate
    delay 0.1
    tell application "System Events"
        key code {key_code}{modifier_str}
    end tell
    '''

    last_error = None
    for attempt in range(retries + 1):
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True

        last_error = result.stderr
        if "-1712" in result.stderr and attempt < retries:
            time.sleep(0.3 * (attempt + 1))
            continue
        break

    raise Exception(f"AppleScript error: {last_error}")


def _ensure_premiere_focused():
    """Activate Premiere Pro once before a batch operation."""
    script = f'tell application "{PREMIERE_APP_NAME}" to activate'
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10
    )
    time.sleep(0.15)


def _send_keystroke_fast(key: str, modifiers: list = None):
    """Send keystroke WITHOUT activate or delay — use after _ensure_premiere_focused()."""
    if modifiers is None:
        modifiers = []

    if modifiers:
        modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    else:
        modifier_str = ""

    script = f'''tell application "System Events"
    keystroke "{key}"{modifier_str}
end tell'''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        raise Exception(f"AppleScript error: {result.stderr}")
    return True


def _send_key_code_fast(key_code: int, modifiers: list = None):
    """Send key code WITHOUT activate or delay — use after _ensure_premiere_focused()."""
    if modifiers is None:
        modifiers = []

    if modifiers:
        modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    else:
        modifier_str = ""

    script = f'''tell application "System Events"
    key code {key_code}{modifier_str}
end tell'''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        raise Exception(f"AppleScript error: {result.stderr}")
    return True


# =============================================================================
# SEQUENCE LAYOUT / CUT VERIFICATION
# These read the ACTUAL clip layout back from Premiere so we never trust a
# tool's success flag alone (see CLAUDE.md and the premiere-mcp-ops skill).
# =============================================================================

def _fetch_layout(sequence_id: str) -> dict:
    """Fetch the focused clip layout for one sequence.

    Returns the plugin payload: {id, name, frameRateValue, ticksPerFrame,
    videoTracks, audioTracks}. Raises (via sendCommand) if the plugin reports
    failure.
    """
    response = sendCommand(createCommand("getSequenceLayout", {"sequenceId": sequence_id}))
    if isinstance(response, dict):
        return response.get("response", {}) or {}
    return {}


def _active_sequence_id() -> str:
    """Return the id of the sequence Premiere currently has active, or "".

    The Extract keystroke goes to whatever Timeline panel is FOCUSED — which is
    the ACTIVE sequence, not necessarily the sequence_id we pass to a UXP query.
    Before cutting we use this to assert they are the same, so we never razor the
    wrong timeline. Best-effort: returns "" if the info cannot be read.
    """
    try:
        response = sendCommand(createCommand("getProjectInfo", {}))
        payload = response.get("response", {}) if isinstance(response, dict) else {}
        return str(payload.get("activeSequenceId") or "")
    except Exception:
        return ""


def _frame_ticks(layout: dict):
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


def _snap_to_frame(ticks: int, frame_ticks: int, mode: str = "round") -> int:
    """Snap a tick value to a whole-frame boundary."""
    if not frame_ticks or frame_ticks <= 0:
        return int(ticks)
    q = ticks / frame_ticks
    if mode == "floor":
        frames = math.floor(q)
    elif mode == "ceil":
        frames = math.ceil(q)
    else:
        frames = round(q)
    return int(frames * frame_ticks)


def _clips_from_layout(layout: dict):
    """Flatten a layout into (video_clips, audio_clips).

    Each clip: {kind: "v"|"a", trackIndex, start, end} in integer ticks. The
    media kind matters because a video track and an audio track both report
    index 0 — without the kind tag they would collide in a single bucket and a
    video clip could hide an audio gap (or fabricate one). See _detect_gaps.
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


def _gap_record(kind, t_index, start, end, frame_ticks, leading=False):
    gap = end - start
    return {
        "kind": kind,
        "trackIndex": t_index,
        "leading": leading,
        "startTicks": start,
        "endTicks": end,
        "gapTicks": gap,
        "gapSeconds": round(gap / TICKS_PER_SECOND, 4),
        "gapFrames": round(gap / frame_ticks, 2) if frame_ticks else None,
    }


def _detect_gaps(clips: list, frame_ticks):
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
    tol = (frame_ticks // 2) if frame_ticks else int(TICKS_PER_SECOND * 0.001)
    by_lane = {}
    for c in clips:
        by_lane.setdefault((c.get("kind", "?"), c["trackIndex"]), []).append(c)

    gaps = []
    for (kind, t_index), lane in by_lane.items():
        lane.sort(key=lambda c: c["start"])
        if lane and lane[0]["start"] > tol:
            gaps.append(_gap_record(kind, t_index, 0, lane[0]["start"], frame_ticks, leading=True))
        for i in range(len(lane) - 1):
            gap = lane[i + 1]["start"] - lane[i]["end"]
            if gap > tol:
                gaps.append(_gap_record(kind, t_index, lane[i]["end"], lane[i + 1]["start"], frame_ticks))
    return gaps


def _gaps_by_lane(gaps: list) -> dict:
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


def _av_misalignments(video: list, audio: list, frame_ticks):
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

    Note: junctions are pooled across ALL video tracks vs ALL audio tracks. This
    is exact right after a transcript cut (only the linked base layer exists). If
    you call it later, after b-roll or music is layered on higher tracks, a clip
    boundary on V2/A2 that legitimately does not line up with the base layer can
    show as a misalignment — so trust it most immediately after the cut.
    """
    if not video or not audio:
        return []
    ft = frame_ticks or int(TICKS_PER_SECOND / 24)
    thr = max(ft // 2, 1)
    # Match tolerance: half a frame. Allows pure integer-rounding noise on a
    # snapped boundary but treats a one-frame (or larger) offset as a misalignment.
    match_tol = thr
    v_junctions = sorted({c["start"] for c in video if c["start"] > thr})
    a_junctions = sorted({c["start"] for c in audio if c["start"] > thr})

    def unmatched(points, others, side):
        out = []
        for t in points:
            nearest = min((abs(t - o) for o in others), default=None)
            if nearest is None or nearest > match_tol:
                out.append({
                    "side": side,
                    "tick": t,
                    "seconds": round(t / TICKS_PER_SECOND, 4),
                    "frame": round(t / ft, 2),
                    "offsetFrames": round(nearest / ft, 2) if nearest is not None else None,
                })
        return out

    return unmatched(v_junctions, a_junctions, "video") + unmatched(a_junctions, v_junctions, "audio")


def _summarize_layout(layout: dict) -> dict:
    """Reduce a raw layout to the numbers we verify against."""
    frame_ticks = _frame_ticks(layout)
    video, audio = _clips_from_layout(layout)

    video_end = max((c["end"] for c in video), default=0)
    audio_end = max((c["end"] for c in audio), default=0)
    duration_ticks = max(video_end, audio_end)

    # Content = summed clip durations per media kind. Removal is measured against
    # this (not the global end) so an untouched longer track — a music bed or a
    # full-length title — cannot mask how much was actually cut.
    video_content = sum((c["end"] - c["start"]) for c in video)
    audio_content = sum((c["end"] - c["start"]) for c in audio)

    gaps = _detect_gaps(video + audio, frame_ticks)

    return {
        "videoClipCount": len(video),
        "audioClipCount": len(audio),
        "durationTicks": duration_ticks,
        "durationSeconds": round(duration_ticks / TICKS_PER_SECOND, 4),
        "videoEndTicks": video_end,
        "audioEndTicks": audio_end,
        "videoContentTicks": video_content,
        "audioContentTicks": audio_content,
        "gaps": gaps,
        "gapCount": len(gaps),
        "frameTicks": frame_ticks,
    }


def _verify_cut(sequence_id: str, before: dict, expected_removed_ticks: int, frame_ticks, cut_count=1):
    """Compare the post-cut layout to the pre-cut baseline.

    Returns {verified, packed, avSynced, ...}. ``verified`` is True only when the
    right amount of content was removed, the cut introduced no new gaps, and
    video/audio still cut at the same timecodes (frame-accurate sync). It is None
    when no usable baseline was captured (cannot confirm a delta), and False when
    any of those checks fail.

    The two halves the user cares about are surfaced explicitly:
      - ``packed``   — True when the whole sequence is back to back, zero gaps.
      - ``avSynced`` — True when every cut lands on the same frame for V and A.
    """
    try:
        after_layout = _fetch_layout(sequence_id)
        after = _summarize_layout(after_layout)
        a_video, a_audio = _clips_from_layout(after_layout)
    except Exception as e:
        return {"verified": None, "error": f"Could not read layout after cut: {e}"}

    if not before or before.get("error") or before.get("durationTicks") is None:
        return {
            "verified": None,
            "reason": "No usable pre-cut baseline; cannot confirm the change.",
            "packed": after["gapCount"] == 0,
            "after": {k: after.get(k) for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")},
        }

    ft = frame_ticks or after.get("frameTicks") or int(TICKS_PER_SECOND / 24)

    # Removal measured on CONTENT per kind, so a longer untouched track can't
    # mask the cut. Take the larger of the two — a symmetric Extract moves both.
    v_removed = before.get("videoContentTicks", 0) - after.get("videoContentTicks", 0)
    a_removed = before.get("audioContentTicks", 0) - after.get("audioContentTicks", 0)
    actual_removed = max(v_removed, a_removed)

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

    # Gaps: a clean Extract closes the gap it makes, so it can only reduce gaps on
    # the targeted lanes, never add one. Compare gap counts PER LANE, not as one
    # global total: a global count can stay flat when a pre-existing gap closes
    # while a new one opens on an untargeted lane. Any lane whose gap count went
    # UP is a newly introduced gap (the timeline is no longer back to back there).
    packed = after["gapCount"] == 0
    before_lanes = _gaps_by_lane(before.get("gaps", []))
    after_lanes = _gaps_by_lane(after["gaps"])
    new_gap_lanes = [lane for lane, n in after_lanes.items() if n > before_lanes.get(lane, 0)]
    new_gap_count = sum(n - before_lanes.get(lane, 0) for lane, n in after_lanes.items()
                        if n > before_lanes.get(lane, 0))
    no_new_gaps = not new_gap_lanes

    # A/V sync: video and audio must cut at the same frame. End-skew is a weaker
    # secondary signal kept for the case where one media kind is absent.
    av_applicable = bool(a_video) and bool(a_audio)
    misalignments = _av_misalignments(a_video, a_audio, ft) if av_applicable else []
    if before.get("videoClipCount") and before.get("audioClipCount") and a_video and a_audio:
        end_skew = abs((before["videoEndTicks"] - after["videoEndTicks"]) -
                       (before["audioEndTicks"] - after["audioEndTicks"]))
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
            f"{after['gapCount']} pre-existing gap(s) remain elsewhere on the timeline "
            "(not introduced by this cut). The sequence is not fully back to back."
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
        "before": {k: before.get(k) for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")},
        "after": {k: after.get(k) for k in ("videoClipCount", "audioClipCount", "durationSeconds", "gapCount")},
        "warnings": warnings,
    }


#logger.log(f"Python path: {sys.executable}")
#logger.log(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
#logger.log(f"Current working directory: {os.getcwd()}")
#logger.log(f"Sys.path: {sys.path}")


mcp_name = "Adobe Premiere MCP Server"
mcp = FastMCP(mcp_name, log_level="ERROR")
print(f"{mcp_name} running on stdio", file=sys.stderr)

APPLICATION = "premiere"
PROXY_URL = os.environ.get('PROXY_URL', 'http://localhost:3001')
PROXY_TIMEOUT = int(os.environ.get('PROXY_TIMEOUT', '120'))

socket_client.configure(
    app=APPLICATION,
    url=PROXY_URL,
    timeout=PROXY_TIMEOUT
)

init(APPLICATION, socket_client)

# Register additional Premiere-only UXP tools.
try:
    from .tools import register_tools
    register_tools(mcp)
    print("Registered extended Premiere tools", file=sys.stderr)
except ImportError as e:
    print(f"Note: extended Premiere tools not available: {e}", file=sys.stderr)

@mcp.tool()
def get_project_info():
    """
    Returns basic info on the currently active project in Premiere Pro.

    Returns lightweight info: whether a project is open, sequence count,
    and active sequence name/id. Use get_full_project_data for detailed
    sequence and clip information.
    """

    command = createCommand("getProjectInfo", {
    })

    return sendCommand(command)


@mcp.tool()
def get_full_project_data():
    """
    Returns full detailed data about all sequences and project items.

    WARNING: This can return a LARGE response for big projects.
    Use sparingly. For basic info, use get_project_info instead.

    Returns:
        - sequences: All sequences with their tracks and clips
        - projectItems: All items in the project bin
    """

    command = createCommand("getFullProjectData", {
    })

    return sendCommand(command)

@mcp.tool()
def save_project():
    """
    Saves the active project in Premiere Pro.
    """

    command = createCommand("saveProject", {
    })

    return sendCommand(command)

@mcp.tool()
def save_project_as(file_path: str):
    """Saves the current Premiere project to the specified location.
    
    Args:
        file_path (str): The absolute path (including filename) where the file will be saved.
            Example: "/Users/username/Documents/project.prproj"

    """
    
    command = createCommand("saveProjectAs", {
        "filePath":file_path
    })

    return sendCommand(command)

@mcp.tool()
def open_project(file_path: str):
    """Opens the Premiere project at the specified path.
    
    Args:
        file_path (str): The absolute path (including filename) of the Premiere Pro project to open.
            Example: "/Users/username/Documents/project.prproj"

    """
    
    command = createCommand("openProject", {
        "filePath":file_path
    })

    return sendCommand(command)


@mcp.tool()
def create_project(directory_path: str, project_name: str):
    """
    Create a new Premiere project.

    Creates a new Adobe Premiere project file, saves it to the specified location and then opens it in Premiere.

    The function initializes an empty project with default settings.

    Args:
        directory_path (str): The full path to the directory where the project file will be saved. This directory must exist before calling the function.
        project_name (str): The name to be given to the project file. The '.prproj' extension will be added.
    """

    command = createCommand("createProject", {
        "path":directory_path,
        "name":project_name
    })

    return sendCommand(command)



@mcp.tool()
def set_audio_track_mute(sequence_id:str, audio_track_index: int, mute: bool):
    """
    Sets the mute property on the specified audio track. If mute is true, all clips on the track will be muted and not played.

    Args:
        sequence_id (str) : The id of the sequence on which to set the audio track mute.
        audio_track_index (int): The index of the audio track to mute or unmute. Indices start at 0 for the first audio track.
        mute (bool): Whether the track should be muted.
            - True: Mutes the track (audio will not be played)
            - False: Unmutes the track (audio will be played normally)

    """

    command = createCommand("setAudioTrackMute", {
        "sequenceId": sequence_id,
        "audioTrackIndex":audio_track_index,
        "mute":mute
    })

    return sendCommand(command)


@mcp.tool()
def set_active_sequence(sequence_id: str):
    """
    Sets the sequence with the specified id as the active sequence within Premiere Pro (currently selected and visible in timeline)
    
    Args:
        sequence_id (str): ID for the sequence to be set as active
    """

    command = createCommand("setActiveSequence", {
        "sequenceId":sequence_id
    })

    return sendCommand(command)


@mcp.tool()
def create_sequence_from_media(item_names: list[str], sequence_name: str = "default"):
    """
    Creates a new sequence from the specified project items, placing clips on the timeline in the order they are provided.
    
    If there is not an active sequence the newly created sequence will be set as the active sequence when created.
    
    Args:
        item_names (list[str]): A list of project item names to include in the sequence in the desired order.
        sequence_name (str, optional): The name to give the new sequence. Defaults to "default".
    """


    command = createCommand("createSequenceFromMedia", {
        "itemNames":item_names,
        "sequenceName":sequence_name
    })

    return sendCommand(command)

@mcp.tool()
def add_media_to_sequence(sequence_id:str, item_name: str, video_track_index: int, audio_track_index: int, insertion_time_ticks: int = 0, overwrite: bool = True):
    """
    Adds a specified media item to the active sequence's timeline.

    Args:
        sequence_id (str) : The id for the sequence to add the media to
        item_name (str): The name or identifier of the media item to add.
        video_track_index (int, optional): The index of the video track where the item should be inserted. Defaults to 0.0.
        audio_track_index (int, optional): The index of the audio track where the item should be inserted. Defaults to 0.0.
        insertion_time_ticks (int, optional): The position on the timeline in ticks, with 0 being the beginning. The API will return positions of existing clips in ticks
        overwrite (bool, optional): Whether to overwrite existing content at the insertion point. Defaults to True. If False, any existing clips that overlap will be split and item inserted.
    """


    command = createCommand("addMediaToSequence", {
        "sequenceId": sequence_id,
        "itemName":item_name,
        "videoTrackIndex":video_track_index,
        "audioTrackIndex":audio_track_index,
        "insertionTimeTicks":insertion_time_ticks,
        "overwrite":overwrite
    })

    return sendCommand(command)


@mcp.tool()
def set_audio_clip_disabled(sequence_id:str, audio_track_index: int, track_item_index: int, disabled: bool):
    """
    Enables or disables a audio clip in the timeline.
    
    Args:
        sequence_id (str) : The id for the sequence to set the audio clip disabled property.
        audio_track_index (int): The index of the audio track containing the target clip.
        track_item_index (int): The index of the clip within the track to enable/disable.
        disabled (bool): Whether to disable the clip.
            - True: Disables the clip (clip will not be visible during playback or export)
            - False: Enables the clip (normal visibility)
    """

    command = createCommand("setAudioClipDisabled", {
        "sequenceId": sequence_id,
        "audioTrackIndex":audio_track_index,
        "trackItemIndex":track_item_index,
        "disabled":disabled
    })

    return sendCommand(command)

@mcp.tool()
def set_video_clip_disabled(sequence_id:str, video_track_index: int, track_item_index: int, disabled: bool):
    """
    Enables or disables a video clip in the timeline.
    
    Args:
        sequence_id (str) : The id for the sequence to set the video clip disabled property.
        video_track_index (int): The index of the video track containing the target clip.
        track_item_index (int): The index of the clip within the track to enable/disable.
        disabled (bool): Whether to disable the clip.
            - True: Disables the clip (clip will not be visible during playback or export)
            - False: Enables the clip (normal visibility)
    """

    command = createCommand("setVideoClipDisabled", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "disabled":disabled
    })

    return sendCommand(command)


@mcp.tool()
def add_black_and_white_effect(sequence_id:str, video_track_index: int, track_item_index: int):
    """
    Adds a black and white effect to a clip at the specified track and position.
    
    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Black & White",
        "properties":[
        ]
    })

    return sendCommand(command)

@mcp.tool()
def export_frame(sequence_id:str, file_path: str, seconds: int):
    """Captures a specific frame from the sequence at the given timestamp
    and exports it as a PNG image file to the specified path.
    
    Args:
        sequence_id (str) : The id for the sequence to export the frame from
        file_path (str): The destination path where the exported PNG image will be saved.
            Must include the full directory path and filename with .png extension.
        seconds (int): The timestamp in seconds from the beginning of the sequence
            where the frame should be captured. The frame closest to this time position
            will be extracted.
    """
    if not file_path.lower().endswith(".png"):
        file_path += ".png"
    
    command = createCommand("exportFrame", {
        "sequenceId": sequence_id,
        "filePath": file_path,
        "seconds":seconds
        }
    )

    return sendCommand(command)


@mcp.tool()
def add_gaussian_blur_effect(sequence_id: str, video_track_index: int, track_item_index: int, blurriness: float, blur_dimensions: str = "HORIZONTAL_VERTICAL"):
    """
    Adds a gaussian blur effect to a clip at the specified track and position.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        blurriness (float): The intensity of the blur effect. Higher values create stronger blur.
            Recommended range is between 0.0 and 100.0 (Max 3000).
            
        blur_dimensions (str, optional): The direction of the blur effect. Defaults to "HORIZONTAL_VERTICAL".
            Valid options are:
            - "HORIZONTAL_VERTICAL": Blur in all directions
            - "HORIZONTAL": Blur only horizontally
            - "VERTICAL": Blur only vertically
    """
    dimensions = {"HORIZONTAL_VERTICAL": 0, "HORIZONTAL": 1, "VERTICAL": 2}
    
    # Validate blur_dimensions parameter
    if blur_dimensions not in dimensions:
        raise ValueError(f"Invalid blur_dimensions. ")

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "effectName": "AE.ADBE Gaussian Blur 2",
        "properties": [
            {"name": "Blur Dimensions", "value": dimensions[blur_dimensions]},
            {"name": "Blurriness", "value": blurriness}
        ]
    })

    return sendCommand(command)

def rgb_to_premiere_color3(rgb_color, alpha=1.0):
    """Converts RGB (0–255) dict to Premiere Pro color format [r, g, b, a] with floats (0.0–1.0)."""
    return [
        rgb_color["red"] / 255.0,
        rgb_color["green"] / 255.0,
        rgb_color["blue"] / 255.0,
        alpha
    ]

def rgb_to_premiere_color(rgb_color, alpha=255):
    """
    Converts an RGB(A) dict (0–255) to a 64-bit Premiere Pro color parameter (as int).
    Matches Adobe's internal ARGB 16-bit fixed-point format.
    """
    def to16bit(value):
        return int(round(value * 256))

    r16 = to16bit(rgb_color["red"] / 255.0)
    g16 = to16bit(rgb_color["green"] / 255.0)
    b16 = to16bit(rgb_color["blue"] / 255.0)
    a16 = to16bit(alpha / 255.0)

    high = (a16 << 16) | r16       # top 32 bits: A | R
    low = (g16 << 16) | b16        # bottom 32 bits: G | B

    packed_color = (high << 32) | low
    return packed_color




@mcp.tool()
def add_tint_effect(sequence_id: str, video_track_index: int, track_item_index: int, black_map:dict = {"red":0, "green":0, "blue":0}, white_map:dict = {"red":255, "green":255, "blue":255}, amount:int = 100):
    """
    Adds the tint effect to a clip at the specified track and position.
    
    This function applies a tint effect that maps the dark and light areas of the clip to specified colors.
    
    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        black_map (dict): The RGB color values to map black/dark areas to, with keys "red", "green", and "blue".
            Default is {"red":0, "green":0, "blue":0} (pure black).
            
        white_map (dict): The RGB color values to map white/light areas to, with keys "red", "green", and "blue".
            Default is {"red":255, "green":255, "blue":255} (pure white).
            
        amount (int): The intensity of the tint effect as a percentage, ranging from 0 to 100.
            Default is 100 (full tint effect).
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Tint",
        "properties":[
            #{"name":"Map White To", "value":rgb_to_premiere_color(white_map)},
            #{"name":"Map Black To", "value":rgb_to_premiere_color(black_map)}
            {"name":"Map Black To", "value":rgb_to_premiere_color(black_map)}
            #{"name":"Amount to Tint", "value":amount / 100}
        ]
    })

    return sendCommand(command)



@mcp.tool()
def add_motion_blur_effect(sequence_id: str, video_track_index: int, track_item_index: int, direction: int, length: int):
    """
    Adds the directional blur effect to a clip at the specified track and position.
    
    This function applies a motion blur effect that simulates movement in a specific direction.
    
    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.
            
        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.
            
        direction (int): The angle of the directional blur in degrees, ranging from 0 to 360.
            - 0/360: Vertical blur upward
            - 90: Horizontal blur to the right 
            - 180: Vertical blur downward
            - 270: Horizontal blur to the left
            
        length (int): The intensity or distance of the blur effect, ranging from 0 to 1000.
    """

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Motion Blur",
        "properties":[
            {"name":"Direction", "value":direction},
            {"name":"Blur Length", "value":length}
        ]
    })

    return sendCommand(command)

@mcp.tool()
def append_video_transition(sequence_id: str, video_track_index: int, track_item_index: int, transition_name: str, duration: int = 1.0, clip_alignment: float = 0.5):
    """
    Creates a transition between the specified clip and the adjacent clip on the timeline.
    
    In general, you should keep transitions short (no more than 2 seconds is a good rule).

    Args:
        sequence_id (str) : The id for the sequence to add the transition to
        video_track_index (int): The index of the video track containing the target clips.
        track_item_index (int): The index of the clip within the track to apply the transition to.
        transition_name (str): The name of the transition to apply. Must be a valid transition name (see below).
        duration (int): The duration of the transition in seconds.
        clip_alignment (float): Controls how the transition is distributed between the two clips.
                                Range: 0.0 to 1.0, where:
                                - 0.0 places transition entirely on the right (later) clip
                                - 0.5 centers the transition equally between both clips (default)
                                - 1.0 places transition entirely on the left (earlier) clip
 
    Valid Transition Names:
        Basic Transitions (ADBE):
            - "ADBE Additive Dissolve"
            - "ADBE Cross Zoom"
            - "ADBE Cube Spin"
            - "ADBE Film Dissolve"
            - "ADBE Flip Over"
            - "ADBE Gradient Wipe"
            - "ADBE Iris Cross"
            - "ADBE Iris Diamond"
            - "ADBE Iris Round"
            - "ADBE Iris Square"
            - "ADBE Page Peel"
            - "ADBE Push"
            - "ADBE Slide"
            - "ADBE Wipe"
            
        After Effects Transitions (AE.ADBE):
            - "AE.ADBE Center Split"
            - "AE.ADBE Inset"
            - "AE.ADBE Cross Dissolve New"
            - "AE.ADBE Dip To White"
            - "AE.ADBE Split"
            - "AE.ADBE Whip"
            - "AE.ADBE Non-Additive Dissolve"
            - "AE.ADBE Dip To Black"
            - "AE.ADBE Barn Doors"
            - "AE.ADBE MorphCut"
    """

    command = createCommand("appendVideoTransition", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "transitionName":transition_name,
        "clipAlignment":clip_alignment,
        "duration":duration
    })

    return sendCommand(command)


@mcp.tool()
def set_video_clip_properties(sequence_id: str, video_track_index: int, track_item_index: int, opacity: int = 100, blend_mode: str = "NORMAL"):
    """
    Sets opacity and blend mode properties for a video clip in the timeline.

    This function modifies the visual properties of a specific clip located on a specific video track
    in the active Premiere Pro sequence. The clip is identified by its track index and item index
    within that track.

    Args:
        sequence_id (str) : The id for the sequence to set the video clip properties
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track.
        track_item_index (int): The index of the clip within the track to modify.
            Clip indices start at 0 for the first clip on the track.
        opacity (int, optional): The opacity value to set for the clip, as a percentage.
            Valid values range from 0 (completely transparent) to 100 (completely opaque).
            Defaults to 100.
        blend_mode (str, optional): The blend mode to apply to the clip.
            Must be one of the valid blend modes supported by Premiere Pro.
            Defaults to "NORMAL".
    """

    command = createCommand("setVideoClipProperties", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "opacity":opacity,
        "blendMode":blend_mode
    })

    return sendCommand(command)

@mcp.tool()
def import_media(file_paths:list):
    """
    Imports a list of media files into the active Premiere project.

    Args:
        file_paths (list): A list of file paths (strings) to import into the project.
            Each path should be a complete, valid path to a media file supported by Premiere Pro.
    """

    command = createCommand("importMedia", {
        "filePaths":file_paths
    })

    return sendCommand(command)


@mcp.tool()
def split_video_clip(sequence_id: str, video_track_index: int, track_item_index: int, split_time_seconds: float):
    """
    UNSAFE for transcript cuts: splitting then deleting can desync linked
    video/audio or leave gaps. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Splits a video clip at the specified time, creating two separate clips.

    The original clip will end at the split point, and a new clip will be created
    starting from the split point with the remainder of the content.

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        video_track_index (int): The index of the video track containing the clip.
            Track indices start at 0.
        track_item_index (int): The index of the clip within the track.
            Clip indices start at 0.
        split_time_seconds (float): The time in seconds (from sequence start) where the split should occur.
            Must be within the clip's start and end time.
    """
    TICKS_PER_SECOND = 254016000000
    split_time_ticks = int(split_time_seconds * TICKS_PER_SECOND)

    command = createCommand("splitVideoClip", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "splitTimeTicks": split_time_ticks
    })

    return sendCommand(command)


@mcp.tool()
def split_audio_clip(sequence_id: str, audio_track_index: int, track_item_index: int, split_time_seconds: float):
    """
    UNSAFE for transcript cuts: splitting then deleting can desync linked
    video/audio or leave gaps. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Splits an audio clip at the specified time, creating two separate clips.

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        audio_track_index (int): The index of the audio track containing the clip.
            Track indices start at 0.
        track_item_index (int): The index of the clip within the track.
            Clip indices start at 0.
        split_time_seconds (float): The time in seconds (from sequence start) where the split should occur.
            Must be within the clip's start and end time.
    """
    TICKS_PER_SECOND = 254016000000
    split_time_ticks = int(split_time_seconds * TICKS_PER_SECOND)

    command = createCommand("splitAudioClip", {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "splitTimeTicks": split_time_ticks
    })

    return sendCommand(command)


@mcp.tool()
def split_clip_at_time(sequence_id: str, split_time_seconds: float,
                       video_track_index: int = None, video_clip_index: int = 0,
                       audio_track_index: int = None, audio_clip_index: int = 0):
    """
    Splits both video and audio clips at the specified time in a single operation.

    This is the preferred method for splitting clips as it:
    - Splits video and audio together (keeps them in sync)
    - Creates a single undo entry (one Cmd+Z undoes the whole operation)

    Args:
        sequence_id (str): The id of the sequence.
        split_time_seconds (float): The time in seconds where the split should occur.
        video_track_index (int, optional): Video track index. If None, video is not split.
        video_clip_index (int, optional): Index of video clip on the track. Defaults to 0.
        audio_track_index (int, optional): Audio track index. If None, audio is not split.
        audio_clip_index (int, optional): Index of audio clip on the track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000
    split_time_ticks = int(split_time_seconds * TICKS_PER_SECOND)

    command = createCommand("splitClipAtTime", {
        "sequenceId": sequence_id,
        "splitTimeTicks": split_time_ticks,
        "videoTrackIndex": video_track_index,
        "videoClipIndex": video_clip_index,
        "audioTrackIndex": audio_track_index,
        "audioClipIndex": audio_clip_index
    })

    return sendCommand(command)


@mcp.tool()
def batch_split_clips(sequence_id: str, split_times_seconds: list,
                      video_track_index: int = None, video_clip_index: int = 0,
                      audio_track_index: int = None, audio_clip_index: int = 0):
    """
    UNSAFE for transcript cuts: batch splitting then deleting can desync linked
    video/audio or leave gaps. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Performs multiple splits at once.

    Splits are performed from end to start to preserve clip indices.
    Each split creates a separate undo entry.

    Args:
        sequence_id (str): The id of the sequence.
        split_times_seconds (list): List of times in seconds where splits should occur.
            Example: [10.5, 25.3, 42.0, 55.8]
        video_track_index (int, optional): Video track index. If None, video is not split.
        video_clip_index (int, optional): Index of video clip. Defaults to 0.
        audio_track_index (int, optional): Audio track index. If None, audio is not split.
        audio_clip_index (int, optional): Index of audio clip. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000
    split_time_ticks_list = [int(t * TICKS_PER_SECOND) for t in split_times_seconds]

    command = createCommand("batchSplitClips", {
        "sequenceId": sequence_id,
        "splitTimeTicksList": split_time_ticks_list,
        "videoTrackIndex": video_track_index,
        "videoClipIndex": video_clip_index,
        "audioTrackIndex": audio_track_index,
        "audioClipIndex": audio_clip_index
    })

    return sendCommand(command)


@mcp.tool()
def trim_video_clip(sequence_id: str, video_track_index: int, track_item_index: int,
                    new_start_seconds: float = None, new_end_seconds: float = None,
                    new_in_point_seconds: float = None, new_out_point_seconds: float = None,
                    linked: bool = True, audio_track_index: int = 0):
    """
    UNSAFE for transcript cuts: manual trims can desync linked video/audio or
    leave gaps. Prefer remove_silence_segments. See the premiere-mcp-ops skill.

    Trims a video clip by adjusting its start/end times or in/out points.
    By default, also trims the linked audio counterpart.

    - Start/End times: Position on the timeline (sequence time)
    - In/Out points: Which part of the source media is used

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        video_track_index (int): The index of the video track containing the clip.
        track_item_index (int): The index of the clip within the track.
        new_start_seconds (float, optional): New start position on timeline in seconds.
        new_end_seconds (float, optional): New end position on timeline in seconds.
        new_in_point_seconds (float, optional): New in-point in source media in seconds.
        new_out_point_seconds (float, optional): New out-point in source media in seconds.
        linked (bool, optional): If True, also trim the linked audio counterpart. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    options = {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "linked": linked,
        "linkedTrackIndex": audio_track_index,
    }

    if new_start_seconds is not None:
        options["newStartTicks"] = int(new_start_seconds * TICKS_PER_SECOND)
    if new_end_seconds is not None:
        options["newEndTicks"] = int(new_end_seconds * TICKS_PER_SECOND)
    if new_in_point_seconds is not None:
        options["newInPointTicks"] = int(new_in_point_seconds * TICKS_PER_SECOND)
    if new_out_point_seconds is not None:
        options["newOutPointTicks"] = int(new_out_point_seconds * TICKS_PER_SECOND)

    command = createCommand("trimVideoClip", options)
    return sendCommand(command)


@mcp.tool()
def trim_audio_clip(sequence_id: str, audio_track_index: int, track_item_index: int,
                    new_start_seconds: float = None, new_end_seconds: float = None,
                    new_in_point_seconds: float = None, new_out_point_seconds: float = None,
                    linked: bool = True, linked_video_track_index: int = 0):
    """
    UNSAFE for transcript cuts: manual trims can desync linked video/audio or
    leave gaps. Prefer remove_silence_segments. See the premiere-mcp-ops skill.

    Trims an audio clip by adjusting its start/end times or in/out points.
    By default, also trims the linked video counterpart.

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        audio_track_index (int): The index of the audio track containing the clip.
        track_item_index (int): The index of the clip within the track.
        new_start_seconds (float, optional): New start position on timeline in seconds.
        new_end_seconds (float, optional): New end position on timeline in seconds.
        new_in_point_seconds (float, optional): New in-point in source media in seconds.
        new_out_point_seconds (float, optional): New out-point in source media in seconds.
        linked (bool, optional): If True, also trim the linked video counterpart. Defaults to True.
        linked_video_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    options = {
        "sequenceId": sequence_id,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "linked": linked,
        "linkedTrackIndex": linked_video_track_index,
    }

    if new_start_seconds is not None:
        options["newStartTicks"] = int(new_start_seconds * TICKS_PER_SECOND)
    if new_end_seconds is not None:
        options["newEndTicks"] = int(new_end_seconds * TICKS_PER_SECOND)
    if new_in_point_seconds is not None:
        options["newInPointTicks"] = int(new_in_point_seconds * TICKS_PER_SECOND)
    if new_out_point_seconds is not None:
        options["newOutPointTicks"] = int(new_out_point_seconds * TICKS_PER_SECOND)

    command = createCommand("trimAudioClip", options)
    return sendCommand(command)


@mcp.tool()
def remove_video_clip_range(sequence_id: str, video_track_index: int, track_item_index: int,
                            range_start_seconds: float, range_end_seconds: float):
    """
    UNSAFE for transcript cuts: operates on video only, so it can desync linked
    audio. Prefer remove_silence_segments. See the premiere-mcp-ops skill.

    Removes a section from a video clip, keeping the content before and after the range.

    The clip will be split at the range boundaries, and the middle section will be
    removed (the second part will be moved to connect with the first part).

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        video_track_index (int): The index of the video track containing the clip.
        track_item_index (int): The index of the clip within the track.
        range_start_seconds (float): Start of the range to remove (in sequence time).
        range_end_seconds (float): End of the range to remove (in sequence time).
    """
    TICKS_PER_SECOND = 254016000000

    command = createCommand("removeVideoClipRange", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "trackItemIndex": track_item_index,
        "rangeStartTicks": int(range_start_seconds * TICKS_PER_SECOND),
        "rangeEndTicks": int(range_end_seconds * TICKS_PER_SECOND)
    })

    return sendCommand(command)

@mcp.tool()
def remove_linked_clip_range(sequence_id: str, track_item_index: int,
                             range_start_seconds: float, range_end_seconds: float,
                             video_track_index: int = 0, audio_track_index: int = 0):
    """
    UNSAFE for transcript cuts: API-based split+ripple has desynced linked
    video/audio in this project. Prefer remove_silence_segments (native Extract).
    See the premiere-mcp-ops skill.

    Removes a section from BOTH video and audio clips together, keeping content before and after.

    The clips will be split at the range boundaries, and the middle section will be
    removed with the second part moved to connect with the first part.

    Args:
        sequence_id (str): The id of the sequence containing the clip.
        track_item_index (int): The index of the clip within the track.
        range_start_seconds (float): Start of the range to remove (in sequence time).
        range_end_seconds (float): End of the range to remove (in sequence time).
        video_track_index (int): The index of the video track. Defaults to 0.
        audio_track_index (int): The index of the audio track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    command = createCommand("removeLinkedClipRange", {
        "sequenceId": sequence_id,
        "videoTrackIndex": video_track_index,
        "audioTrackIndex": audio_track_index,
        "trackItemIndex": track_item_index,
        "rangeStartTicks": int(range_start_seconds * TICKS_PER_SECOND),
        "rangeEndTicks": int(range_end_seconds * TICKS_PER_SECOND)
    })

    return sendCommand(command)

@mcp.tool()
def get_player_position(sequence_id: str):
    """
    Gets the current playhead/player position in the sequence.

    Args:
        sequence_id (str): The id of the sequence.

    Returns:
        Dict with position in ticks and seconds.
    """
    command = createCommand("getPlayerPosition", {
        "sequenceId": sequence_id
    })
    return sendCommand(command)


@mcp.tool()
def set_player_position(sequence_id: str, position_seconds: float):
    """
    Sets the playhead/player position in the sequence.

    Args:
        sequence_id (str): The id of the sequence.
        position_seconds (float): The position in seconds from the start of the sequence.
    """
    TICKS_PER_SECOND = 254016000000
    position_ticks = int(position_seconds * TICKS_PER_SECOND)

    command = createCommand("setPlayerPosition", {
        "sequenceId": sequence_id,
        "positionTicks": position_ticks
    })
    return sendCommand(command)


@mcp.tool()
def add_marker(sequence_id: str, start_time_seconds: float, name: str = "Marker",
               marker_type: str = "Comment", duration_seconds: float = None, comments: str = ""):
    """
    Adds a marker to the sequence at the specified time.

    Args:
        sequence_id (str): The id of the sequence.
        start_time_seconds (float): Position in seconds where the marker should be placed.
        name (str, optional): Name of the marker. Defaults to "Marker".
        marker_type (str, optional): Type of marker ("Comment", "Chapter", "Segmentation", etc.). Defaults to "Comment".
        duration_seconds (float, optional): Duration of the marker in seconds. Defaults to None (point marker).
        comments (str, optional): Additional comments for the marker. Defaults to "".
    """
    TICKS_PER_SECOND = 254016000000

    options = {
        "sequenceId": sequence_id,
        "startTimeTicks": int(start_time_seconds * TICKS_PER_SECOND),
        "name": name,
        "markerType": marker_type,
        "comments": comments
    }

    if duration_seconds is not None:
        options["durationTicks"] = int(duration_seconds * TICKS_PER_SECOND)

    command = createCommand("addMarker", options)
    return sendCommand(command)


@mcp.tool()
def get_markers(sequence_id: str):
    """
    Gets all markers in the sequence.

    Args:
        sequence_id (str): The id of the sequence.

    Returns:
        Dict with list of markers including name, type, position, duration, and comments.
    """
    command = createCommand("getMarkers", {
        "sequenceId": sequence_id
    })
    return sendCommand(command)


@mcp.tool()
def remove_marker(sequence_id: str, marker_index: int):
    """
    Removes a marker from the sequence by its index.

    Args:
        sequence_id (str): The id of the sequence.
        marker_index (int): The index of the marker to remove (0-based).
    """
    command = createCommand("removeMarker", {
        "sequenceId": sequence_id,
        "markerIndex": marker_index
    })
    return sendCommand(command)


@mcp.tool()
def remove_clips(sequence_id: str, video_items: list = None, audio_items: list = None, ripple: bool = False,
                 linked: bool = True, audio_track_index: int = 0):
    """
    Removes clips from the timeline. By default, also removes linked audio/video counterparts.

    Args:
        sequence_id (str): The id of the sequence.
        video_items (list, optional): List of video clips to remove. Each item should be a dict with
            "trackIndex" and "clipIndex" keys.
            Example: [{"trackIndex": 0, "clipIndex": 0}, {"trackIndex": 0, "clipIndex": 1}]
        audio_items (list, optional): List of audio clips to remove. Same format as video_items.
        ripple (bool, optional): If True, close the gap after removing clips. Defaults to False.
        linked (bool, optional): If True, also remove the linked audio/video counterparts. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    command = createCommand("removeClips", {
        "sequenceId": sequence_id,
        "videoItems": video_items or [],
        "audioItems": audio_items or [],
        "ripple": ripple,
        "linked": linked,
        "linkedTrackIndex": audio_track_index
    })
    return sendCommand(command)


@mcp.tool()
def duplicate_clip(sequence_id: str, track_index: int, clip_index: int, is_video: bool,
                   time_offset_seconds: float, video_track_offset: int = 0, audio_track_offset: int = 0,
                   insert: bool = False, linked: bool = True, audio_track_index: int = 0):
    """
    Duplicates a clip on the timeline. By default, also duplicates the linked audio/video counterpart.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip to duplicate.
        is_video (bool): True if duplicating a video clip, False for audio.
        time_offset_seconds (float): Where to place the duplicate (in seconds from sequence start).
        video_track_offset (int, optional): Number of tracks to offset for video. Defaults to 0.
        audio_track_offset (int, optional): Number of tracks to offset for audio. Defaults to 0.
        insert (bool, optional): If True, insert and shift other clips. Defaults to False (overwrite).
        linked (bool, optional): If True, also duplicate the linked audio/video counterpart. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    command = createCommand("duplicateClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video,
        "timeOffsetTicks": int(time_offset_seconds * TICKS_PER_SECOND),
        "videoTrackOffset": video_track_offset,
        "audioTrackOffset": audio_track_offset,
        "insert": insert,
        "linked": linked,
        "linkedTrackIndex": audio_track_index
    })
    return sendCommand(command)


@mcp.tool()
def move_clip(sequence_id: str, track_index: int, clip_index: int, is_video: bool, move_time_seconds: float,
              linked: bool = True, audio_track_index: int = 0):
    """
    Moves a clip by a time offset on the timeline (relative move). By default, also moves the linked audio/video counterpart.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip to move.
        is_video (bool): True if moving a video clip, False for audio.
        move_time_seconds (float): Time offset in seconds (positive = right, negative = left).
        linked (bool, optional): If True, also move the linked audio/video counterpart. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    command = createCommand("moveClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video,
        "moveTimeTicks": int(move_time_seconds * TICKS_PER_SECOND),
        "linked": linked,
        "linkedTrackIndex": audio_track_index
    })
    return sendCommand(command)


@mcp.tool()
def set_clip_position(sequence_id: str, track_index: int, clip_index: int, is_video: bool, new_start_seconds: float,
                      linked: bool = True, audio_track_index: int = 0):
    """
    UNSAFE: can stretch/expand clips instead of moving them. Do NOT use to close
    gaps. Prefer letting remove_silence_segments regroup via Extract. See the
    premiere-mcp-ops skill.

    Moves a clip to an absolute position on the timeline. By default, also moves the linked audio/video counterpart.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip to move.
        is_video (bool): True if moving a video clip, False for audio.
        new_start_seconds (float): The new start position in seconds (absolute, from sequence start).
        linked (bool, optional): If True, also move the linked audio/video counterpart. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.
    """
    TICKS_PER_SECOND = 254016000000

    command = createCommand("setClipPosition", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video,
        "newStartTicks": int(new_start_seconds * TICKS_PER_SECOND),
        "linked": linked,
        "linkedTrackIndex": audio_track_index
    })
    return sendCommand(command)


@mcp.tool()
def get_sequence_settings(sequence_id: str):
    """
    Gets the settings and info for a sequence.

    Args:
        sequence_id (str): The id of the sequence.

    Returns:
        Dict with sequence name, id, frame dimensions, and duration.
    """
    command = createCommand("getSequenceSettings", {
        "sequenceId": sequence_id
    })
    return sendCommand(command)


@mcp.tool()
def rename_clip(sequence_id: str, track_index: int, clip_index: int, is_video: bool, new_name: str):
    """
    Renames a clip in the timeline.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip to rename.
        is_video (bool): True if renaming a video clip, False for audio.
        new_name (str): The new name for the clip.
    """
    command = createCommand("renameClip", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video,
        "newName": new_name
    })
    return sendCommand(command)


@mcp.tool()
def delete_clip(sequence_id: str, track_index: int, clip_index: int, is_video: bool,
                linked: bool = True, audio_track_index: int = 0):
    """
    Delete a specific clip. By default, also deletes the linked audio/video counterpart.

    Leaves a gap where the clip was (no ripple). Use this when you want to
    remove clips without shifting content on other tracks.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip to delete.
        is_video (bool): True if deleting a video clip, False for audio.
        linked (bool, optional): If True, also delete the linked audio/video counterpart. Defaults to True.
        audio_track_index (int, optional): The index of the linked counterpart track. Defaults to 0.

    Returns:
        Dict with success message.
    """
    if is_video:
        video_items = [{"trackIndex": track_index, "clipIndex": clip_index}]
        audio_items = []
    else:
        video_items = []
        audio_items = [{"trackIndex": track_index, "clipIndex": clip_index}]

    command = createCommand("removeClips", {
        "sequenceId": sequence_id,
        "videoItems": video_items,
        "audioItems": audio_items,
        "ripple": False,
        "linked": linked,
        "linkedTrackIndex": audio_track_index
    })
    return sendCommand(command)


@mcp.tool()
def get_clip_info(sequence_id: str, track_index: int, clip_index: int, is_video: bool):
    """
    Get detailed information about a specific clip.

    Returns start time, end time, duration, in/out points, and clip name.
    Useful for understanding clip positions before editing operations.

    Args:
        sequence_id (str): The id of the sequence.
        track_index (int): The index of the track containing the clip.
        clip_index (int): The index of the clip.
        is_video (bool): True for video clip, False for audio clip.

    Returns:
        Dict with clip details:
        - name: Clip name
        - startTimeTicks/startTimeSeconds: Timeline position where clip starts
        - endTimeTicks/endTimeSeconds: Timeline position where clip ends
        - durationTicks/durationSeconds: Clip duration
        - inPointTicks/inPointSeconds: Source media in-point
        - outPointTicks/outPointSeconds: Source media out-point
        - disabled: Whether the clip is disabled
    """
    command = createCommand("getClipInfo", {
        "sequenceId": sequence_id,
        "trackIndex": track_index,
        "clipIndex": clip_index,
        "isVideo": is_video
    })
    return sendCommand(command)


# =============================================================================
# KEYBOARD SHORTCUT TOOLS (via AppleScript)
# These bypass the UXP API and send keystrokes directly to Premiere Pro
# =============================================================================

@mcp.tool()
def send_keystroke(key: str, command: bool = False, shift: bool = False, option: bool = False, control: bool = False):
    """
    Send a keyboard shortcut to Premiere Pro.

    This uses AppleScript to send keystrokes directly to Premiere,
    bypassing the UXP API limitations.

    Args:
        key (str): The key to press (single character like "t", "e", "z", etc.)
        command (bool): Hold Command key. Defaults to False.
        shift (bool): Hold Shift key. Defaults to False.
        option (bool): Hold Option key. Defaults to False.
        control (bool): Hold Control key. Defaults to False.

    Example:
        send_keystroke("t", command=True)  # Cmd+T
        send_keystroke("z", command=True)  # Cmd+Z (undo)
    """
    modifiers = []
    if command:
        modifiers.append("command")
    if shift:
        modifiers.append("shift")
    if option:
        modifiers.append("option")
    if control:
        modifiers.append("control")

    send_keystroke_to_premiere(key, modifiers)
    return {"success": True, "key": key, "modifiers": modifiers}


@mcp.tool()
def cut_at_playhead():
    """
    UNSAFE for transcript cuts: razoring at the playhead and deleting separately
    is not verified and can desync A/V. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Cut/razor all tracks at the current playhead position.

    This sends Cmd+D to Premiere Pro.
    Make sure the playhead is at the desired position first using set_player_position.
    """
    send_keystroke_to_premiere("d", ["command"])
    return {"success": True, "action": "cut_at_playhead"}


@mcp.tool()
def ripple_delete():
    """
    UNSAFE for transcript cuts: a bare ripple delete is not verified and can hit
    the wrong segment or desync A/V. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Ripple delete the clip segment at the current playhead position.

    This sends Cmd+E (or your configured ripple delete shortcut) to Premiere Pro.
    The clip under the playhead will be deleted and the gap will be closed.
    """
    send_keystroke_to_premiere("e", ["command"])
    return {"success": True, "action": "ripple_delete"}


@mcp.tool()
def undo():
    """
    Undo the last action in Premiere Pro.

    Sends Cmd+Z to Premiere Pro.
    """
    send_keystroke_to_premiere("z", ["command"])
    return {"success": True, "action": "undo"}


@mcp.tool()
def redo():
    """
    Redo the last undone action in Premiere Pro.

    Sends Cmd+Shift+Z to Premiere Pro.
    """
    send_keystroke_to_premiere("z", ["command", "shift"])
    return {"success": True, "action": "redo"}


@mcp.tool()
def select_all():
    """
    Select all clips in the timeline.

    Sends Cmd+A to Premiere Pro.
    """
    send_keystroke_to_premiere("a", ["command"])
    return {"success": True, "action": "select_all"}


@mcp.tool()
def deselect_all():
    """
    Deselect all clips in the timeline.

    Sends Cmd+Shift+A to Premiere Pro.
    """
    send_keystroke_to_premiere("a", ["command", "shift"])
    return {"success": True, "action": "deselect_all"}


@mcp.tool()
def delete_selected():
    """
    Delete the currently selected clips.

    Sends Delete/Backspace key to Premiere Pro.
    """
    # Key code 51 is Delete/Backspace
    send_key_code_to_premiere(51)
    return {"success": True, "action": "delete_selected"}


@mcp.tool()
def play_pause():
    """
    Toggle play/pause in Premiere Pro.

    Sends Space key to Premiere Pro.
    """
    send_keystroke_to_premiere(" ", [])
    return {"success": True, "action": "play_pause"}


@mcp.tool()
def go_to_start():
    """
    Move playhead to the start of the sequence.

    Sends Home key to Premiere Pro.
    """
    # Key code 115 is Home
    send_key_code_to_premiere(115)
    return {"success": True, "action": "go_to_start"}


@mcp.tool()
def go_to_end():
    """
    Move playhead to the end of the sequence.

    Sends End key to Premiere Pro.
    """
    # Key code 119 is End
    send_key_code_to_premiere(119)
    return {"success": True, "action": "go_to_end"}


@mcp.tool()
def remove_silence_segments(sequence_id: str, silence_segments: list,
                            frame_snap: bool = True, verify: bool = True):
    """
    Cut the given segments out of the sequence and regroup (close the gaps).

    This is the PRIMARY editing primitive for transcript-based cuts. For each
    segment it sets the sequence in/out points (via the UXP API) and triggers
    Premiere's native Extract command (apostrophe, macOS key code 39). Extract
    ripple-deletes the marked range across the TARGETED video AND audio tracks
    and shifts the remaining clips left to close the gap, so cutting and
    regrouping happen together in one native, A/V-synced operation.

    Segments are processed from END to START so earlier timecodes do not shift
    before they are cut.

    Args:
        sequence_id (str): The id of the sequence to cut.
        silence_segments (list): Segments to remove, in sequence-timeline seconds.
            Each is a dict {"start": <sec>, "end": <sec>}.
            Example: [{"start": 10.5, "end": 12.3}, {"start": 25.0, "end": 27.5}]
        frame_snap (bool): Snap each range to whole-frame boundaries before cutting
            to avoid 1-frame video/audio gaps. Defaults to True. Skipped silently
            if the sequence frame rate cannot be read.
        verify (bool): After cutting, read the ACTUAL clip layout back from
            Premiere and confirm the duration changed by the expected amount, no
            gaps remain, and video/audio shifted by the same amount. Defaults to
            True.

    IMPORTANT: Treat "verified": false (or null, when verification could not run)
    as NOT confirmed. Do not report the cut as successful — inspect the
    "verification" block and follow the premiere-mcp-ops hard-stop contract.
    Premiere must be frontmost with the Timeline focused for Extract to land, and
    track targeting must include every track you intend to cut.
    """
    if not silence_segments:
        return {
            "action": "remove_silence_segments",
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": None,
            "verification": {"reason": "No segments supplied; nothing to cut."},
        }

    # SAFETY: the Extract keystroke lands on the ACTIVE/focused Timeline, which
    # may not be the sequence_id passed. We ALWAYS make sequence_id active first
    # (idempotent, and it focuses that Timeline) so we never rely on the right one
    # already being focused — this is what stops the guard from "failing open"
    # when the active id cannot be read. Then we confirm: if the active id reads
    # back as a DIFFERENT sequence, setActiveSequence did not stick and we refuse
    # (Extract would razor the wrong timeline). If it cannot be read at all, we
    # proceed having set it active — the post-cut verify of THIS sequence_id will
    # show no change if Extract somehow landed elsewhere.
    try:
        sendCommand(createCommand("setActiveSequence", {"sequenceId": sequence_id}))
        time.sleep(0.4)
    except Exception:
        pass
    active_id = _active_sequence_id()
    if active_id and active_id != str(sequence_id):
        return {
            "action": "remove_silence_segments",
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": False,
            "verification": {
                "verified": False,
                "reason": (
                    f"Target sequence {sequence_id} could not be made active "
                    f"(active is {active_id}). Extract would cut the wrong timeline. "
                    "Open/click the target sequence's Timeline tab so it is active, "
                    "then retry."
                ),
            },
            "nextSteps": [
                f"In Premiere, click the Timeline tab for sequence {sequence_id} "
                "so it becomes the active/focused sequence.",
                "Re-run remove_silence_segments with the same arguments.",
            ],
        }
    active_unconfirmed = not active_id

    # Sort segments by start time descending (process from end to start).
    sorted_segments = sorted(silence_segments, key=lambda x: x["start"], reverse=True)

    # Pre-cut baseline (also gives us the frame rate for snapping).
    before_summary = None
    frame_ticks = None
    if verify or frame_snap:
        try:
            before_summary = _summarize_layout(_fetch_layout(sequence_id))
            frame_ticks = before_summary.get("frameTicks")
        except Exception as e:
            before_summary = {"error": str(e)}

    # Activate Premiere ONCE for the whole batch. Per-cut activation can hang
    # while Premiere is busy, so we deliberately do not re-activate per segment.
    try:
        _ensure_premiere_focused()
    except Exception:
        pass

    succeeded = 0
    failed = 0
    results = []
    expected_removed_ticks = 0
    for seg in sorted_segments:
        start = seg.get("start")
        end = seg.get("end")

        in_ticks = int(start * TICKS_PER_SECOND)
        out_ticks = int(end * TICKS_PER_SECOND)
        if frame_snap and frame_ticks:
            in_ticks = _snap_to_frame(in_ticks, frame_ticks, "round")
            out_ticks = _snap_to_frame(out_ticks, frame_ticks, "round")
            if out_ticks <= in_ticks:
                out_ticks = in_ticks + frame_ticks  # never collapse to zero length

        seg_ok = False
        last_err = None
        for attempt in range(3):  # up to 2 retries
            try:
                command = createCommand("setSequenceInOutPoints", {
                    "sequenceId": sequence_id,
                    "inPointTicks": in_ticks,
                    "outPointTicks": out_ticks
                })
                sendCommand(command)
                time.sleep(0.5)

                # Extract (ripple delete the marked range). Premiere's default
                # Extract shortcut is apostrophe = macOS key code 39.
                _send_key_code_fast(39)
                time.sleep(1.5)

                seg_ok = True
                break
            except Exception as e:
                last_err = str(e)
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))

        if seg_ok:
            succeeded += 1
            expected_removed_ticks += (out_ticks - in_ticks)
            results.append({
                "start": start, "end": end,
                "inTicks": in_ticks, "outTicks": out_ticks, "success": True,
            })
        else:
            failed += 1
            results.append({"start": start, "end": end, "success": False, "error": last_err})

    out = {
        "action": "remove_silence_segments",
        "processed": len(sorted_segments),
        "succeeded": succeeded,
        "failed": failed,
        "frameSnapped": bool(frame_snap and frame_ticks),
        "activeSequenceConfirmed": not active_unconfirmed,
        "results": results,
        "verified": None,
        "verification": None,
    }

    if verify:
        verification = _verify_cut(
            sequence_id, before_summary, expected_removed_ticks, frame_ticks,
            cut_count=succeeded,
        )
        out["verification"] = verification
        out["verified"] = verification.get("verified")
        # Surface the two facts the user explicitly cares about at the top level
        # so callers don't have to dig into the verification block.
        out["packed"] = verification.get("packed")
        out["avSynced"] = verification.get("avSynced")
        out["nextSteps"] = _cut_next_steps(verification, sequence_id)

    return out


def _cut_next_steps(verification: dict, sequence_id: str) -> list:
    """Plain next-step instructions for the user, derived from verification.

    The user asked to be told exactly what to do next, then have it re-checked.
    """
    if not verification:
        return []
    if verification.get("verified") and verification.get("packed") and verification.get("avSynced"):
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
            "A pre-existing gap remains elsewhere. Click into it and ripple-delete it "
            f"(or report it). Then re-run verify_sequence_layout('{sequence_id}')."
        )
    if verification.get("verified") is False and not steps:
        steps.append(
            f"Cut not confirmed — run verify_sequence_layout('{sequence_id}') and inspect "
            "the warnings before continuing."
        )
    steps.append(f"After fixing, re-run verify_sequence_layout('{sequence_id}') to re-validate.")
    return steps


@mcp.tool()
def verify_sequence_layout(sequence_id: str):
    """
    Inspect the live sequence and report clip counts, duration, gaps, and A/V skew.

    This is the verification harness for the cutting workflow. It reads the ACTUAL
    clip layout from Premiere (never a tool's success flag) so you can confirm a
    cut really applied and that the timeline is packed with no gaps.

    Args:
        sequence_id (str): The id of the sequence to inspect.

    Returns a dict with:
        - videoClipCount / audioClipCount
        - durationSeconds
        - gaps: list of remaining gaps, per media-lane, INCLUDING a leading gap
          before the first clip (kind, trackIndex, leading, start/end, gapSeconds,
          gapFrames)
        - packed: True when zero gaps remain on any lane (fully back to back)
        - avMisalignments: cut junctions where video and audio do NOT line up
          within one frame (empty == frame-accurate sync)
        - videoAudioInSync: True when there are no misalignments AND the ends are
          within ~2 frames
        - warnings: plain-language problems, if any
    """
    layout = _fetch_layout(sequence_id)
    summary = _summarize_layout(layout)
    video, audio = _clips_from_layout(layout)
    summary["sequenceId"] = layout.get("id")
    summary["sequenceName"] = layout.get("name")
    summary["packed"] = summary["gapCount"] == 0

    ft = summary.get("frameTicks") or int(TICKS_PER_SECOND / 24)

    # Frame-accurate A/V sync: every internal cut must land on the same timecode
    # for video and audio. This is the precise "audio drifted a frame" check.
    misalignments = _av_misalignments(video, audio, ft) if (video and audio) else []
    summary["avMisalignments"] = misalignments

    skew = abs(summary["videoEndTicks"] - summary["audioEndTicks"])
    summary["videoAudioEndSkewSeconds"] = round(skew / TICKS_PER_SECOND, 4)
    summary["videoAudioInSync"] = (not misalignments) and (skew <= 2 * ft)

    warnings = []
    if not summary["packed"]:
        leading = [g for g in summary["gaps"] if g.get("leading")]
        if leading:
            warnings.append(
                f"{len(leading)} clip lane(s) do not start at 0 — there is a gap "
                "before the first clip; the sequence is not back to back."
            )
        inter = summary["gapCount"] - len(leading)
        if inter > 0:
            warnings.append(f"{inter} gap(s) between clips — clips are not back to back.")
    if misalignments:
        spots = ", ".join(f"{m['side']}@{m['seconds']}s" for m in misalignments[:6])
        warnings.append(
            f"AUDIO/VIDEO OUT OF SYNC at {len(misalignments)} cut point(s): {spots}. "
            "A cut landed on a different frame for video vs audio."
        )
    elif not summary["videoAudioInSync"]:
        warnings.append(
            f"Video and audio ends differ by {summary['videoAudioEndSkewSeconds']}s "
            "(> 2 frames) — possible A/V desync at the tail."
        )
    summary["warnings"] = warnings
    return summary


# RETIRED: not registered as an MCP tool. This cut-then-ripple approach could
# desync video/audio and was never verified. Kept only for reference; use
# remove_silence_segments (which Extracts and verifies). Do not re-add @mcp.tool().
def cut_and_ripple_delete_at_times(sequence_id: str, times_seconds: list, video_track_index: int = 0, audio_track_index: int = 0):
    """
    RETIRED — not exposed as a tool. Use remove_silence_segments instead.

    This function cuts at each time and immediately ripple deletes, which may not work
    as expected and can desync linked audio/video.
    """
    TICKS_PER_SECOND = 254016000000
    sorted_times = sorted(times_seconds, reverse=True)

    results = []
    for t in sorted_times:
        try:
            position_ticks = int(t * TICKS_PER_SECOND)
            command = createCommand("setPlayerPosition", {
                "sequenceId": sequence_id,
                "positionTicks": position_ticks
            })
            sendCommand(command)
            time.sleep(0.15)

            send_keystroke_to_premiere("d", ["command"])
            time.sleep(0.1)

            send_keystroke_to_premiere("e", ["command"])
            time.sleep(0.1)

            results.append({"time": t, "success": True})
        except Exception as e:
            results.append({"time": t, "success": False, "error": str(e)})

    return {
        "action": "cut_and_ripple_delete_at_times",
        "processed": len(sorted_times),
        "results": results
    }


@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use Premiere Pro and this API"""

    return f"""
    You are a Premiere Pro and video expert who is creative and loves to help other people learn to use Premiere and create.

    Rules to follow:

    1. Think deeply about how to solve the task
    2. Always check your work
    3. Read the info for the API calls to make sure you understand the requirements and arguments
    4. In general, add clips first, then effects, then transitions
    5. As a general rule keep transitions short (no more that 2 seconds is a good rule), and there should not be a gap between clips (or else the transition may not work)

    IMPORTANT: To create a new project and add clips:
    1. Create new project (create_project)
    2. Add media to the project (import_media)
    3. Create a new sequence with media (should always add video / image clips before audio.(create_sequence_from_media). This will create a sequence with the clips.
    4. The first clip you add will determine the dimensions / resolution of the sequence

    AVAILABLE TOOLS:

    Project Management:
    - create_project, open_project, save_project, save_project_as
    - get_project_info

    Sequence Management:
    - create_sequence_from_media, set_active_sequence
    - get_sequence_settings

    Media & Timeline:
    - import_media - import files into project
    - add_media_to_sequence - add clips to timeline

    Clip Editing:
    - split_video_clip, split_audio_clip - split clips at a specific time
    - trim_video_clip, trim_audio_clip - adjust in/out points and timeline position
    - remove_video_clip_range - remove a section from a clip (for silence removal)
    - remove_clips - delete clips from timeline (with optional ripple)
    - delete_clip - delete a single clip WITHOUT ripple (track-specific, leaves gaps)
    - get_clip_info - get detailed info about a clip (start, end, duration, in/out points)
    - duplicate_clip - clone a clip
    - move_clip - reposition clips on timeline (relative)
    - set_clip_position - move clip to absolute position
    - rename_clip - change clip name
    - set_video_clip_disabled, set_audio_clip_disabled - enable/disable clips

    Effects & Transitions:
    - add_black_and_white_effect, add_gaussian_blur_effect, add_tint_effect, add_motion_blur_effect
    - append_video_transition - add transitions between clips
    - set_video_clip_properties - opacity and blend mode

    Audio:
    - set_audio_track_mute - mute/unmute audio tracks

    Markers:
    - add_marker - add markers to sequence
    - get_markers - list all markers
    - remove_marker - delete a marker

    Playhead Control:
    - get_player_position - get current playhead position
    - set_player_position - move playhead

    Export:
    - export_frame - export a single frame as PNG

    GENERAL TIPS:

    Audio and Video clips are added on separate Audio / Video tracks, which you can access via their index.

    When adding a video clip that contains audio, the audio will be placed on a separate audio track.

    You can remove clips using remove_clips, or disable them using set_video_clip_disabled/set_audio_clip_disabled.

    For silence removal workflow:
    1. Detect silence segments (external tool)
    2. Use split_video_clip/split_audio_clip to split at silence boundaries
    3. Use remove_clips with ripple=True to remove silent sections and close gaps

    TRACK-SPECIFIC EDITING (avoiding ripple delete issues):
    Ripple delete (Cmd+E) affects ALL unlocked tracks - this is Premiere's design.
    To edit specific tracks without affecting others, use API-based clip management:

    Workflow for editing V2/A2 without affecting V1/A1:
    1. get_full_project_data() - see all clips and their positions
    2. get_clip_info() - get details on specific clips
    3. delete_clip() - remove clips WITHOUT rippling (leaves gaps)
    4. set_clip_position() - move remaining clips into position

    Alternative (non-destructive):
    - set_video_clip_disabled() / set_audio_clip_disabled() - disable unwanted clips
    - Disabled clips don't play but can be re-enabled later

    If you want to do a transition between two clips, the clips must be on the same track and there should not be a gap between them. Place the transition on the first clip.

    Video clips with a higher track index will overlap and hide those with lower index if they overlap.

    When adding images to a sequence, they will have a duration of 5 seconds.

    TIME FORMAT:
    - All time values in the API use seconds (float)
    - Internally Premiere uses ticks (254016000000 ticks per second)
    - The API handles the conversion automatically

    blend_modes: {", ".join(BLEND_MODES)}
    """


BLEND_MODES = [
    "COLOR",
    "COLORBURN",
    "COLORDODGE",
    "DARKEN",
    "DARKERCOLOR",
    "DIFFERENCE",
    "DISSOLVE",
    "EXCLUSION",
    "HARDLIGHT",
    "HARDMIX",
    "HUE",
    "LIGHTEN",
    "LIGHTERCOLOR",
    "LINEARBURN",
    "LINEARDODGE",
    "LINEARLIGHT",
    "LUMINOSITY",
    "MULTIPLY",
    "NORMAL",
    "OVERLAY",
    "PINLIGHT",
    "SATURATION",
    "SCREEN",
    "SOFTLIGHT",
    "VIVIDLIGHT",
    "SUBTRACT",
    "DIVIDE"
]

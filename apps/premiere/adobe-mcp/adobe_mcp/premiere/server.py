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

import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

from mcp.server.fastmcp import FastMCP, Image

from ..shared import createCommand, init, sendCommand, socket_client
from .constants import TICKS_PER_SECOND
from .layout import (
    av_misalignments,
    clips_from_layout,
    frame_ticks,
    lane_roles,
    program_clips,
    summarize_layout,
)
from .plan import (
    plan_cuts,
    probe_from_layout,
    removed_since,
    validate_segments,
)
from .verify import cut_next_steps, verify_cut

# Local aliases so existing call sites keep their _prefixed names.
_frame_ticks = frame_ticks
_clips_from_layout = clips_from_layout
_summarize_layout = summarize_layout
_validate_segments = validate_segments
_plan_cuts = plan_cuts
_probe_from_layout = probe_from_layout
_removed_since = removed_since
_cut_next_steps = cut_next_steps
_lane_roles = lane_roles
_program_clips = program_clips
_av_misalignments = av_misalignments

# Name of the Premiere Pro application as macOS sees it (used by AppleScript).
# Override with PREMIERE_APP_NAME when targeting a different version, e.g.
# "Adobe Premiere Pro 2025". This avoids a yearly hard-coded breakage.
PREMIERE_APP_NAME = os.environ.get("PREMIERE_APP_NAME", "Adobe Premiere Pro 2026")

# Optional absolute .app path for `open -a`. LaunchServices normally resolves
# PREMIERE_APP_NAME on its own; set this when several Premiere versions are
# installed and the name is ambiguous, e.g.
# "/Applications/Adobe Premiere Pro 2026/Adobe Premiere Pro 2026.app".
PREMIERE_APP_PATH = os.environ.get("PREMIERE_APP_PATH", "")


def _run_osascript(script: str, timeout: int = 10):
    """Run one AppleScript snippet; returns the CompletedProcess."""
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _send_key_to_premiere(key: str = None, key_code: int = None,
                          modifiers: list = None, activate: bool = True,
                          retries: int = 0):
    """Send one keystroke (by character or key code) to Premiere via AppleScript.

    activate=True brings Premiere frontmost first via _ensure_premiere_focused()
    (LaunchServices + a confirmed frontmost poll) and RAISES if focus cannot be
    confirmed; activate=False assumes the caller already focused Premiere (batch
    mode). The keystroke itself never goes through AppleScript's `activate`: that
    is an Apple event to Premiere's main thread, which stops answering while the
    app is busy, so it blocks for the whole osascript timeout and fails -1712
    even though the app is healthy (this is what killed `undo` mid-recovery).
    System Events keystrokes keep working in that state.

    Retries only on -1712 Apple-event timeouts. NOTE: a -1712 can fire AFTER the
    key event was delivered, so callers cutting the timeline must NOT blindly
    retry on failure — verify the timeline state instead (see the cut loop).
    """
    if modifiers:
        modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    else:
        modifier_str = ""
    press = f'keystroke "{key}"{modifier_str}' if key is not None else f"key code {key_code}{modifier_str}"

    script = f'''tell application "System Events"
    {press}
end tell'''

    if activate:
        # Raises if Premiere cannot be confirmed frontmost — better than typing
        # a destructive key into whatever window happens to be in front.
        _ensure_premiere_focused()

    last_error = None
    for attempt in range(retries + 1):
        result = _run_osascript(script)
        if result.returncode == 0:
            return True
        last_error = result.stderr
        if "-1712" in result.stderr and attempt < retries:
            time.sleep(0.3 * (attempt + 1))
            continue
        break

    raise Exception(f"AppleScript error: {last_error}")


def send_keystroke_to_premiere(key: str, modifiers: list = None, retries: int = 0):
    """Send a keystroke to Premiere Pro (activates Premiere first).

    retries defaults to 0: a -1712 timeout can fire AFTER the key was
    delivered, so retrying a destructive shortcut (undo, Extract, Delete)
    can double-fire. The cut path never retries blindly; neither should
    the public keyboard tools.
    """
    return _send_key_to_premiere(key=key, modifiers=modifiers, retries=retries)


def send_key_code_to_premiere(key_code: int, modifiers: list = None, retries: int = 0):
    """Send a key code to Premiere Pro (activates Premiere first)."""
    return _send_key_to_premiere(key_code=key_code, modifiers=modifiers, retries=retries)


def _launch_premiere_frontmost():
    """Ask LaunchServices (`open -a`) to raise Premiere. Returns (ok, error).

    Deliberately NOT AppleScript's `activate`: that is an Apple event to
    Premiere's main thread and hangs for the full timeout (-1712) whenever the
    app is busy, even though the app is fine and UXP keeps answering. `open`
    goes through LaunchServices, which has no such dependency.
    """
    target = PREMIERE_APP_PATH or PREMIERE_APP_NAME
    try:
        result = subprocess.run(
            ["open", "-a", target], capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired:
        return False, f"`open -a {target}` timed out"
    except Exception as e:
        return False, f"`open -a {target}` failed: {e}"
    if result.returncode != 0:
        return False, (result.stderr or "").strip() or f"`open -a {target}` failed"
    return True, None


def _ensure_premiere_focused(timeout: float = 6.0):
    """Bring Premiere frontmost before a batch operation and CONFIRM it, or raise.

    Every caller follows this with keystrokes that go to whatever app is
    frontmost — Extract, Close Gap, undo. So an unconfirmed focus attempt must
    never be allowed to look like success: that is exactly how a batch marks an
    In/Out range the Timeline never received and then Extracts a range nobody
    planned. Raise instead, and let the caller refuse to start.
    """
    ok, err = _launch_premiere_frontmost()
    deadline = time.time() + timeout
    state = None
    while True:
        state = _premiere_is_frontmost()
        if state is True:
            time.sleep(0.15)  # brief settle before the first keystroke
            return True
        if time.time() >= deadline:
            break
        time.sleep(0.15)

    if state is None:
        raise Exception(
            "Could not read the frontmost application via System Events — grant "
            "Automation/Accessibility permission to the process hosting this MCP "
            "server. Refusing to send keystrokes to an unverified window."
        )
    raise Exception(
        f"Premiere ('{PREMIERE_APP_NAME}') did not become frontmost within "
        f"{timeout:.1f}s"
        + (f" — {err}" if err else "")
        + ". Refusing to send keystrokes to another application."
    )


def _send_keystroke_fast(key: str, modifiers: list = None):
    """Send keystroke WITHOUT activate/delay/retry — use after _ensure_premiere_focused()."""
    return _send_key_to_premiere(key=key, modifiers=modifiers, activate=False, retries=0)


def _send_key_code_fast(key_code: int, modifiers: list = None):
    """Send key code WITHOUT activate/delay/retry — use after _ensure_premiere_focused()."""
    return _send_key_to_premiere(key_code=key_code, modifiers=modifiers, activate=False, retries=0)


def _premiere_is_frontmost():
    """True/False if the frontmost app can be read, None if the read fails.

    Read-only System Events query. Used before each destructive keystroke:
    if the user switched apps mid-batch, the keystroke would land in the wrong
    application, so the batch must stop rather than type into it.
    """
    try:
        result = _run_osascript(
            'tell application "System Events" to get name of first application '
            "process whose frontmost is true"
        )
        if result.returncode != 0:
            return None
        name = (result.stdout or "").strip()
        if not name:
            return None
        return name.lower() in PREMIERE_APP_NAME.lower() or PREMIERE_APP_NAME.lower() in name.lower()
    except Exception:
        return None


def _apple_events_responsive(timeout: int = 4):
    """True/False if Premiere answers a trivial Apple event, None if unreadable.

    Premiere's main thread stops answering Apple events while it is busy, and it
    keeps answering UXP over the proxy the whole time — so every other health
    read looks green while AppleScript `activate` hangs for its full timeout and
    fails -1712. Nothing in the cut path depends on Apple events any more (focus
    goes through LaunchServices, keystrokes through System Events), so this is
    diagnostic: it separates "Premiere is wedged/modal" from "the bridge broke".

    ONLY call this when Premiere is known to be running — `tell application`
    would otherwise LAUNCH it.
    """
    try:
        result = _run_osascript(
            f'tell application "{PREMIERE_APP_NAME}" to get name', timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return None
    if result.returncode == 0:
        return True
    if "-1712" in (result.stderr or ""):
        return False
    return None


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


def _verify_cut(sequence_id: str, before: dict, expected_removed_ticks: int,
                frame_ticks_value, cut_count=1):
    """Fetch the live post-cut layout and run the pure verifier."""
    try:
        after_layout = _fetch_layout(sequence_id)
    except Exception as e:
        return {"verified": None, "error": f"Could not read layout after cut: {e}"}
    return verify_cut(before, after_layout, expected_removed_ticks, frame_ticks_value, cut_count)


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
def export_frame(sequence_id:str, file_path: str, seconds: float):
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
    # UXP exportFrame does path.parse + appends ".png" to the basename. Passing
    # a path that already ends in .png writes "out.png.png". Strip one trailing
    # .png so the file Premiere writes is the path the caller asked for.
    request_path = file_path
    if request_path.lower().endswith(".png"):
        request_path = request_path[:-4]

    command = createCommand("exportFrame", {
        "sequenceId": sequence_id,
        "filePath": request_path,
        "seconds":seconds
        }
    )

    return sendCommand(command)


def _encode_frame_png(path: str, max_dimension: int = 1280) -> bytes:
    """Read a PNG from disk and, if it is larger than max_dimension on its
    longest edge, downscale it (preserving aspect) to keep the returned image
    cheap in tokens. max_dimension <= 0 returns the original bytes untouched.
    Falls back to the raw bytes if Pillow is unavailable or decoding fails."""
    with open(path, "rb") as f:
        raw = f.read()
    if not max_dimension or max_dimension <= 0:
        return raw
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(io.BytesIO(raw)) as im:
            width, height = im.size
            longest = max(width, height)
            if longest <= max_dimension:
                return raw
            scale = max_dimension / float(longest)
            new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            resized = im.resize(new_size, _PILImage.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return raw


@mcp.tool()
def get_sequence_frame_image(sequence_id: str, seconds: float, max_dimension: int = 1280):
    """Captures the frame at `seconds` and returns it to you as an inline image so
    you can VISUALLY confirm a cut junction after a transcript Extract — the right
    content is on screen, the expected frame is present, nothing duplicated or
    dropped. Use this alongside the numeric checks from verify_sequence_layout /
    remove_silence_segments (A/V sync, gaps, removed-frame deltas) when you want to
    actually see the result, not just read the metrics.

    Read-only: it does NOT modify the timeline. Unlike export_frame (which only
    writes a PNG to disk and returns the path), this returns the actual pixels.

    Args:
        sequence_id (str): The id of the sequence to capture from.
        seconds (float): Timestamp in seconds from the start of the sequence.
            Fractional / tick-precise values are supported, so you can land
            exactly on a cut-junction frame for inspection.
        max_dimension (int): Longest-edge pixel cap for the returned image; the
            frame is downscaled to fit (preserving aspect) to control token cost.
            Defaults to 1280. Set to 0 to return the frame at full sequence
            resolution.
    """
    tmp_dir = tempfile.gettempdir()
    base = f"premiere_frame_{uuid.uuid4().hex}"
    # Pass a base path WITHOUT an extension: the UXP exportFrame handler appends
    # ".png" itself, and its path reconstruction doubles the extension if one is
    # already present. We glob the result by unique prefix instead of trusting an
    # exact returned path.
    request_path = os.path.join(tmp_dir, base)

    command = createCommand("exportFrame", {
        "sequenceId": sequence_id,
        "filePath": request_path,
        "seconds": seconds,
    })
    result = sendCommand(command)

    candidates = sorted(
        p for p in glob.glob(os.path.join(tmp_dir, base + "*")) if os.path.isfile(p)
    )
    if not candidates:
        return {
            "error": "frame_export_failed",
            "detail": "Premiere did not write a frame PNG; cannot return an image. "
                      "Confirm the sequence is active and the proxy/plugin are connected.",
            "sequenceId": sequence_id,
            "seconds": seconds,
            "commandResult": result,
        }

    out_path = candidates[0]
    try:
        data = _encode_frame_png(out_path, max_dimension)
    finally:
        for p in candidates:
            try:
                os.remove(p)
            except OSError:
                pass

    return Image(data=data, format="png")


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

    if blur_dimensions not in dimensions:
        raise ValueError(
            f"Invalid blur_dimensions {blur_dimensions!r}; expected one of {sorted(dimensions)}."
        )

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
def add_tint_effect(sequence_id: str, video_track_index: int, track_item_index: int, black_map: dict = None):
    """
    Adds the tint effect to a clip at the specified track and position.

    KNOWN LIMITATION: only the "Map Black To" color is applied. Setting
    "Map White To" and "Amount to Tint" through the UXP parameter API has not
    worked reliably (inherited from upstream), so white stays at Premiere's
    default (pure white) and the amount at 100%. Adjust those two in the
    Effect Controls panel if needed.

    Args:
        sequence_id (str) : The id for the sequence to add the effect to
        video_track_index (int): The index of the video track containing the target clip.
            Track indices start at 0 for the first video track and increment upward.

        track_item_index (int): The index of the clip within the track to apply the effect to.
            Clip indices start at 0 for the first clip in the track and increment from left to right.

        black_map (dict): The RGB color values to map black/dark areas to, with keys "red", "green", and "blue".
            Default is {"red":0, "green":0, "blue":0} (pure black).
    """
    if black_map is None:
        black_map = {"red": 0, "green": 0, "blue": 0}

    command = createCommand("appendVideoFilter", {
        "sequenceId": sequence_id,
        "videoTrackIndex":video_track_index,
        "trackItemIndex":track_item_index,
        "effectName":"AE.ADBE Tint",
        "properties":[
            {"name":"Map Black To", "value":rgb_to_premiere_color(black_map)}
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
def append_video_transition(sequence_id: str, video_track_index: int, track_item_index: int, transition_name: str, duration: float = 1.0, clip_alignment: float = 0.5):
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
    UNSAFE for transcript cuts: splitting then deleting can desync linked
    video/audio or leave gaps. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

    Splits both video and audio clips at the specified time in a single operation.

    If you must split (outside the transcript-cut workflow), prefer this over
    split_video_clip/split_audio_clip: it splits video and audio together and
    creates a single undo entry (one Cmd+Z undoes the whole operation).

    Args:
        sequence_id (str): The id of the sequence.
        split_time_seconds (float): The time in seconds where the split should occur.
        video_track_index (int, optional): Video track index. If None, video is not split.
        video_clip_index (int, optional): Index of video clip on the track. Defaults to 0.
        audio_track_index (int, optional): Audio track index. If None, audio is not split.
        audio_clip_index (int, optional): Index of audio clip on the track. Defaults to 0.
    """
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
    UNSAFE for transcript cuts: removing clips (with or without ripple) bypasses
    the verified Extract path and can desync linked video/audio or leave gaps.
    Prefer remove_silence_segments. See the premiere-mcp-ops skill.

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
    UNSAFE: same createSetStartAction family as set_clip_position; can
    stretch/desync linked A/V. Do NOT use to close gaps. See premiere-mcp-ops.

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
    UNSAFE for transcript cuts: deleting a clip leaves a gap and bypasses the
    verified Extract path. Prefer remove_silence_segments. See the
    premiere-mcp-ops skill.

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
    UNSAFE: sends an arbitrary keystroke to whichever Premiere panel is
    focused. Can fire Extract, Ripple Trim, Delete, or any custom bind.
    Not part of the transcript-cut workflow. See premiere-mcp-ops.

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
    UNSAFE for transcript cuts: deletes the current selection with no
    verification and can desync A/V. Prefer remove_silence_segments.
    See the premiere-mcp-ops skill.

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


def _content_probe(sequence_id: str) -> dict:
    return _probe_from_layout(_fetch_layout(sequence_id))


def _wait_for_extract(sequence_id: str, probe_before: dict, cut_len_ticks: int,
                      frame_ticks, timeout: float = 4.0, interval: float = 0.25):
    """Poll the layout until the Extract shows up in the numbers, or timeout.

    This replaces the old fixed post-keystroke sleep: it returns as soon as the
    removal is visible (faster on a fast Premiere) and keeps waiting on a slow
    one (safer). It is also the per-segment success gate that makes keystroke
    retries safe: a keystroke error is only retried when a successful layout
    read shows the timeline did NOT change (probe=None means UNKNOWN, never
    retry), so a second Extract cannot double-cut wanted content.

    Returns {landed, matched, removedTicks, probe, error}.
    """
    ft = frame_ticks or int(TICKS_PER_SECOND / 24)
    min_change = max(1, min(ft // 2, cut_len_ticks // 2))
    tol = 2 * ft
    deadline = time.monotonic() + timeout
    removed = 0
    probe = None
    err = None
    mismatch_streak = 0
    while time.monotonic() < deadline:
        try:
            probe = _content_probe(sequence_id)
            err = None
        except Exception as e:
            err = str(e)
            time.sleep(interval)
            continue
        removed = _removed_since(probe_before, probe)
        if removed >= min_change:
            if abs(removed - cut_len_ticks) <= tol:
                return {"landed": True, "matched": True, "removedTicks": removed,
                        "probe": probe, "error": None}
            # A landed-but-wrong reading could be a probe racing the op; require
            # two consecutive mismatching reads before calling it a mismatch.
            mismatch_streak += 1
            if mismatch_streak >= 2:
                return {"landed": True, "matched": False, "removedTicks": removed,
                        "probe": probe, "error": None}
        time.sleep(interval)
    landed = removed >= min_change
    return {"landed": landed,
            "matched": landed and abs(removed - cut_len_ticks) <= tol,
            "removedTicks": removed, "probe": probe, "error": err}


@mcp.tool()
def remove_silence_segments(sequence_id: str, silence_segments: list,
                            frame_snap: bool = True, verify: bool = True,
                            dry_run: bool = False):
    """
    Cut the given segments out of the sequence and regroup (close the gaps).

    This is the PRIMARY editing primitive for transcript-based cuts. For each
    segment it sets the sequence in/out points (via the UXP API) and triggers
    Premiere's native Extract command (apostrophe, macOS key code 39). Extract
    ripple-deletes the marked range across the TARGETED video AND audio tracks
    and shifts the remaining clips left to close the gap, so cutting and
    regrouping happen together in one native, A/V-synced operation.

    PLAN FIRST: call with dry_run=True to get the exact frame-snapped cut plan
    (per-cut in/out, merged overlaps, expected removal, whether frame-snap is
    available, whether the target sequence is active) WITHOUT touching the
    timeline. Show that plan to the user, get approval, then re-run with
    dry_run=False to execute. Segments are processed from END to START so
    earlier timecodes do not shift before they are cut.

    All segments are validated and planned up front — a malformed, swapped,
    overlapping, or out-of-bounds range refuses the WHOLE batch before anything
    is cut. During execution each Extract is confirmed against the live layout
    (adaptive polling, no blind sleeps); a keystroke is only ever retried when a
    successful layout read shows the timeline did not change (an unreadable
    layout hard-stops the batch instead), and the batch also hard-stops if
    Premiere loses focus or a cut removes a different amount than planned.

    Args:
        sequence_id (str): The id of the sequence to cut.
        silence_segments (list): Segments to remove, in sequence-timeline seconds.
            Each is a dict {"start": <sec>, "end": <sec>}.
            Example: [{"start": 10.5, "end": 12.3}, {"start": 25.0, "end": 27.5}]
        frame_snap (bool): Snap each range to whole-frame boundaries before cutting
            to avoid 1-frame video/audio gaps. Defaults to True. If the sequence
            frame rate cannot be read (Premiere 2026 sometimes returns null frame
            ticks), snapping is impossible — the plan/result warns explicitly and
            the documented Close Gap recovery may be needed afterwards.
        verify (bool): After cutting, read the ACTUAL clip layout back from
            Premiere and confirm the duration changed by the expected amount, no
            gaps remain, and video/audio shifted by the same amount. Defaults to
            True.
        dry_run (bool): Plan and validate only — nothing is cut, no in/out points
            are set, the active sequence is not changed. Defaults to False.

    IMPORTANT: Treat "verified": false (or null, when verification could not run)
    as NOT confirmed. Do not report the cut as successful — inspect the
    "verification" block and follow the premiere-mcp-ops hard-stop contract.
    Premiere must be frontmost with the Timeline focused for Extract to land, and
    track targeting must include every track you intend to cut.
    """
    action = "remove_silence_segments"
    if not silence_segments:
        return {
            "action": action, "dryRun": dry_run,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": None,
            "verification": {"reason": "No segments supplied; nothing to cut."},
        }

    parsed, seg_errors = _validate_segments(silence_segments)
    if seg_errors:
        return {
            "action": action, "dryRun": dry_run,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": False if not dry_run else None,
            "refused": True,
            "segmentErrors": seg_errors,
            "nextSteps": [
                "Fix the listed segments (numeric start/end in timeline seconds, "
                "end > start) and re-run. Nothing was cut.",
            ],
        }

    # Baseline layout: frame ticks for snapping, duration for bounds checks, and
    # the before-numbers for verification. Without a readable layout we can
    # neither frame-snap nor verify, so we refuse to cut blind (dry-run still
    # reports what it could not read).
    before_summary = None
    before_probe = None
    frame_ticks = None
    layout_error = None
    try:
        before_layout = _fetch_layout(sequence_id)
        before_summary = _summarize_layout(before_layout)
        before_probe = _probe_from_layout(before_layout)
        frame_ticks = before_summary.get("frameTicks")
    except Exception as e:
        layout_error = str(e)

    if layout_error:
        return {
            "action": action, "dryRun": dry_run,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": None if dry_run else False,
            "refused": True,
            "error": f"Could not read the sequence layout: {layout_error}",
            "nextSteps": [
                "Run premiere_preflight() — the proxy or the UXP plugin is likely "
                "not connected. Cutting without a readable layout would be "
                "unverifiable and is refused.",
            ],
        }

    planned, plan_errors, plan_warnings = _plan_cuts(
        parsed, frame_ticks, before_summary.get("durationTicks"), frame_snap,
    )
    frame_snap_active = bool(frame_snap and frame_ticks)
    if frame_snap and not frame_ticks:
        fr_err = before_layout.get("frameRateError") if isinstance(before_layout, dict) else None
        plan_warnings.append(
            "Premiere/UXP returned no frame ticks"
            + (f" ({fr_err})" if fr_err else "")
            + " — ranges CANNOT be frame-snapped. Extract may leave tiny native "
            "gaps (documented Premiere 2026 failure); the bounded Close Gap "
            "recovery (close_gap_recovery) may be needed after the cut."
        )
    if plan_errors:
        return {
            "action": action, "dryRun": dry_run,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": None if dry_run else False,
            "refused": True,
            "segmentErrors": plan_errors,
            "warnings": plan_warnings,
            "nextSteps": [
                "The removal ranges do not fit this sequence. Confirm the "
                "sequence_id and that the ranges are in CURRENT timeline seconds "
                "(they shift after every applied cut), then re-run. Nothing was cut.",
            ],
        }

    expected_total_ticks = sum(c["lengthTicks"] for c in planned)
    planned_public = [
        {k: c[k] for k in ("inSeconds", "outSeconds", "lengthSeconds", "inTicks",
                           "outTicks", "lengthTicks") if k in c}
        | ({"lengthFrames": c["lengthFrames"]} if "lengthFrames" in c else {})
        | {"mergedFrom": len(c["sources"])}
        for c in planned
    ]

    if dry_run:
        active_id = _active_sequence_id()
        matches = (active_id == str(sequence_id)) if active_id else None
        duration = before_summary.get("durationTicks") or 0
        return {
            "action": action, "dryRun": True,
            "wouldCut": len(planned),
            "plannedCuts": planned_public,
            "expectedRemovedSeconds": round(expected_total_ticks / TICKS_PER_SECOND, 4),
            "durationSeconds": round(duration / TICKS_PER_SECOND, 4),
            "estimatedDurationAfterSeconds": round(
                max(duration - expected_total_ticks, 0) / TICKS_PER_SECOND, 4),
            "frameSnapAvailable": bool(frame_ticks),
            "frameSnapApplied": frame_snap_active,
            "activeSequenceMatches": matches,
            "warnings": plan_warnings,
            "nextSteps": [
                "Review the plan with the user (cuts, expected removal, warnings).",
                "After approval, re-run remove_silence_segments with the SAME "
                "segments and dry_run=False to execute.",
            ]
            + ([] if matches is not False else [
                f"NOTE: the active sequence is {active_id}, not {sequence_id}; the "
                "live run will make the target active before cutting.",
            ]),
        }

    # ---- LIVE RUN ----
    # SAFETY: the Extract keystroke lands on the ACTIVE/focused Timeline, which
    # may not be the sequence_id passed. We ALWAYS make sequence_id active first
    # (idempotent, and it focuses that Timeline). Then we confirm the id reads
    # back as the target. An unreadable active id used to fail OPEN (Extract
    # would hit whatever Timeline was focused). That is now a refuse.
    try:
        sendCommand(createCommand("setActiveSequence", {"sequenceId": sequence_id}))
        time.sleep(0.4)
    except Exception as e:
        set_active_error = str(e)
    else:
        set_active_error = None
    active_id = _active_sequence_id()
    if active_id != str(sequence_id):
        reason_active = active_id or "(unreadable)"
        extra = f" setActiveSequence error: {set_active_error}." if set_active_error else ""
        return {
            "action": action, "dryRun": False,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": False,
            "refused": True,
            "verification": {
                "verified": False,
                "reason": (
                    f"Target sequence {sequence_id} could not be confirmed active "
                    f"(active is {reason_active}).{extra} Extract would cut the "
                    "wrong timeline. Open/click the target sequence's Timeline "
                    "tab so it is active, then retry."
                ),
            },
            "nextSteps": [
                f"In Premiere, click the Timeline tab for sequence {sequence_id} "
                "so it becomes the active/focused sequence.",
                "Re-run remove_silence_segments with the same arguments.",
            ],
        }
    active_unconfirmed = False

    # Focus Premiere ONCE for the whole batch. Per-cut activation can hang while
    # Premiere is busy, so we deliberately do not re-focus per segment.
    # This must be a HARD gate: the batch marks In/Out over UXP (which answers
    # even when the window is not focused) and then Extracts with a keystroke
    # (which needs focus). If focus silently failed, the marks land and the
    # Extract does not — or lands half-applied, which is how a 20s cut once
    # removed 3357s. Refuse to start instead.
    try:
        _ensure_premiere_focused()
    except Exception as e:
        return {
            "action": action, "dryRun": False,
            "processed": 0, "succeeded": 0, "failed": 0,
            "verified": False,
            "refused": True,
            "verification": {
                "verified": False,
                "reason": (
                    f"Could not confirm Premiere is frontmost before cutting: {e} "
                    "Nothing was marked or cut; the timeline is untouched."
                ),
            },
            "nextSteps": [
                "Click Premiere's Timeline so the app is frontmost.",
                "Re-run premiere_preflight to confirm the control chain.",
                "Then re-run remove_silence_segments with the SAME segments.",
            ],
        }

    probe_before = before_probe

    succeeded = 0
    failed = 0
    skipped = 0
    aborted = None
    results = []
    expected_removed_ticks = 0
    run_warnings = list(plan_warnings)

    for idx, cut in enumerate(planned):
        in_ticks, out_ticks = cut["inTicks"], cut["outTicks"]
        cut_len = cut["lengthTicks"]
        base = {"inSeconds": cut["inSeconds"], "outSeconds": cut["outSeconds"],
                "inTicks": in_ticks, "outTicks": out_ticks}

        # Mark the range. The UXP call is idempotent, so retrying is safe.
        marked = False
        mark_err = None
        for attempt in range(3):
            try:
                sendCommand(createCommand("setSequenceInOutPoints", {
                    "sequenceId": sequence_id,
                    "inPointTicks": in_ticks,
                    "outPointTicks": out_ticks,
                }))
                marked = True
                break
            except Exception as e:
                mark_err = str(e)
                time.sleep(0.5 * (attempt + 1))
        if not marked:
            failed += 1
            results.append(base | {"success": False, "stage": "mark", "error": mark_err})
            continue  # nothing mutated; remaining (earlier) segments are unaffected

        # The keystroke goes to the frontmost app. None (System Events
        # unreadable) is as unsafe as False — stop instead of guessing.
        if _premiere_is_frontmost() is not True:
            aborted = ("Premiere frontmost state is unconfirmed — batch "
                       "stopped before this segment's Extract. Click the "
                       "Timeline tab so Premiere is frontmost.")
            skipped = len(planned) - idx
            break

        # Extract exactly once. NEVER blind-retry: an AppleScript -1712 timeout
        # can fire AFTER the key event was delivered, and a second Extract at the
        # same coordinates would cut wanted content on the already-shifted
        # timeline. A 4s poll that still shows "unchanged" is also UNKNOWN
        # (Premiere may still be applying the first Extract).
        key_err = None
        try:
            _send_key_code_fast(39)
        except Exception as e:
            key_err = str(e)

        outcome = _wait_for_extract(sequence_id, probe_before, cut_len, frame_ticks)

        if outcome["probe"] is None:
            # Layout became unreadable mid-batch: the segment's state is unknown
            # and nothing further can be verified. Hard stop per the contract.
            failed += 1
            results.append(base | {
                "success": False, "stage": "extract",
                "error": f"Layout unreadable after Extract ({outcome['error']}); "
                         f"keystroke error: {key_err or 'none'} — state UNKNOWN.",
            })
            aborted = ("Lost the layout read-back mid-batch; remaining segments "
                       "skipped. Re-run premiere_preflight and verify_sequence_layout "
                       "before continuing.")
            skipped = len(planned) - idx - 1
            break

        if not outcome["landed"]:
            # Retry is ONLY safe when the first keystroke itself failed to send
            # AND a successful layout read shows the timeline did not change.
            # A successful send + unchanged layout after the poll window may
            # mean Premiere is still applying the first Extract.
            if key_err is None:
                failed += 1
                results.append(base | {
                    "success": False, "stage": "extract",
                    "error": (
                        "The layout read back UNCHANGED after Extract. The "
                        "keystroke was sent, so a retry could double-cut; "
                        "treating this as UNKNOWN and stopping."
                    ),
                })
                aborted = (
                    "Extract did not become visible within the poll window "
                    "after a successful keystroke send. Remaining segments "
                    "skipped. Re-run verify_sequence_layout before retrying."
                )
                skipped = len(planned) - idx - 1
                break
            if _premiere_is_frontmost() is not True:
                aborted = ("Premiere frontmost state is unconfirmed — "
                           "batch stopped before retrying this segment's Extract.")
                failed += 1
                results.append(base | {"success": False, "stage": "extract",
                                       "error": "Focus unconfirmed before retry."})
                skipped = len(planned) - idx - 1
                break
            try:
                _send_key_code_fast(39)
                key_err = None
            except Exception as e:
                key_err = str(e)
            outcome = _wait_for_extract(sequence_id, probe_before, cut_len, frame_ticks)

            if outcome["probe"] is None:
                failed += 1
                results.append(base | {
                    "success": False, "stage": "extract",
                    "error": f"Layout unreadable after Extract retry "
                             f"({outcome['error']}); keystroke error: "
                             f"{key_err or 'none'} — state UNKNOWN.",
                })
                aborted = ("Lost the layout read-back mid-batch; remaining "
                           "segments skipped. Re-run premiere_preflight and "
                           "verify_sequence_layout before continuing.")
                skipped = len(planned) - idx - 1
                break

        if outcome["landed"] and outcome["matched"]:
            succeeded += 1
            expected_removed_ticks += cut_len
            probe_before = outcome["probe"]
            results.append(base | {
                "success": True,
                "measuredRemovedSeconds": round(outcome["removedTicks"] / TICKS_PER_SECOND, 4),
            })
        elif outcome["landed"]:
            # Something was removed but not the planned amount — the timeline no
            # longer matches the plan. Continuing would cut at stale coordinates.
            failed += 1
            results.append(base | {
                "success": False, "stage": "extract",
                "error": (
                    f"Extract removed {outcome['removedTicks'] / TICKS_PER_SECOND:.3f}s "
                    f"but the plan expected {cut_len / TICKS_PER_SECOND:.3f}s."
                ),
            })
            aborted = ("A cut removed a different amount than planned; remaining "
                       "segments skipped because their timecodes may no longer be "
                       "valid. Verify the sequence and re-plan the remaining ranges.")
            skipped = len(planned) - idx - 1
            break
        else:
            failed += 1
            results.append(base | {
                "success": False, "stage": "extract",
                "error": key_err or "The layout read back UNCHANGED after Extract "
                        "(keystroke likely did not reach the Timeline panel).",
            })
            # The layout was read and provably did not change for this segment;
            # later segments are earlier on the timeline and remain valid.

    out = {
        "action": action, "dryRun": False,
        "processed": len(planned),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "aborted": aborted,
        "frameSnapped": frame_snap_active,
        "activeSequenceConfirmed": not active_unconfirmed,
        "plannedCuts": planned_public,
        "results": results,
        "warnings": run_warnings,
        "verified": None,
        "verification": None,
    }

    if verify:
        verification = _verify_cut(
            sequence_id, before_summary, expected_removed_ticks, frame_ticks,
            cut_count=max(succeeded, 1),
        )
        out["verification"] = verification
        out["verified"] = verification.get("verified")
        # Surface the two facts the user explicitly cares about at the top level
        # so callers don't have to dig into the verification block.
        out["packed"] = verification.get("packed")
        out["avSynced"] = verification.get("avSynced")
        next_steps = _cut_next_steps(verification, sequence_id)
        if aborted:
            next_steps.insert(0, aborted)
        out["nextSteps"] = next_steps
    elif aborted:
        out["nextSteps"] = [aborted]

    return out


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
          before the first clip (kind, trackIndex, lane, leading, start/end,
          gapSeconds, gapFrames)
        - laneRoles: each lane classified "program" (the base bed, must be packed)
          or "overlay" (b-roll/titles/transition stingers, sparse by design)
        - packed: True when zero gaps remain on the PROGRAM bed. Overlay-lane gaps
          are counted separately (overlayGapCount) and never make this False —
          otherwise every finished sequence with stingers reads as broken.
        - allLanesPacked / allLaneGapCount: the strict every-lane view, for a bare
          timeline where any gap at all is a defect.
        - avMisalignments: PROGRAM cut junctions where video and audio do NOT line
          up within one frame (empty == frame-accurate sync)
        - videoAudioInSync: True when there are no misalignments AND the ends are
          within ~2 frames
        - warnings: real problems. notes: informational (e.g. overlay-lane gaps).
    """
    layout = _fetch_layout(sequence_id)
    summary = _summarize_layout(layout)
    video, audio = _clips_from_layout(layout)
    summary["sequenceId"] = layout.get("id")
    summary["sequenceName"] = layout.get("name")
    summary["packed"] = summary["gapCount"] == 0
    summary["allLanesPacked"] = summary["allLaneGapCount"] == 0

    ft = summary.get("frameTicks") or int(TICKS_PER_SECOND / 24)

    # Frame-accurate A/V sync: every internal cut must land on the same timecode
    # for video and audio. Judged on the PROGRAM bed only — an overlay stinger or
    # SFX deliberately starting a frame off the cut is style, not desync.
    roles = _lane_roles(video + audio, summary.get("durationTicks", 0), ft)
    pv, pa = _program_clips(video, roles), _program_clips(audio, roles)
    misalignments = _av_misalignments(pv, pa, ft) if (pv and pa) else []
    summary["avMisalignments"] = misalignments
    summary["overlayGaps"] = [g for g in summary["gaps"] if g["lane"] == "overlay"]

    skew = abs(summary["videoEndTicks"] - summary["audioEndTicks"])
    summary["videoAudioEndSkewSeconds"] = round(skew / TICKS_PER_SECOND, 4)
    summary["videoAudioInSync"] = (not misalignments) and (skew <= 2 * ft)

    warnings = []
    notes = []
    if summary["overlayGapCount"]:
        overlay_lanes = sorted({f"{g['kind']}{g['trackIndex']}" for g in summary["overlayGaps"]})
        notes.append(
            f"{summary['overlayGapCount']} gap(s) on overlay lane(s) {', '.join(overlay_lanes)} "
            "— these carry b-roll/titles/transition stingers and are sparse by design, "
            "so they are reported but not treated as defects."
        )
    if not summary["packed"]:
        leading = [g for g in summary["gaps"] if g.get("leading") and g["lane"] == "program"]
        if leading:
            warnings.append(
                f"{len(leading)} clip lane(s) do not start at 0 — there is a gap "
                "before the first clip; the sequence is not back to back."
            )
        inter = summary["gapCount"] - len(leading)
        if inter > 0:
            warnings.append(f"{inter} gap(s) between clips on the program bed — clips are not back to back.")
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
    summary["notes"] = notes
    return summary


# Key that Premiere's Sequence > Close Gap command is bound to in THIS user's
# workspace (a custom mapping — Premiere's default binds W to Ripple Trim Next
# Edit, which would be destructive). close_gap_recovery verifies content ticks
# after every press precisely because this binding cannot be confirmed from
# outside Premiere.
CLOSE_GAP_KEY = os.environ.get("PREMIERE_CLOSE_GAP_KEY", "w")


@mcp.tool()
def premiere_preflight():
    """
    One-call health check for the whole Premiere control chain. READ-ONLY.

    Run this FIRST in a session (and after any connection hiccup) instead of
    discovering problems as timeouts mid-edit. It checks, in dependency order:

    1. Proxy server reachable on PROXY_URL (via its /status endpoint).
    2. Premiere UXP plugin registered with the proxy (the "Connect" button).
    3. A project is open; the active sequence id/name.
    4. Frame ticks readable for the active sequence — when Premiere/UXP returns
       null (known Premiere 2026 failure) frame-snapping is unavailable and the
       Close Gap recovery may be needed after cuts.
    5. Premiere frontmost (Extract keystrokes land on the focused Timeline), and
       that System Events can be read at all — if it cannot, the guard that
       stops a batch typing into the wrong window cannot run, so cuts refuse.
    6. Premiere answering Apple events. Diagnostic: a -1712 here means the main
       thread is wedged (modal dialog, background render) while UXP keeps
       answering, which is why every other check can look green during a hang.

    Returns {ready, proxyRunning, pluginConnected, projectOpen, activeSequence,
    frameSnapAvailable, premiereFrontmost, appleEventsResponsive, issues,
    nextSteps}. `ready: true` means a transcript cut can proceed (dry-run it
    first regardless).
    """
    issues = []
    next_steps = []
    proxy_running = False
    plugin_connected = False
    proxy_status = None

    try:
        with urllib.request.urlopen(f"{PROXY_URL}/status", timeout=3) as resp:
            proxy_status = json.loads(resp.read().decode("utf-8"))
        proxy_running = True
    except Exception as e:
        issues.append(f"Proxy not reachable at {PROXY_URL}: {e}")
        next_steps.append("Start the proxy from the repo root: bun run premiere:proxy")

    if proxy_running:
        clients = (proxy_status or {}).get("clients") or {}
        plugin_connected = bool(clients.get(APPLICATION))
        if not plugin_connected:
            issues.append("Proxy is running but no Premiere UXP plugin is registered.")
            next_steps.append(
                "In Premiere, open the 'Premiere MCP Agent' panel (Window > "
                "Extensions if docked away) and click Connect. Load it via Adobe "
                "UXP Developer Tools from apps/premiere/adobe-mcp/uxp-plugins/premiere "
                "if it is not installed."
            )

    project_open = None
    active_sequence = None
    sequence_count = None
    frame_snap_available = None
    layout_readable = None
    if plugin_connected:
        try:
            info = sendCommand(createCommand("getProjectInfo", {}))
            payload = info.get("response", {}) if isinstance(info, dict) else {}
            project_open = bool(payload.get("hasProject"))
            sequence_count = payload.get("sequenceCount")
            if payload.get("activeSequenceId"):
                active_sequence = {
                    "id": payload.get("activeSequenceId"),
                    "name": payload.get("activeSequenceName"),
                }
        except Exception as e:
            # The plugin rejects most commands outright when no project is open
            # ("Requires an open Premiere Project") — map that to the real state
            # instead of reporting a plugin failure.
            if "Requires an open Premiere Project" in str(e):
                project_open = False
            else:
                issues.append(f"Plugin is connected but getProjectInfo failed: {e}")
                next_steps.append(
                    "Reload the UXP plugin (UXP Developer Tools > Reload) and re-run "
                    "premiere_preflight."
                )
        if project_open is False:
            issues.append("No project is open in Premiere.")
            next_steps.append("Open the target .prproj in Premiere, then re-run preflight.")
        elif project_open and not active_sequence:
            issues.append("A project is open but no sequence is active.")
            next_steps.append(
                "Double-click the target sequence in the Project panel so a "
                "Timeline is active."
            )
        if active_sequence:
            try:
                layout = _fetch_layout(active_sequence["id"])
                layout_readable = True
                frame_snap_available = bool(_frame_ticks(layout))
                if not frame_snap_available:
                    fr_err = layout.get("frameRateError")
                    issues.append(
                        "Premiere/UXP returned no frame ticks for the active "
                        "sequence"
                        + (f" ({fr_err})" if fr_err else "")
                        + " — frame-snapping is unavailable (known Premiere 2026 "
                        "failure). Cuts may leave tiny native gaps."
                    )
                    next_steps.append(
                        "Proceed only with dry_run planning first; if a cut leaves "
                        "tiny gaps, use close_gap_recovery (the documented bounded "
                        "recovery)."
                    )
            except Exception as e:
                layout_readable = False
                issues.append(
                    f"Could not read the active sequence layout: {e} — "
                    "remove_silence_segments will refuse to cut in this state."
                )
                next_steps.append(
                    "Reload the UXP plugin and re-run premiere_preflight until the "
                    "layout reads back."
                )

    premiere_frontmost = _premiere_is_frontmost()
    if premiere_frontmost is False:
        issues.append(
            "Premiere is not the frontmost application — Extract keystrokes "
            "would land elsewhere (cuts auto-focus Premiere, but keep it front "
            "during batches)."
        )
    elif premiere_frontmost is None:
        issues.append(
            "Could not read the frontmost application via System Events — the "
            "safety check that stops a batch from typing into the wrong window "
            "cannot run, so cuts will refuse to start."
        )
        next_steps.append(
            "Grant Automation + Accessibility permission to the process hosting "
            "this MCP server (System Settings > Privacy & Security), then re-run "
            "premiere_preflight."
        )

    # Apple-event health. Diagnostic only — the cut path uses LaunchServices for
    # focus and System Events for keystrokes — but a wedged main thread is worth
    # knowing about BEFORE a batch instead of discovering it as a mid-cut hang.
    apple_events_responsive = _apple_events_responsive() if plugin_connected else None
    if apple_events_responsive is False:
        issues.append(
            "Premiere is running and answering UXP, but NOT answering Apple "
            "events (-1712) — its main thread is busy or blocked, often by a "
            "modal dialog or a background render. Cutting does not depend on "
            "Apple events, but Premiere may not process keystrokes promptly."
        )
        next_steps.append(
            "Check Premiere for an open modal dialog or a running render and "
            "clear it, then re-run premiere_preflight."
        )

    ready = bool(proxy_running and plugin_connected and project_open
                 and active_sequence and layout_readable
                 and premiere_frontmost is not None)
    if ready and not issues:
        next_steps.append(
            "Ready. Plan the cut with remove_silence_segments(..., dry_run=True), "
            "review with the user, then execute."
        )

    return {
        "action": "premiere_preflight",
        "ready": ready,
        "proxyRunning": proxy_running,
        "pluginConnected": plugin_connected,
        "projectOpen": project_open,
        "sequenceCount": sequence_count,
        "activeSequence": active_sequence,
        "frameSnapAvailable": frame_snap_available,
        "premiereFrontmost": premiere_frontmost,
        "appleEventsResponsive": apple_events_responsive,
        "proxyStatus": proxy_status,
        "issues": issues,
        "nextSteps": next_steps,
    }


@mcp.tool()
def close_gap_recovery(sequence_id: str, max_passes: int = 3,
                       max_gap_seconds: float = 0.5):
    """
    Bounded, verified Sequence > Close Gap recovery for tiny native Extract gaps.

    This automates the ONLY documented gap recovery in this workspace: when
    Premiere/UXP reported no frame ticks, `remove_silence_segments` could not
    frame-snap, and Extract left tiny native gaps (typically 0.03-0.07s) with
    `packed: false`. It presses the workspace's Close Gap key (default "w",
    override with PREMIERE_CLOSE_GAP_KEY) ONE pass at a time and re-reads the
    layout after every press, exactly as the premiere-mcp-ops skill requires.

    It REFUSES to run unless the preconditions hold:
    - the target sequence is (or can be made) the active sequence,
    - every remaining gap is smaller than max_gap_seconds (tiny native gaps,
      not user-created timeline holes),
    - there are no A/V misalignments (those need an undo, not gap closing).

    Safety gate: Close Gap moves clips without changing their content. If a
    press changes total clip CONTENT (which would mean the key is bound to
    something destructive like Ripple Trim), the tool hard-stops and tells you
    to undo. It never auto-undoes.

    Keep the result only when it returns clean=true (packed, videoAudioInSync,
    gapCount 0, no warnings). Otherwise follow nextSteps (undo to the previous
    clean baseline) per the documented contract.

    Args:
        sequence_id (str): The sequence to pack.
        max_passes (int): Maximum Close Gap presses before giving up. Default 3.
        max_gap_seconds (float): Refuse if any gap is larger than this. Default 0.5.
    """
    action = "close_gap_recovery"

    # Same active-sequence guard as the cut path: the keystroke lands on the
    # focused Timeline, so the target must provably be the active sequence.
    try:
        sendCommand(createCommand("setActiveSequence", {"sequenceId": sequence_id}))
        time.sleep(0.4)
    except Exception as e:
        set_active_error = str(e)
    else:
        set_active_error = None
    active_id = _active_sequence_id()
    if active_id != str(sequence_id):
        reason_active = active_id or "(unreadable)"
        extra = f" setActiveSequence error: {set_active_error}." if set_active_error else ""
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": (
                f"Target sequence {sequence_id} could not be confirmed active "
                f"(active is {reason_active}).{extra}"
            ),
            "nextSteps": [
                f"Click the Timeline tab for sequence {sequence_id} so it is "
                "active, then re-run close_gap_recovery.",
            ],
        }

    try:
        baseline = verify_sequence_layout(sequence_id)
    except Exception as e:
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": f"Could not read the sequence layout: {e}",
            "nextSteps": ["Run premiere_preflight() and fix the connection first."],
        }

    if baseline.get("packed") and baseline.get("videoAudioInSync"):
        return {
            "action": action, "clean": True, "passes": 0,
            "reason": "Sequence is already packed and in sync — nothing to do.",
            "layout": baseline,
        }
    if baseline.get("gapCount") == 0:
        # Packed but not in sync (e.g. end-skew only): there is no gap for
        # Close Gap to close, so pressing the key could only do harm.
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": (
                "Zero gaps in the sequence — Close Gap does not apply. The "
                "remaining problem (e.g. video/audio end skew) needs a different "
                "fix; see the layout warnings."
            ),
            "layout": baseline,
            "nextSteps": [
                "Inspect the layout warnings; an end skew usually means a track "
                "was not targeted during a cut — undo that cut and re-run it "
                "with all tracks targeted.",
            ],
        }
    if baseline.get("avMisalignments"):
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": "A/V misalignments present — Close Gap cannot fix a desync.",
            "layout": baseline,
            "nextSteps": [
                "Undo the last Extract (Cmd+Z), confirm Linked Selection and track "
                "targeting, and re-run the cut. Do not close gaps while V/A are "
                "misaligned.",
            ],
        }
    if baseline.get("overlayGapCount"):
        # Overlay lanes mean this is a LAYERED sequence (b-roll, titles, stingers),
        # not the bare post-Extract timeline this recovery was written for. Close
        # Gap acts on the timeline as a whole, so a pass here could slide overlays
        # off the frames they were placed on.
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": (
                "Sequence has overlay lanes with intentional gaps (b-roll, titles or "
                "transition stingers). close_gap_recovery only handles the bare "
                "post-Extract timeline; a Close Gap pass here could shift overlays."
            ),
            "overlayGaps": baseline.get("overlayGaps", []),
            "nextSteps": ["Close any program-bed gap manually in Premiere on this layered sequence."],
        }
    oversized = [g for g in baseline.get("gaps", [])
                 if g.get("lane") == "program" and g.get("gapSeconds", 0) > max_gap_seconds]
    if oversized:
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": (
                f"{len(oversized)} gap(s) exceed max_gap_seconds={max_gap_seconds}; "
                "these are not tiny native Extract gaps, so the documented recovery "
                "does not apply."
            ),
            "oversizedGaps": oversized,
            "nextSteps": [
                "Inspect the listed gaps manually; close_gap_recovery only handles "
                "tiny Extract-created gaps.",
            ],
        }

    content_before = (baseline.get("videoContentTicks", 0),
                      baseline.get("audioContentTicks", 0))
    ft = baseline.get("frameTicks") or int(TICKS_PER_SECOND / 24)
    content_tol = ft // 2

    # Bring Premiere frontmost once for the whole recovery (like the cut batch):
    # the Close Gap keystroke goes to the focused app, and W is bound to Ripple
    # Trim in a default workspace — pressing it blind into the wrong window, or
    # into an unfocused Premiere, is not a risk worth taking. Refuse instead.
    try:
        _ensure_premiere_focused()
    except Exception as e:
        return {
            "action": action, "clean": False, "passes": 0, "refused": True,
            "reason": (
                f"Could not confirm Premiere is frontmost: {e} No key was "
                "pressed; the timeline is untouched."
            ),
            "layout": baseline,
            "nextSteps": [
                "Click Premiere's Timeline so the app is frontmost, then re-run "
                "close_gap_recovery.",
            ],
        }

    def _undo_steps(n: int) -> list:
        if n == 0:
            return [
                "Do NOT undo — no press changed the timeline.",
                f"Re-run verify_sequence_layout('{sequence_id}') to confirm the baseline.",
            ]
        return [
            f"Undo {n} time(s) (Cmd+Z) — one per press that actually changed the "
            "timeline — back to the pre-recovery state.",
            f"Then re-run verify_sequence_layout('{sequence_id}') to confirm the baseline.",
        ]

    passes = 0
    effective_passes = 0  # presses that verifiably changed the layout (undo units)
    history = []
    prev_state = (baseline.get("gapCount"), baseline.get("durationTicks"),
                  content_before[0], content_before[1])
    summary = baseline
    for _ in range(max_passes):
        if _premiere_is_frontmost() is not True:
            return {
                "action": action, "clean": False, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": "Premiere frontmost state is unconfirmed — stopped before the next press.",
                "layout": summary, "history": history,
                "nextSteps": [
                    "Click Premiere's Timeline tab so the app is frontmost, "
                    "then re-run close_gap_recovery."
                ]
                + _undo_steps(effective_passes)[:1],
            }
        # ONE press, no retry: an AppleScript -1712 timeout can fire after the
        # key event was delivered, so a retry could press twice in one pass.
        # A keystroke error is resolved by the layout read below, not a re-send.
        key_err = None
        try:
            _send_keystroke_fast(CLOSE_GAP_KEY)
        except Exception as e:
            key_err = str(e)
        passes += 1
        time.sleep(0.6)

        try:
            summary = verify_sequence_layout(sequence_id)
        except Exception as e:
            return {
                "action": action, "clean": False, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": f"Layout unreadable after pass {passes}: {e} — state "
                          "unverified, treat as NOT clean.",
                "history": history,
                "nextSteps": [
                    "Re-run verify_sequence_layout once the connection is back "
                    "and compare against the pre-recovery gap list before "
                    "deciding whether to undo.",
                ],
            }
        state = (summary.get("gapCount"), summary.get("durationTicks"),
                 summary.get("videoContentTicks", 0), summary.get("audioContentTicks", 0))
        changed = state != prev_state
        if changed:
            effective_passes += 1
        history.append({
            "pass": passes,
            "changedTimeline": changed,
            "keystrokeError": key_err,
            "gapCount": summary.get("gapCount"),
            "packed": summary.get("packed"),
            "videoAudioInSync": summary.get("videoAudioInSync"),
            "warnings": summary.get("warnings"),
        })

        content_after = (summary.get("videoContentTicks", 0),
                         summary.get("audioContentTicks", 0))
        if (abs(content_after[0] - content_before[0]) > content_tol
                or abs(content_after[1] - content_before[1]) > content_tol):
            return {
                "action": action, "clean": False, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": (
                    "Clip CONTENT changed after the keystroke — the key is bound to "
                    "something destructive (not Close Gap). HARD STOP."
                ),
                "layout": summary, "history": history,
                "nextSteps": _undo_steps(effective_passes)[:1] + [
                    "Verify the workspace keyboard mapping: Sequence > Close Gap "
                    f"must be bound to '{CLOSE_GAP_KEY}' (or set PREMIERE_CLOSE_GAP_KEY).",
                    f"Re-run verify_sequence_layout('{sequence_id}') afterwards.",
                ],
            }

        if (summary.get("packed") and summary.get("videoAudioInSync")
                and summary.get("gapCount") == 0 and not summary.get("warnings")):
            return {
                "action": action, "clean": True, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": f"Sequence verified clean after {passes} Close Gap pass(es).",
                "layout": summary, "history": history,
            }

        if not changed:
            return {
                "action": action, "clean": False, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": (
                    f"Pass {passes} did not change the timeline at all"
                    + (f" (keystroke error: {key_err})" if key_err else "")
                    + " — the press likely never reached the Timeline panel. Stopping."
                ),
                "layout": summary, "history": history,
                "nextSteps": _undo_steps(effective_passes) + [
                    "Check that the Timeline panel is focused and the Close Gap "
                    f"key mapping ('{CLOSE_GAP_KEY}') is correct, then re-run.",
                ],
            }

        if (summary.get("gapCount") is not None and prev_state[0] is not None
                and summary["gapCount"] >= prev_state[0]):
            return {
                "action": action, "clean": False, "passes": passes,
                "effectivePasses": effective_passes,
                "reason": (
                    f"Pass {passes} did not reduce the gap count "
                    f"({prev_state[0]} -> {summary['gapCount']}) — no progress, stopping."
                ),
                "layout": summary, "history": history,
                "nextSteps": _undo_steps(effective_passes)
                + ["Report the residual gaps for manual packing."],
            }
        prev_state = state

    return {
        "action": action, "clean": False, "passes": passes,
        "effectivePasses": effective_passes,
        "reason": f"Not clean after {passes} pass(es) (bounded recovery exhausted).",
        "layout": summary, "history": history,
        "nextSteps": _undo_steps(effective_passes)
        + ["Stop here, per the premiere-mcp-ops contract."],
    }


@mcp.resource("config://get_instructions")
def get_instructions() -> str:
    """Read this first! Returns information and instructions on how to use Premiere Pro and this API"""

    return f"""
    You are a Premiere Pro and video expert. This workspace edits the LIVE active
    Premiere Pro sequence through Adobe MCP. The live sequence is the source of
    truth — never assume an edit landed just because a tool returned success;
    re-read the layout with verify_sequence_layout.

    Rules to follow:

    1. Think deeply about how to solve the task.
    2. Always check your work against the actual sequence layout — not the success flag.
    3. Read the API call docstrings so you understand the requirements and arguments.
    4. When building from scratch: add clips first, then effects, then transitions.
    5. Keep transitions short (<= 2 seconds), and there must be no gap between clips
       (or the transition may not work).

    ====================================================================
    PRIMARY WORKFLOW: TRANSCRIPT / SILENCE REMOVAL (the supported path)
    ====================================================================

    Step 0 — preflight. Run premiere_preflight() first: it confirms the proxy,
    the UXP plugin connection, the open project, the active sequence, and
    whether frame-snapping is available — in one read-only call, instead of
    discovering a dead link as a timeout mid-edit.

    Step 1 — plan (nothing is cut). Removing dead filler is done with ONE tool:

        remove_silence_segments(sequence_id, silence_segments, dry_run=True)

    The dry run validates every range, frame-snaps, merges overlaps, and returns
    the exact plannedCuts + expectedRemovedSeconds WITHOUT touching the timeline.
    Show the plan to the user and get approval.

    Step 2 — execute. Re-run with dry_run=False. It is the only safe cut
    primitive. For each planned range it:
    - asserts the target sequence IS the active/focused timeline (it calls
      setActiveSequence first; if it cannot confirm, it REFUSES and returns
      nextSteps, because the cut keystroke lands on whatever timeline is focused),
    - frame-snaps the range so video and audio cut on the exact same frame,
    - removes the range with Premiere's native Extract (ripple-delete), which
      closes the gap in the SAME A/V-synced op (this is the "regroup" — there is
      no separate gap-closing step in the happy path),
    - processes ranges end -> start so earlier timecodes stay valid,
    - confirms each Extract against the live layout (a keystroke is only retried
      when the timeline provably did not change),
    - then auto-verifies the result.

    After it runs, read the top-level flags:
    - verified  — true only when the right amount was removed, NO new gap appeared,
                  and every cut lands on the same frame for video and audio.
    - packed    — true when the PROGRAM bed is back to back (zero gaps on
                  program lanes, including a leading gap). Overlay-lane gaps
                  (b-roll, titles, stingers) are reported separately and do
                  not fail packed. allLanesPacked is the strict every-lane view.
    - avSynced  — true when every PROGRAM cut lands on the same timecode.
    - nextSteps — plain instructions for the user when something needs attention.
    Treat verified: false / null as NOT confirmed. Re-inspect with
    verify_sequence_layout. You can also capture get_sequence_frame_image at a cut
    junction to SEE that the right frame is present and nothing is duplicated/dropped.

    Recovery — ONLY when frame ticks were unavailable and Extract left tiny
    native gaps (packed: false, gaps ~0.03-0.07s): close_gap_recovery(sequence_id)
    runs the documented bounded Sequence > Close Gap recovery — one press at a
    time, verified after every press, hard-stopping if clip content changes.
    Keep the edit only when it returns clean: true; otherwise follow its
    nextSteps (undo to the previous clean baseline).

    DO NOT use the following for transcript cuts — they desync linked video/audio
    and/or leave gaps, and they carry an UNSAFE docstring prefix:
      split_video_clip, split_audio_clip, split_clip_at_time, batch_split_clips,
      trim_video_clip, trim_audio_clip,
      remove_video_clip_range, remove_linked_clip_range, remove_clips,
      delete_clip, cut_at_playhead, ripple_delete,
      set_clip_position (can stretch clips; never use it to close gaps),
      send_keystroke, delete_selected, move_clip.
    Never close a residual gap with split/trim/delete/set_clip_position. If a gap
    remains after a cut and the close_gap_recovery preconditions do not hold,
    STOP and report it for manual packing with its location from the
    verification block.

    Do not create alternate sequences, rendered MP4 assemblies, FFmpeg proxy cuts,
    or API-built replacement timelines unless the user explicitly asks.

    AVAILABLE TOOLS:

    Preflight & verification (use these to confirm every edit):
    - premiere_preflight - one-call health check: proxy, plugin, project, active
      sequence, frame-snap availability (read-only; run it first)
    - verify_sequence_layout - per-lane gaps, packed, avMisalignments, end-skew, warnings
    - get_sequence_frame_image - return the frame at a timestamp as an inline image
      (visual cut-junction check; read-only)
    - get_full_project_data, get_project_info, get_sequence_settings, get_clip_info

    Transcript editing (the supported cut path):
    - remove_silence_segments - the ONLY safe cut tool (dry_run plan + Extract +
      frame-snap + verify)
    - close_gap_recovery - bounded, verified Close Gap recovery for tiny native
      Extract gaps (the only allowed gap fix)
    - import/export transcript helpers (premiere_* tools)

    Project Management:
    - create_project, open_project, save_project, save_project_as

    Sequence Management:
    - create_sequence_from_media, set_active_sequence

    Media & Timeline:
    - import_media - import files into project
    - add_media_to_sequence - add clips to timeline

    Effects & Transitions:
    - add_black_and_white_effect, add_gaussian_blur_effect, add_tint_effect, add_motion_blur_effect
    - append_video_transition - add transitions between clips
    - set_video_clip_properties - opacity and blend mode
    - premiere_apply_lumetri_correction, premiere_clean_audio_pipeline (manual-finish helpers)

    Audio:
    - set_audio_track_mute - mute/unmute audio tracks
    - set_video_clip_disabled, set_audio_clip_disabled - disable clips non-destructively

    Markers:
    - add_marker, get_markers, remove_marker

    Playhead Control:
    - get_player_position, set_player_position

    Export:
    - export_frame - write a single frame to disk as PNG (returns the path)

    GENERAL TIPS:

    Audio and Video clips live on separate Audio / Video tracks, accessed by index.
    When a video clip contains audio, the audio is placed on a separate audio track.

    To remove unwanted material from a transcript edit, use remove_silence_segments.
    To hide material without cutting, use set_video_clip_disabled / set_audio_clip_disabled
    (disabled clips don't play but can be re-enabled later) — this leaves the layout
    intact and is safe.

    For a transition between two clips, the clips must be on the same track with no
    gap between them; place the transition on the first clip.

    Video clips with a higher track index overlap and hide lower-index clips.
    Images added to a sequence default to a 5-second duration.

    TIME FORMAT:
    - All time values in the API use seconds (float).
    - Internally Premiere uses ticks (254016000000 ticks per second).
    - The API handles the conversion automatically.

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

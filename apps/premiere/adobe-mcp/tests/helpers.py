"""Shared layout fixtures for Premiere verification tests."""

from adobe_mcp.premiere.constants import TICKS_PER_SECOND


def ticks(seconds: float) -> int:
    return int(seconds * TICKS_PER_SECOND)


def clip(start_s: float, end_s: float, index: int = 0) -> dict:
    return {
        "startTimeTicks": ticks(start_s),
        "endTimeTicks": ticks(end_s),
        "index": index,
    }


def make_layout(video_tracks, audio_tracks, fps: float = 24.0, ticks_per_frame=None):
    """Build a getSequenceLayout-shaped payload.

    Each track is a list of (start_s, end_s) pairs.
    """
    if ticks_per_frame is None and fps:
        ticks_per_frame = str(int(round(TICKS_PER_SECOND / fps)))
    return {
        "id": "seq-test",
        "name": "test",
        "frameRateValue": fps,
        "ticksPerFrame": ticks_per_frame,
        "videoTracks": [
            {
                "index": i,
                "tracks": [clip(s, e, j) for j, (s, e) in enumerate(track)],
            }
            for i, track in enumerate(video_tracks)
        ],
        "audioTracks": [
            {
                "index": i,
                "tracks": [clip(s, e, j) for j, (s, e) in enumerate(track)],
            }
            for i, track in enumerate(audio_tracks)
        ],
    }

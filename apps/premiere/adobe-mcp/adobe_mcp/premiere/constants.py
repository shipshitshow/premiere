"""Shared Premiere timing constants.

Premiere stores every timeline position as an integer tick count.
This value is stable across Premiere versions.
"""

# Premiere uses 254016000000 ticks per second internally.
TICKS_PER_SECOND = 254016000000

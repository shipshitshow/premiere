# 2026-06-23 Premiere Loop Cut

## Result

Edited the active Premiere sequence `260623 - video`
(`99e5f898-98cf-4484-8be9-4d9ce8d1029f`) into the "How to Build AI Agent Loops
with Claude & Codex" cut.

Final verified state:

- Duration: `900.2687s` (`15:00.27`)
- Clips: `6` video / `6` audio
- `packed: true`
- `videoAudioInSync: true`
- `gapCount: 0`
- `warnings: []`

Project save returned `SUCCESS`.

## Source Ranges Kept

- `330.96-432.15`
- `508.74-617.68`
- `876.66-1132.44`
- `1213.92-1400.16`
- `1562.46-1767.61`
- `2880.69-2923.80`

The original plan used `431.85` as the end of the first keep, but that cuts
before the transcript word "loop." The verified edit uses `432.15` so the full
sentence lands before the cut.

## Recovery Details

Bridge/proxy was healthy at `localhost:3001` with one Premiere client connected.
The active sequence was correct, but `getSequenceLayout` returned
`frameRateValue: null` and `ticksPerFrame: null`, so `frame_snap=True` could not
snap ranges before Extract.

`remove_silence_segments` removed the correct material, but some cuts left tiny
native gaps and failed `packed` verification. The safe recovery was native
Premiere **Sequence > Close Gap** (`W` in this workspace), followed by
`verify_sequence_layout` after each press.

Verified recovery counts:

- `432.15-508.74` required two `W` passes, then verified clean.
- `0.0-330.96` required one `W` pass, then verified clean.

If this recurs, do not use `set_clip_position`, split, trim, or delete fallback
APIs. Use bounded native Close Gap passes only when the active sequence is still
correct and the residual gaps are tiny Extract-created gaps; otherwise undo back
to the previous clean baseline and stop.

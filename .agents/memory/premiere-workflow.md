---
last_verified: 2026-06-23
---

# Premiere Workflow Memory

This repo exists to edit inside Adobe Premiere Pro through Adobe MCP.

## Source Of Truth

The live Premiere sequence is the source of truth. Do not replace it with a
Python-rendered assembly, proxy timeline, or generated alternate sequence unless
the user explicitly asks for that path.

## Active Workspace

- Active app: `apps/premiere`
- MCP server and UXP bridge: `apps/premiere/adobe-mcp`
- Legacy ExtendScripts (quarantined, unused): `apps/premiere/scripts/legacy-extendscript`
- Repo workflow skills: `apps/premiere/skills`
- The old self-editing Python app has been removed from the working tree.

## Cutting Contract

- Use `remove_silence_segments` for transcript-based removals.
- Provide removal ranges in source timeline seconds.
- The tool processes cuts end-to-start and cuts with Premiere's **Extract**
  (apostrophe, macOS key code 39) — a ripple-delete that removes the in/out range
  across targeted tracks AND closes the gap in the same A/V-synced native op.
  This is the "regroup" step; no separate gap-closing call is needed or allowed.
- The tool frame-snaps removal ranges (`frame_snap=True`) to avoid 1-frame V/A
  gaps, reads the sequence before and after, and returns top-level `verified`,
  `packed` (fully back to back), `avSynced` (every cut frame-aligned across V/A),
  and `nextSteps`, plus a `verification` block (expected vs actual removed seconds
  measured on clip content, `newGapsIntroduced`, `residualGaps`,
  `avMisalignments`).
- Before cutting it makes the target sequence active and confirms it; if it can't,
  it refuses (Extract would hit the focused — possibly wrong — Timeline) and
  returns `nextSteps`.
- The A/V check flags any cut where video and audio diverge by ≥1 frame (only
  sub-frame rounding is tolerated) — the exact "audio drifted a frame" failure.
- Treat `verified: false` or `verified: null` as NOT confirmed. Re-inspect with
  `verify_sequence_layout` and report the real state; never claim success from the
  MCP flag alone.

## Premiere 2026 Close Gap Recovery

Observed on the 2026-06-23 livestream cut: Premiere/UXP returned
`frameRateValue: null` and `ticksPerFrame: null`, so `frame_snap=True` could not
snap ranges before Extract. Extract still removed the right material, but some
cuts left tiny native gaps (roughly 0.03-0.07s) that verification correctly
reported as `packed: false`.

When this exact condition happens, the verified-safe recovery is Premiere's
native **Sequence > Close Gap** command (`W` in this workspace), followed by
`verify_sequence_layout` after every press. This is a native Premiere pack step,
not `set_clip_position`, split, trim, or API clip mutation.

Use it only under these constraints:

- `remove_silence_segments` actually changed the target sequence.
- The active sequence id/name is still the requested sequence.
- The residual gaps are tiny native Extract gaps, not arbitrary user-created
  timeline holes.
- Press `W` one pass at a time, then re-run `verify_sequence_layout`.
- Keep the cut only when `packed: true`, `videoAudioInSync: true`,
  `gapCount: 0`, and `warnings: []`.
- If A/V still fails after bounded Close Gap passes, undo back to the previous
  clean baseline and stop.

For the 2026-06-23 "Claude & Codex loops" edit specifically, the transcript
boundary `431.85-508.74` cut before the word "loop." and produced a mismatch.
Use `432.15-508.74` instead; it kept the full sentence and verified clean after
two native Close Gap passes. The lead cut `0.0-330.96` verified clean after one
native Close Gap pass.

## Verification + Effects Tools

- `verify_sequence_layout(sequence_id)` — clip counts, duration, residual gaps
  (per lane, incl. a leading gap before the first clip), `avMisalignments`,
  `videoAudioInSync`, and `warnings` from the live sequence. Use after any edit.
- `premiere_get_sequence_layout(sequence_id)` — focused single-sequence layout +
  frame rate (lighter than full project data).
- `premiere_apply_lumetri_correction(...)` — UXP-scriptable Lumetri color; sets
  the params you pass (unknown names are skipped and reported). Does NOT press the
  Lumetri "Auto" button (no API) — that stays manual.
- `premiere_clean_audio_pipeline(...)` — adds DeNoise/DeReverb across audio clips
  (fuzzy-matched against live effect names). Reversible; not "Enhance Speech"
  (no API). Verify by ear.

## Audio Polish Preset

The user's normal dialogue cleanup is a track-level Audio Track Mixer insert
chain, applied to the dialogue track after the cut is assembled:

1. Parametric EQ
2. DeNoise — Amount `20.0%`
3. DeReverb — Amount `20.0%`
4. Vocal Enhancer — Mode `Low Tone`

Observed Parametric EQ setting from the mixer UI: `Low Shelf Frequency` around
`110.39 Hz`.

Current MCP support is close but not complete: `premiere_clean_audio_pipeline`
can apply DeNoise/DeReverb as clip-level effects, and `premiere_add_effect` can
add audio effects to clips. It does not yet control Audio Track Mixer inserts,
set track-level audio effect parameters, or apply Premiere's speech enhancement
UI. Until those track-mixer controls are exposed, do not claim this house audio
preset was fully applied by automation; either have the user do the mixer insert
chain manually or add/verify a UXP command that can target track effects and read
the resulting mixer state back.

## Hard Stops

Stop and report status if:

- the active sequence is not the requested sequence
- Premiere focus or keyboard automation is uncertain
- a cut reports success but the timeline layout is unchanged
- a fallback would use unsafe split/delete/trim APIs
- a fallback would create a new timeline, rendered file, or replacement assembly

## Unsafe For This Workflow

- `split_video_clip`
- `split_audio_clip`
- `remove_linked_clip_range`
- `batch_split_clips`
- `cut_at_playhead`
- `trim_video_clip`
- `trim_audio_clip`
- `set_clip_position`

---
name: premiere-mcp-ops
description: Safely operate this repo's adobe-premiere-mcp workflow. Use when the user wants to verify the Premiere bridge, execute transcript-based cuts, recover from partial failures, or work directly against the active Premiere sequence.
---

# Premiere MCP Ops

Use this skill for the fragile, repo-specific Premiere control path.

## Preconditions

Before any cut execution, confirm:

- proxy server is running on `localhost:3001`
- Premiere is connected to the proxy
- the active sequence exists
- Premiere is the frontmost window

If MCP tools are not exposed in the session, say that plainly. Do not pretend the edit was applied.

## Cutting Rules

- Use `remove_silence_segments` only for transcript-based removal ranges.
- Do not use split/delete combinations that can desync video and audio.
- Provide removal segments in source timeline seconds.
- The tool processes end-to-start and cuts with Premiere's **Extract**
  (apostrophe, macOS key code 39): a ripple-delete that removes the in/out range
  across targeted tracks AND closes the gap in the same A/V-synced native op. The
  "regroup" normally happens inside each Extract. If Premiere/UXP cannot provide
  frame ticks and verification reports only tiny native Extract gaps, use the
  bounded native Close Gap recovery in the Gap Handling section.
- The tool frame-snaps ranges (`frame_snap=True`) to avoid 1-frame V/A gaps and
  runs verification (`verify=True`) by reading the sequence before and after.
- Before cutting, the tool asserts the target `sequence_id` IS the active/focused
  sequence (it tries `setActiveSequence` first). If it cannot confirm that, it
  REFUSES to cut and returns `verified: false` with `nextSteps` — because the
  Extract keystroke lands on whatever Timeline is focused, not necessarily the id
  you passed. Follow the `nextSteps` (click the right Timeline tab, retry).
- Cut only the existing sequence requested by the user. Do not create alternate
  sequences, rendered assemblies, proxy files, or API-built replacement timelines
  unless the user explicitly asks for that.
- Read the tool's `verified` flag and `verification` block. Treat `verified:
  false` or `verified: null` as NOT confirmed — the cut is untrusted until the
  actual clip layout confirms it (`verify_sequence_layout`, plus clip-level
  inspection if needed).
- If the tool reports success but the target sequence did not change, stop and
  report a Premiere focus / keyboard automation problem. Do not invent a fallback
  edit strategy inside the live project.
- Do not use `set_clip_position` to close gaps. It can stretch/expand clips rather
  than move them safely.
- If a residual gap is reported after a cut (Extract did not regroup, e.g. because
  a track was not targeted), go to Gap Handling. Use only the documented native
  Close Gap recovery when its constraints are met; otherwise stop and report the
  exact residual gap. Do not close it with `set_clip_position`, split, trim, or
  delete fallback APIs.

Unsafe tools for this workflow (all carry an `UNSAFE` docstring prefix in the
server; `cut_and_ripple_delete_at_times` has been retired and is not registered):

- `split_video_clip`
- `split_audio_clip`
- `remove_linked_clip_range`
- `remove_video_clip_range`
- `batch_split_clips`
- `cut_at_playhead`
- `ripple_delete`
- `trim_video_clip`
- `trim_audio_clip`
- `set_clip_position`

## Verification Contract

`remove_silence_segments` now verifies itself. Top-level it returns:

- `verified` — true only when the right amount was removed, NO new gaps appeared,
  and every cut lands on the same frame for video and audio.
- `packed` — true when the whole sequence is back to back (zero gaps on any lane,
  including a leading gap before the first clip).
- `avSynced` — true when video and audio cut at the same timecode everywhere
  (frame-accurate). This is the "no frame missing / audio in sync" check.
- `nextSteps` — plain instructions for the user: what to do next, then re-validate.
- `verification` — the detail block: expected vs actual removed seconds (measured
  on per-kind clip CONTENT, so an untouched longer track can't mask the cut),
  `newGapsIntroduced`, `residualGaps`, `avMisalignments` (each cut point where V/A
  diverge by ≥1 frame, with seconds + offset), and `warnings`.

It is built on `verify_sequence_layout`, which you can also call standalone.
Verification is a guardrail, not a license to trust the success flag.

For a visual confirmation on top of the numbers, `get_sequence_frame_image(sequence_id,
seconds)` returns the frame at a timestamp as an inline image (read-only — it does
not touch the timeline). Capture it at a cut junction to see that the right content
is on screen and nothing is duplicated or dropped. It complements, and does not
replace, the numeric `verified`/`packed`/`avSynced` checks.

The A/V check tolerates only SUB-frame rounding (half a frame). A full one-frame
drift between video and audio is reported as a misalignment — this is the exact
"audio drifted a frame" failure, and it fails `verified`/`avSynced`.

After each cut batch:

1. Read `verified`, `packed`, `avSynced`. All three true = back to back, in sync,
   right amount removed.
2. Treat `verified: false`/`null` as NOT confirmed. Read `nextSteps` and the
   `warnings`; re-inspect with `verify_sequence_layout` if anything is uncertain.
3. Confirm the target sequence name/id is still the one the user requested.
4. Confirm clip count, clip starts/ends, or sequence duration actually changed.
5. If the tool returned success but the target sequence layout is unchanged, treat
   the operation as failed.
6. Report the verified state in plain terms before continuing.

Do not trust MCP success responses alone.

## Audio Polish Workflow

For this user's livestream/dialogue edits, the preferred audio polish is a
track-level Audio Track Mixer insert chain on the dialogue track, not only
clip-level cleanup:

1. Parametric EQ
2. DeNoise — Amount `20.0%`
3. DeReverb — Amount `20.0%`
4. Vocal Enhancer — Mode `Low Tone`

Observed mixer parameter: Parametric EQ `Low Shelf Frequency` around `110.39 Hz`.

Current automation limits:

- `premiere_clean_audio_pipeline` applies DeNoise/DeReverb across audio clips.
- `premiere_add_effect` can add audio effects to individual audio clips.
- The current MCP tool surface does not safely control Audio Track Mixer insert
  slots, track-level effect parameters, Vocal Enhancer mode, or Premiere's speech
  enhancement UI.

If asked to apply the "proper audio edit," first check whether new track-mixer
tools are available. If they are not, say that only the clip-level subset can be
automated and ask the user to do the Audio Track Mixer preset manually, or extend
the UXP bridge before claiming the full preset is applied. Always verify by ear.

## Gap Handling

Extract (the cut command) closes each removed range's gap in the same op, so a
correct cut leaves no gap — that is the "regroup". If the `verification` block
still reports a residual gap, something went wrong (e.g. a track was not targeted,
or focus/command mapping failed).

- Do not close gaps with `set_clip_position`; it can stretch/expand clips.
- Do not close gaps with split/trim/delete fallback APIs.
- Only close gaps if there is a documented, verified-safe Premiere workflow for
  the current project state.
- If a residual gap is reported and no safe gap-closing method is verified, stop
  and tell the user: "Cuts landed but verified packing did not complete," and
  give the exact gap location from the `verification` block.

### Documented Native Close Gap Recovery

For Premiere 2026 runs where `getSequenceLayout` returns `frameRateValue: null`
and `ticksPerFrame: null`, `frame_snap=True` cannot snap before Extract. In that
state, `remove_silence_segments` may remove the right duration but leave tiny
native gaps (about 0.03-0.07s) and `packed: false`.

The verified recovery is Premiere's own **Sequence > Close Gap** command (`W` in
this workspace), not any lower-level clip mutation. Use it only when:

- `remove_silence_segments` actually changed the requested active sequence.
- The residual gaps are tiny gaps introduced by native Extract.
- You press `W` one pass at a time and re-run `verify_sequence_layout` after each
  pass.
- You keep the cut only when `packed: true`, `videoAudioInSync: true`,
  `gapCount: 0`, and `warnings: []`.
- If those flags do not all verify after bounded Close Gap passes, undo back to
  the previous clean baseline and stop.

Known 2026-06-23 livestream note: the planned `431.85-508.74` removal cuts before
the word "loop." and produces a fractional-frame mismatch. Use
`432.15-508.74`; it verified clean after two native Close Gap passes. The lead
cut `0.0-330.96` verified clean after one native Close Gap pass.

## Never Create Unless Explicitly Asked

Do not create:

- alternate edit sequences
- duplicate target sequences
- rendered MP4 assemblies
- FFmpeg proxy cuts
- API-built replacement timelines
- temporary media intended to replace the Premiere timeline

If a recovery path requires any of the above, stop and ask the user first.

## Hard Stop Conditions

Stop immediately if any of these happen:

- The active sequence is not the sequence the user named.
- `remove_silence_segments` reports success but the target sequence did not change.
- AppleScript / keyboard automation is denied, times out, or appears to hit the
  wrong Premiere panel.
- A proposed fallback would use an unsafe tool listed above.
- A proposed fallback would create a new timeline or rendered file.
- A verification step shows clips stretched, desynced, duplicated unexpectedly, or
  otherwise changed outside the approved removal ranges.

When stopped, give the user the exact sequence name/id, what changed, what did not
change, and the next manual action needed.

## Recovery

If the connection drops or cuts partially apply:

1. Re-check proxy connectivity.
2. Reconnect the UXP plugin if needed.
3. Inspect project/sequence state.
4. Determine which removal ranges are still pending.
5. Resume with only the remaining ranges.

If a fallback would require creating a new sequence, rendering a cut, cloning
clips manually, or using lower-level clip mutation APIs, do not proceed. Ask the
user or stop with a clear status.

## Collaboration Rules

- Planning and execution are separate steps.
- If the user asks for a timeline plan only, do not execute.
- If the user asks to cut now, use the approved removal ranges directly.

## References

Read these only if needed:

- `.agents/memory/premiere-workflow.md`
- `apps/premiere/adobe-mcp/PREMIERE_MCP_WORKFLOW.md`

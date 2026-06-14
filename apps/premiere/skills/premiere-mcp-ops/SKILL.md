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
  "regroup" happens inside each Extract — there is no separate gap-closing call,
  and none is allowed.
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
  actual clip layout confirms it (`verify_sequence_layout`, `get_full_project_data`,
  or clip-level inspection).
- If the tool reports success but the target sequence did not change, stop and
  report a Premiere focus / keyboard automation problem. Do not invent a fallback
  edit strategy inside the live project.
- Do not use `set_clip_position` to close gaps. It can stretch/expand clips rather
  than move them safely.
- If a residual gap is reported after a cut (Extract did not regroup, e.g. because
  a track was not targeted), stop and report it. Do not close it with
  `set_clip_position`, split, or trim. Tell the user the cuts landed but a gap
  needs manual packing.

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

## Gap Handling

Extract (the cut command) closes each removed range's gap in the same op, so a
correct cut leaves no gap — that is the "regroup". If the `verification` block
still reports a residual gap, something went wrong (e.g. a track was not targeted,
or focus/command mapping failed).

- Do not close gaps with `set_clip_position`; it can stretch/expand clips.
- Do not close gaps with split/trim/delete fallback APIs.
- Only close gaps if there is a documented, verified-safe Premiere workflow for the
  current project state.
- If a residual gap is reported and no safe gap-closing method is verified, stop
  and tell the user: "Cuts landed but a gap remains for manual packing," and give
  the exact gap location from the `verification` block.

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

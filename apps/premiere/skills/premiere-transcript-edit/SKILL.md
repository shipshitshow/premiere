---
name: premiere-transcript-edit
description: Plan and execute transcript-driven edits for this repo's Premiere workflow. Use when the user provides a transcript JSON, wants a keep-plan, wants removal ranges, or wants a livestream cut assembled around a topic and target runtime.
---

# Premiere Transcript Edit

Use this skill for transcript-first editing in this repo.

## Inputs

- Transcript JSON file
- Topic or framing angle
- Target runtime if specified

Expected transcript shape:

```json
{
  "language": "en-us",
  "segments": [
    {
      "start": 247.62,
      "duration": 29.47,
      "words": [
        {"text": "So", "start": 247.62, "type": "word", "tags": []}
      ]
    }
  ],
  "speakers": []
}
```

Ignore empty `text` values and disfluency-only filler entries when planning.

## Workflow

1. Read the transcript and extract timestamped segment text.
2. Identify the strongest editorial angle from the user's prompt and the transcript.
3. Build a keep-plan with section labels and source ranges.
4. Tighten the selection to hit the requested runtime.
5. Convert keep ranges into removal ranges.
6. If the user wants execution and Premiere MCP is available, hand off the removal
   ranges to the Premiere cutting workflow.

## End-to-end execution (after approval)

This is the supported one-call path. The user does not manually edit the
Premiere timeline to cut or to close gaps:

1. Get user approval on the removal ranges (planning and execution are separate).
2. Call `remove_silence_segments(sequence_id, removal_ranges)`. It cuts each range
   with Premiere's Extract (ripple-delete), which normally **regroups** by closing
   the gap in the same A/V-synced op, frame-snaps to avoid 1-frame gaps, and
   verifies.
3. Confirm `verified: true` with zero residual gaps. If Premiere/UXP returned no
   frame ticks and Extract left only tiny native gaps, hand off to the Premiere
   MCP ops native Close Gap recovery and verify after every pass. For any other
   `verified: false`/`null` result, report the real layout
   (`verify_sequence_layout`) and stop — do not paper over it.
4. Hand back to the user to finish manually. Optional UXP-scriptable finishing
   helpers: `premiere_apply_lumetri_correction` (color), `premiere_clean_audio_pipeline`
   (DeNoise/DeReverb). The Lumetri "Auto" button, adjustment layers, and "Enhance
   Speech" have no UXP API and stay manual.

## Output Shape

Always provide:

- topic / framing line
- target runtime estimate
- keep ranges
- removal ranges

Example:

```text
Topic: Builders using AI already have leverage; backlash will not stop adoption

Keep:
- 247.62-325.90
- 354.09-493.50

Remove:
- 0.00-247.62
- 325.90-354.09
```

## Execution Rules

- Do not cut blindly from transcript text alone if the user only asked for planning.
- Wait for approval before asking the Premiere MCP layer to change the timeline.
- If the user wants a shorter or more technical cut, revise the keep-plan first, then regenerate removal ranges.

## References

Read these only if needed:

- `.agents/memory/premiere-workflow.md`
- `apps/premiere/adobe-mcp/PREMIERE_MCP_WORKFLOW.md`

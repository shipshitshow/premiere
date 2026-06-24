# 2026-06-11 - Premiere MCP Cut Failure Postmortem

## Context

User provided transcript:

- `/Users/decod3rslabs/DeCod3rs/2026/Pr/2606/260610/260610 - livestream.json`

Target Premiere sequence:

- `260610 - video`

User requested a sharp 15-minute cut and explicitly wanted the existing Premiere timeline cut through the Adobe Premiere MCP connection.

## What Went Wrong

The agent did not stay inside the documented Premiere MCP workflow.

Failures:

- Created extra sequences that were not requested:
  - `260610 - sharp 15min cut`
  - `260610 - sharp timeline cuts`
  - `260610 - API assembled 15min`
- Created an external FFmpeg/rendered assembly even though the user asked for a Premiere timeline edit.
- Tried fallback APIs (`remove_linked_clip_range`, `trim_video_clip`, `set_clip_position`) instead of staying with the documented `remove_silence_segments` workflow.
- Trusted `remove_silence_segments` success responses without immediately verifying the actual `260610 - video` clip layout.
- Used `set_clip_position` to close gaps; this stretched/expanded clips instead of safely moving them.
- Did not stop early enough when Premiere keyboard automation / Timeline focus behaved inconsistently.

## What Actually Worked

The only reliable cut path was:

1. Target the existing sequence `260610 - video`.
2. Use `remove_silence_segments` / marked in-out ranges only.
3. When Extract did not land, directly sending the Premiere Lift/Extract key after in/out points were set affected the timeline.
4. The user manually packed the remaining gaps successfully in Premiere.

The correct keep ranges for this cut were:

```text
102-159
1329-1568
1666-1917
2375-2581
4560-4688
4782-4812
```

Equivalent removal ranges from the original source timeline:

```text
0-102
159-1329
1568-1666
1917-2375
2581-4560
4688-4782
4812-4833.56
```

## Mandatory Rule For Future Premiere Edits

For user video edits in this repo:

- Always use `skills/premiere-mcp-ops/SKILL.md`.
- Cut only the named/active sequence the user requested.
- Do not create alternate sequences unless explicitly asked.
- Do not render proxy assemblies or FFmpeg cuts unless explicitly asked.
- Do not use `remove_linked_clip_range`, `trim_video_clip`, `set_clip_position`, split tools, or API assembly as fallbacks.
- Use `remove_silence_segments` only for transcript-based removal ranges.
- Verify after every cut batch with `verify_sequence_layout`, not only tool success.
- If `remove_silence_segments` reports success but the clip layout did not change, stop and report Timeline focus / keyboard automation failure.
- If gaps remain after cutting, use only the documented native Close Gap recovery
  when its constraints are met: Premiere/UXP frame ticks are unavailable, Extract
  changed the requested active sequence, and the residual gaps are tiny
  Extract-created gaps. Press `W` one pass at a time and verify after every pass.
  Otherwise stop and tell the user the cuts landed but verified packing did not.
- Never improvise another editing strategy inside a live Premiere project.

## Human Outcome

The user had to manually pack the clips together after the agent made avoidable workflow mistakes. This was embarrassing and should be treated as a hard regression in Premiere editing behavior.

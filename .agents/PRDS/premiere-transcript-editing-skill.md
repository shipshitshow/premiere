## PRD: Transcript-to-Premiere Editing Skill

**Task:** [Premiere Transcript Editing Skill](../TASKS/premiere-transcript-editing-skill.md)
**Status:** Draft
**Owner:** Codex  
**Date:** 2026-04-16

### Problem

The repo already contains the editing logic and docs for transcript-driven Adobe Premiere work, but that knowledge is fragmented across:

- `mcp/premiere-python-mcp/WORKFLOW.md`
- `mcp/adobe-premiere-mcp/PREMIERE_PIPELINE_SETUP.md`
- session logs
- ad hoc prompts in chat

That causes repeat friction:

- The model has to rediscover the transcript schema each session.
- The safe cutting method (`remove_silence_segments` only) is easy to forget.
- The workflow mixes planning, inversion to removal ranges, and MCP execution without a single stable operating guide.
- Session quality depends too much on remembering prior context.

### Goal

Create a repo-specific skill that turns a transcript into an approved Premiere editing plan and then executes the edit through the existing Premiere MCP workflow.

### Non-Goals

- Replace `adobe-premiere-mcp`
- Replace `premiere-python-mcp`
- Build a generic video-editing skill for all repos
- Fully automate creative judgment without user approval
- Rebuild rendering/export logic already handled elsewhere

### Proposed Skill

**Working name:** `premiere-transcript-edit`

### User Stories

1. As an editor, I can drop in a transcript file and ask for a 10-minute cut around a topic, and the skill will produce a keep-plan with source timestamps.
2. As an editor, I can approve the strategy before any timeline changes happen.
3. As an editor, once approved, the skill converts keep ranges into removal ranges and uses the correct Premiere MCP tool safely.
4. As an editor, if the MCP connection drops, the skill knows how to resume from remaining cuts instead of restarting blindly.

### Scope

#### In Scope

- Detect and explain supported transcript formats used in this repo
- Read transcript JSON and extract timestamped content
- Produce a keep-segment plan based on user topic and target length
- Invert keep segments into removal ranges
- Enforce the documented cutting constraints:
  - use `remove_silence_segments`
  - do not use split/delete tools that desync media
  - require Premiere to be frontmost
- Guide recovery after partial failure
- Store repo-specific references so the workflow is stable across sessions

#### Out of Scope

- Auto-generating final creative choices without review
- Subtitle styling/rendering
- Thumbnail generation
- Browser-based publishing/upload automation
- Replacing manual gap-closing behavior in Premiere

### Why A Skill Is Worth It

This repo has fragile, repo-specific operating knowledge that a generic model or generic `skills.sh` skill will not reliably infer:

- the transcript schema we expect
- the exact keep-to-remove inversion workflow
- the one cutting tool that actually preserves sync here
- the frontmost-window requirement
- the resume/recovery procedure

This is exactly the kind of repeated, low-freedom workflow a local skill should encode.

### Recommended Shape

Do **not** build one broad “video editor” skill.

Build one narrow operational skill first:

- `premiere-transcript-edit`

Optional later companion skills:

- `premiere-render-verify`
- `premiere-transcript-normalize`

### Skill Behavior

When triggered, the skill should:

1. Identify the transcript source and schema.
2. Summarize the content and ask only the minimum planning questions if needed.
3. Produce a keep-plan with timestamps and section labels.
4. Estimate resulting runtime and tighten the plan if necessary.
5. Wait for user approval.
6. Convert the keep-plan into removal segments.
7. Confirm Premiere MCP prerequisites:
   - proxy is running
   - UXP plugin connected
   - active sequence available
   - Premiere frontmost
8. Execute cuts with `remove_silence_segments`.
9. If execution fails midway, inspect state and resume with only remaining segments.

### Deliverables

#### 1. Skill Folder

Create a local skill with:

- `SKILL.md`
- optional `references/`
- optional `scripts/`

Suggested location:

- `/Users/decod3rslabs/www/premiere/.agents/skills/premiere-transcript-edit/`

#### 2. SKILL.md Content

The skill should encode:

- when it triggers
- transcript schema examples
- planning workflow
- keep-to-remove conversion rules
- approved Premiere MCP tool usage
- recovery steps

#### 3. Reference Files

Suggested references:

- transcript schema examples
- sample keep-plan and removal-range formats
- troubleshooting notes for Premiere MCP/proxy/UXP

#### 4. Optional Scripts

If repetition justifies it later:

- `scripts/normalize_transcript.py`
- `scripts/invert_keep_ranges.py`

These are optional for v1. The first version can be instruction-driven.

### Acceptance Criteria

- A user can provide a transcript and topic and receive a coherent keep-plan with timestamps.
- The skill explicitly waits for approval before changing the timeline.
- The skill uses only the approved cut path for timeline execution.
- The skill contains enough repo-specific guidance that a fresh session can run the workflow reliably.
- The skill is concise and does not duplicate large docs unnecessarily.

### Risks

- Over-scoping into a generic video-editing framework
- Duplicating docs instead of referencing them cleanly
- Encoding too much rigidity into creative planning
- Mixing planning and execution so tightly that safe approval checkpoints get skipped

### Recommendation

Yes, build this skill.

But keep v1 narrow:

- transcript in
- keep-plan out
- approval gate
- removal ranges
- Premiere MCP execution

That will remove the repeated operational confusion without forcing a rewrite of the existing tooling.

### Proposed Next Step

If approved, implement v1 of `premiere-transcript-edit` as a local repo skill and wire it to the existing workflow docs rather than creating a second parallel process.

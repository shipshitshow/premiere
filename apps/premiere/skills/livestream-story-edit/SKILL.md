---
name: livestream-story-edit
description: Shape a long livestream into a tight story-driven video. Use when the source is a livestream transcript or recording and the goal is to find the strongest thesis, hook, supporting beats, and ending rather than simply trimming dead air.
---

# Livestream Story Edit

Use this skill when a raw livestream has good ideas but weak structure.

The job is not just to shorten it. The job is to turn conversation into a story.

## Goal

Find the strongest through-line and cut the video around that, even if the original livestream wandered.

## What To Optimize For

- one clear thesis
- one strong hook near the front
- supporting beats that escalate or deepen the point
- minimal repetition
- a clean ending with a takeaway, punchline, or call to action

## Default Shape

For this repo's typical talking-head / builder livestreams, prefer:

1. Hook
2. Thesis
3. Proof beat 1
4. Proof beat 2
5. Optional counterpoint or objection
6. Strong closing line

Do not preserve the original order if a later moment makes a better hook.

## Editing Rules

- Cut setup chatter unless it adds character or context.
- Prefer clean, direct sentences over rambling versions of the same idea.
- When two segments make the same point, keep the sharper one.
- If a speaker struggles through a sentence and says it better later, keep the later version.
- Keep moments that create momentum: bold claims, concrete examples, tension, disagreement, strong conclusions.
- Remove circular debate unless it meaningfully changes the argument.

## For "Us" Style Videos

When the material sounds like your usual AI / builder conversations, bias toward:

- contrarian but usable framing
- concrete examples over vague opinion
- builder leverage over abstract ethics talk
- strong lines about adoption, workflow, economics, or competitive reality

## Output

Always produce:

- the core thesis in one sentence
- a proposed title or framing line
- a keep-plan with section labels
- a note on why each kept section earns its place

Example shape:

```text
Thesis: People arguing emotionally about AI are already behind the people using it daily.

Sections:
- Hook
- Why backlash misses the real trajectory
- Concrete workflow leverage
- Why adoption keeps compounding
- Closing punch
```

## Hand-off

After the story structure is approved:

- use `premiere-transcript-edit` to derive precise keep/remove ranges
- use `premiere-mcp-ops` if the user wants the cuts applied in Premiere

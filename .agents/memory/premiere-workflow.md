---
last_verified: 2026-09-09
---

# Premiere Workflow Memory

Durable house facts. Current computer-use instructions live in
`apps/premiere/skills/premiere-weekly-edit/SKILL.md` and the sibling shorts skill.
The MCP cut contract applies only to explicitly requested MCP operation.

## Source of truth

The live Premiere sequence. Do not replace it with a rendered assembly, proxy
timeline, or generated alternate sequence unless the user explicitly asks.

## Active workspace

- App: `apps/premiere`
- MCP + proxy + UXP: `apps/premiere/adobe-mcp`
- Legacy ExtendScript: quarantined at `apps/premiere/scripts/legacy-extendscript`
- Old self-editing Python app: git history only

## Historical audio preset (observed before September 2026)

Historical reference only, superseded for the 260908 edit by the chain below:

1. Parametric EQ — observed `Low Shelf Frequency` around `110.39 Hz`
2. DeNoise — Amount `20.0%`
3. DeReverb — Amount `20.0%`
4. Vocal Enhancer — Mode `Low Tone`

`premiere_get_audio_tracks` lists tracks and reports
`mixerInsertsSupported: false`. Premiere UXP `AudioTrack` has name/mute/clips
only — not mixer inserts. Clip-level DeNoise/DeReverb is
`premiere_clean_audio_pipeline`. Do not claim the house mixer preset was applied.

## Known 2026-06-23 livestream ranges

Sequence cut before the word "loop." when planned as `431.85-508.74`.
Use `432.15-508.74` instead. Lead cut `0.0-330.96` verified after one
native Close Gap pass; the loop cut needed two.

## Env overrides (code defaults)

- `PREMIERE_APP_NAME` — default `Adobe Premiere Pro 2026`
- `PREMIERE_APP_PATH` — optional absolute `.app` when several versions are installed
- `PREMIERE_CLOSE_GAP_KEY` — default `w` (this workspace). Premiere's default
  `W` is Ripple Trim Next Edit; `close_gap_recovery` hard-stops if content ticks
  change, but the first press already happened.

## September computer-use workflow

Vincent reaffirmed native computer use on 2026-09-09. Read the repository skills,
including `premiere-weekly-edit/references/native-control.md`, before UI work.
The full edit record and frame tables live in that skill's
`references/260908-edit-record.md`.

260908 audio: Parametric EQ 80 Hz high-pass / 24 dB per octave, DeNoise 20%,
DeReverb 20%, single-band compressor −18 dB / 3:1 / 5 ms / 120 ms / +5 dB,
true-peak limiter −1 dB. Lumetri: exposure +0.15, contrast +5, highlights −18,
shadows +12, whites −8. Assess the new recording before reusing settings.
Caption style: Poppins ExtraBold, short uppercase phrases, white / black 5 px
outer stroke, selected green #00E83F keywords; 84 px vertical and 72 px wide.
These are applied settings with playback review still pending, not a claim of
final user approval or measured audio quality.

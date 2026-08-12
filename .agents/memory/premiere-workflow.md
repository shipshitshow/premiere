---
last_verified: 2026-08-12
---

# Premiere Workflow Memory

Durable house facts. The **live-cut contract** lives in
`apps/premiere/skills/premiere-mcp-ops/SKILL.md` — do not copy it here.

## Source of truth

The live Premiere sequence. Do not replace it with a rendered assembly, proxy
timeline, or generated alternate sequence unless the user explicitly asks.

## Active workspace

- App: `apps/premiere`
- MCP + proxy + UXP: `apps/premiere/adobe-mcp`
- Legacy ExtendScript: quarantined at `apps/premiere/scripts/legacy-extendscript`
- Old self-editing Python app: git history only

## House audio polish (manual)

Track-level Audio Track Mixer insert chain on the dialogue track, after the cut:

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

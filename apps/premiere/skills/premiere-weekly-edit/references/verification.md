# Native edit verification

Last verified: 2026-09-09. Read for any native cut, assembly, caption replacement
or orientation change. Verification supplements computer use; it does not authorize
an API edit or an external project rewrite.

## Before mutation

Identify project and active sequence visually; do not rely on a previous task's
window ID, tab order, coordinates or sequence name. Record the expected full master
duration and locks. Record the target's source media, source ranges, destination
ranges and frame rate. Save a baseline when authorized and preserve a recoverable
project backup before a substantial batch. Reuse an already approved plan.

For computer use, inspect targeted tracks, linked picture/audio, playhead and
selection. A successful click is not evidence of the intended selection. Stop
when the UI cannot distinguish the master from the target. Do not broadly delete
clips to obtain an empty sequence.

## After a small cut or insertion batch

- Master retains the original source range and all A/V tracks are locked.
- Target picture and dialogue boundaries match at every cut; no one-frame drift.
- Program lanes start at zero and adjacent clips meet exactly. Intentional gaps
  on graphics/B-roll/effect lanes are separate from program gaps.
- Each source selection and ordering matches the intended plan. A/V sync alone
  can pass the wrong assembly or an accidentally shortened master.
- Duration and clip count match expectations. With frame-rate interpretation
  differences, compare ticks and actual source selection before accepting rounding.
- Scrub across the junctions and listen for clipped words or transitions masking
  dialogue. Do not report a listening pass from visual waveforms or effect hashes.

On an unexpected result, stop dependent operations, inspect the affected sequence,
and undo the known last operation only after confirming focus. Verify restoration
before resuming. Never repeatedly send a mutation because the screenshot is stale.
For gap recovery, inspect the cause and the native command's current binding first;
`W` is not universally Close Gap. Do not call MCP recovery in a computer-use task.

## Saved project as supplemental evidence

After a native save, read the `.prproj` gzip/XML without modifying it. Correlate
Sequence → TrackGroups → tracks → clip items → SubClip → Clip. Keep both exact
ticks and display-frame values; different sequences may use different tick rates.
Read lock state for every master A/V track, not only the populated tracks.

Data tracks contain caption clip items and FormattedTextData blocks. Rich text can
store white text and green words in separate formatting runs; searching for one
contiguous sentence may fail. Parse/inspect all runs and compare actual cue start,
end, wording and count with the sidecar. Font presence or a matching effect hash
is only part of verification; use native UI to confirm appearance and settings.
Repeated parameter names require component identity, implicit default Motion is
valid, and numeric plugin references are not necessarily missing file paths.

The 260908 CSVs preserve a known snapshot; they are not an import mechanism.
Do not hard-code their project path, source ranges, counts or IDs into next week's
checks. Temporary helpers under `/private/tmp` may disappear and are not dependencies.

## Before handoff/export

Check both orientations: matching cuts/audio, appropriate speaker crop, full-frame
lighting layer, captions visible and within safe margins, longest phrases, green
words, first/last cues, and no caption tail beyond picture. Sync sidecars and
manifests to native ranges, retaining obsolete proposals only as clearly historical.

State which checks ran and what remains. Save a reviewable project. If review was
reserved, leave exports pending. After an authorized Premiere export, verify actual
file dimensions, duration, burned-in captions, sound, first/last frames and tails.
An SRT beside a video does not prove burned-in subtitles. An old export does not
prove the current edit was exported.

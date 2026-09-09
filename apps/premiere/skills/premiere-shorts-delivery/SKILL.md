---
name: premiere-shorts-delivery
description: Turn Vincent's Premiere livestream into 3–5 edited shorts with corrected visible captions, vertical and 16:9 versions for X, and one delivery folder per short. Use for short selection, native sequence preparation, folder audits, or approved exports in this weekly workflow.
---

# Premiere shorts and delivery

Use the installed Premiere app under Vincent's native macOS-control preference. The sibling [premiere-weekly-edit](../premiere-weekly-edit/SKILL.md) skill documents project preservation and native panel operation. Respect the current request: a folder audit or skill-writing request does not authorize new timeline edits or exports.

## Build reviewable shorts

- Select 3–5 self-contained moments from the full livestream, with one idea, immediate context, and a satisfying ending. The 260908 examples lasted 24–31 seconds; that is an example, not a mandatory duration for future material.
- Keep the complete `livestream` locked and retain the long edit. Assemble each requested short in its own native sequence using the project-local source. Never clear the master or trim a valuable duplicate merely to obtain an empty sequence.
- Plan source in/out ranges and destination frames, remove repetition and dead air without changing meaning, then verify the actual applied ranges and synced picture/audio. Separate proposed ranges from confirmed native ranges in saved metadata. Do not leave an obsolete cut map labeled as applied.
- Produce both 1080×1920 vertical and 1920×1080 16:9 when requested, at the appropriate sequence frame rate. The working reference used 30 fps. Match the edit and audio timing across variants. For a side-by-side interview, follow the active speaker in vertical and retain both speakers in wide. Inspect the actual source geometry before calculating crops.
- Apply and verify dialogue cleanup and lighting in every sequence. Reference the reviewed long edit when appropriate, but assess the short's own levels and crop. A full-duration lighting layer must cover the output frame after orientation changes.

## Visible corrected subtitles

Read the transcript against actual speech, correct obvious recognition errors and names, and preserve what was said. Map captions to the edited timeline, not raw recording time. Use short readable cues with a maximum of two lines, punctuation, and safe margins. Check opening/closing cues, fast speaker changes, and line breaks.

Vincent’s visual references use bold uppercase white captions with a black outline and green keyword accents. In the revised 260908 project, use native style `260908 - Shorts - Punchy`: Poppins ExtraBold, 84 px vertical / 72 px wide, 5 px black outer stroke and shadow, bottom-center, Y −220 vertical / −90 wide. Green accent: #00E83F. These are observed project values, not universal dimensions. The earlier Arial treatment and simply capitalizing long cues were rejected. Shorten cues to natural phrases, usually 2–4 words and at most two lines; balance reading time against speech. Emphasize meaningful words selectively. Do not claim animation when only static character colors were applied.

Keep wide overrides local so they do not overwrite the vertical shared style. Set the destination caption track style before pasting styled captions between sequences, then change size and position locally; applying a style afterward can reset keyword colors. Inspect longest cues, first/last cues and accented words in both formats. Import at timeline zero, verify captions are visible, and ensure the final cue ends within picture. Native import may round SRT timing, so synchronize delivery sidecars to the actual saved native caption ranges.

SRT files alone are not visible video subtitles. Verify native caption tracks; for approved export, select the caption option that burns them into the image and inspect the exported file. A cue file modified on disk is not proof the in-project caption changed.

## Folder convention and audit

Inspect neighboring dated projects first. Observed working structure:

```text
<YYYY>/Pr/<YYMM>/<YYMMDD>/
  <YYMMDD> - livestream.prproj
  <YYMMDD>.mp4
  transcript - livestream.json
  shorts/
    shorts-edit-plan.json
    short 01 - <title>.srt
    short 01 - <title>/
      edit-plan.json
      vertical/
        captions.srt
      16x9/
        captions.srt
```

Repeat the short folder for each selected moment. Preserve root SRT files already linked into Premiere; duplicate-looking files may be real dependencies. Do not relocate source media, plugin assets, autosaves, or previews as cosmetic cleanup.

Audit that project media references resolve, the copied source matches the original, each short has both orientation folders, sidecar cues agree with actual sequence timing, and project-wide/per-short manifests agree. Record exact native sequence names, dimensions, frame rate, duration, caption count, and export status. Update stale preparation notes that contradict the saved project. Keep proposed titles clearly marked if they were never added as graphics.

At review stage, folders may contain captions/metadata only. Say clearly that MP4s do not yet exist. Do not present those folders as publish-ready videos. Existing long exports under `<YYYY>/finals/<YYMM>/<YYMMDD>/` do not establish approval or completion of new short exports.

## Review and export

If Vincent reserved Premiere review first, finish the sequences and folder preparation, then wait for that review. Do not add an extra approval step once he explicitly requests export. For an approved export, use Premiere, the verified full sequence range (not stale work-area marks), the requested orientation, audible processed dialogue, and captions burned into the image. Use distinct filenames per short and orientation; follow the user's output location or existing finals convention, retaining one folder per short.

Verify each rendered file's duration, dimensions, start/end, captions, and audible playback. Check for black tails, clipped captions, wrong speaker crops, jumps that cut words, and audio peaks. Report any unperformed listening/render checks honestly. Titles/post copy, thumbnail or cover selection, and publishing are separate remaining work when requested; exporting does not authorize posting to X or other platforms.

This repository copy is the maintained source. Synchronize the installed `~/.codex/skills/premiere-shorts-delivery/` copy after updates.

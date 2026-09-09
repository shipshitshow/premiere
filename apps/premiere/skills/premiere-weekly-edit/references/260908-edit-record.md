# 260908 applied edit reference

Last verified: 2026-09-09. Reconciled the conversation, installed skills, project-local
manifests, native-operation scripts and saved Premiere project. This is an applied
state reference, not a replay of every click or a new editorial plan. No timeline
changes or exports were made during this documentation pass.

## Production assets

Project: `DeCod3rs/2026/Pr/2609/260908/260908 - livestream.prproj`.
Working source: `260908.mp4` beside the project; original under
`DeCod3rs/_raws/2609/260908.mp4`. The user's initial `.m4` spelling was a typo.
The source copy was previously hash-matched to the original. Transcript:
`transcript - livestream.json`, exported by Vincent after the Text panel discussion.

Saved project SHA256 at this audit:
`4ffb15987a16353bea837bc4427f9901b56f241c4d738bc3a120ffb2b4f7f01b`.
A later save may change the hash without changing the edit.

Preserve the user's bins: `assets`, `sequences/shorts`, `sequences/youtube`.
Do not reorganize linked media, Animation Composer assets, root SRTs, autosaves
or previews. The full transcript and binary project remain in production storage.

## Sequences and actual ranges

| Sequence | Frame size | Picture frames | Display duration | Source clips | Caption cues |
| --- | --- | ---: | --- | ---: | ---: |
| livestream | 1920×1080 | 82184 | 45:39:14 | 1 | — |
| video | 1920×1080 | 27000 | 15:00:00 | 134 | — |
| short 01 - AI that cuts server costs | 1080×1920 | 811 | 00:27:01 | 8 | 28 |
| short 02 - You do not need the smartest AI | 1080×1920 | 943 | 00:31:13 | 5 | 36 |
| short 03 - Get paid for AI savings | 1080×1920 | 721 | 00:24:01 | 9 | 20 |

Each short also has a 1920×1080 sequence with ` - 16x9` appended; source ranges,
duration and caption timing match its vertical version. Shorts run at 30 fps.
The original/long sequences use 8467191533 ticks per frame, very close to 30 fps;
shorts use 8467200000. Do not treat those as identical for exact tick arithmetic.
The first short's proposed 812-frame duration became 811 frames in the native edit.

`livestream` has all six A/V tracks locked and retains the full source.
The long sequence was renamed by the user from `edit` to `video`; preserve that.
`shorts - audio setup reference` is an existing 15-minute working duplicate for
mixer transfer, not a fourth deliverable. Do not clear or delete it as cleanup.

- [260908-native-clips.csv](260908-native-clips.csv) records every saved A/V clip,
  including adjustment layers, transition graphics and transition sounds, with
  destination and source frame values plus exact native ticks. Destination ends
  are exclusive; source-out columns retain the saved native value. They are not
  instructions for the UI Out-point keystroke. Rows include the working reference
  and both orientations to make preservation checks explicit.
- [260908-captions.csv](260908-captions.csv) records all 168 applied caption cues
  across six sequences, actual destination frame ranges, text and green keywords.
  Character color was inspected in Premiere; the CSV is not a styled import format.

The full long-video source selection is in the clip table. Do not invent a title
or retroactively call a reconstructed thesis the user's approved wording.

## Audio and light applied

Dialogue Audio Track Mixer chain on the long video and all six shorts:

1. Parametric EQ: 80 Hz high-pass, 24 dB/octave.
2. DeNoise: 20%.
3. DeReverb: 20%.
4. Single-band Compressor: −18 dB threshold, 3:1 ratio, 5 ms attack,
   120 ms release, +5 dB makeup.
5. Hard Limiter: true peak −1 dB, input 0 dB, 7 ms lookahead,
   100 ms release, linked channels.

Copied through native Copy Track Effects / Paste Track Effects. All six short
chains matched `video` by saved effect identity and opaque-data hash. This proves
matching settings, not perceptual quality, measured loudness or a listening pass.
The older Vocal Enhancer / Low Tone preset in repository history is not this chain.

Lumetri: exposure +0.15, contrast +5, highlights −18, shadows +12, whites −8.
Long video V2 has five adjacent adjustment layers, split at frames 3660, 7165,
13890 and 17294, ending at 27000. Each short has one full-duration V2 layer.
Native UI confirmed Basic Correction contrast +5; XML has multiple controls named
Contrast, so a dictionary keyed only by name incorrectly reported zero.

## Framing and transitions

Vertical source Motion: scale 200%, Y 1080; Mitchell X −220, Vincent X 1540.
Short 01 follows Mitchell throughout. Short 02 follows Vincent in source clip 3
(destination frames 292–499), Mitchell elsewhere. Short 03 follows Mitchell in
clip 7 (519–552), Vincent elsewhere. Clip numbers are one-based. These positions
fit this recording's split-screen geometry, not every future interview.
Vertical adjustment-layer Motion is 200%, position 540/960. Wide picture and
adjustment layers are 100%, position 960/540; an omitted/default Motion component
in the project may encode this without explicit parameters.

Six Animation Composer Camera → Pan → Left transitions were applied to the long
video around frames 449, 3660, 7165, 13890, 17294 and 21351. Graphic components
occupy V3/V4 and associated `Transition Complex 14.wav` clips occupy A2/A3.
Exact spans are in the clip table. Preserve linked components together. No claim
is made that a preset merely selected in the browser has been applied.

## Caption treatment and delivery

Earlier Arial Bold was too plain. Capitalizing the existing long cues with
Poppins ExtraBold 68 px produced tall blocks and was rejected. The applied revision:

- Native track style `260908 - Shorts - Punchy`, Poppins ExtraBold.
- 84 px vertical, 72 px wide; uppercase short phrases, one/two lines in inspected frames.
- White text, 5 px black outer stroke, black shadow; bottom center.
- Y offset −220 vertical, −90 wide. Keep wide overrides local.
- One selected keyword cue per short: CODEBASE, ROUTINES, SAVINGS, in #00E83F.
- No per-word animation or animated highlighting was added.

Imported assets are `short 01 - punchy.srt`, `short 02 - punchy.srt`, and
`short 03 - punchy.srt` in the project `shorts/` root. Preserve old root SRTs that
remain linked. Delivery sidecars live at `shorts/<short name>/{vertical,16x9}/captions.srt`.
Native caption ends are 810/939/717 frames, safely inside pictures of 811/943/721.
One-frame import rounding was reconciled into the sidecars and manifests.

`shorts/shorts-edit-plan.json`, each short's `edit-plan.json`, format READMEs and
`shorts-preparation.md` distinguish applied clips from historical planned ranges.
Suggested opening titles were not added as graphics. No short MP4s are exported.
Earlier long exports under `DeCod3rs/2026/finals/2609/260908/` do not establish
approval for current short exports or prove they match the current project.

## Failures to avoid and unfinished review

The master livestream was accidentally emptied earlier in the session and was
restored. The successful end state is full source + locked tracks; never repeat
sequence clearing as a construction shortcut. Wrong focus, Shift+3 and inline
renaming were recurring risks. A desktop wrapper's panel-control failure did not
mean Premiere could not be controlled; native macOS input subsequently worked.

Verified: packed and synced program clips, preserved master, matching variants,
source selections, frame bounds, Poppins font/sizes, mixer settings, lighting
coverage and representative/long caption frames. Full playback/listening and
rendered-file QA remain pending. Vincent requested review in Premiere before
export. Last handoff showed short 02 at 00:11 with ROUTINES green; re-observe the
current screen before acting. Export only after the requested review/authorization.

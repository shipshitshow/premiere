# Native panel lessons

Observed 2026-09-08 on Mac Studio, Premiere Pro 2026. Re-check behavior after app or workspace changes.

- Discover the actual Premiere process and window bounds. Native app activation through `NSRunningApplication` worked; AppleScript `tell application ... to activate` hung in this session. System Events could operate native menu items. Mouse input through macOS CoreGraphics worked where a desktop-control wrapper could not click panels. A wrapper limitation is not proof Premiere cannot be controlled.
- Only use alternative UI methods within user authorization and the current tool's rules. Do not turn UI permission errors into hidden API/bridge fallbacks.
- Prefer named native menu items where accessible. Screenshots of the main window may omit menus/dialogs: inspect the relevant window or full desktop, rather than guess. Reconfirm focus after modal dialogs.
- Open a sequence by double-clicking its Project panel sequence icon. Clicking an already selected name can enter inline rename. Return can move into renaming the next row. Use the explicit Rename context menu and Escape afterward. Search results may contain dependencies with unrelated names: verify both icon type and full target name.
- Do not use Shift+3 to assume the desired timeline becomes active. It selected the wrong sequence in this workspace.
- Double-click a timecode field and select the entire value before typing. Re-read the actual timecode. Verify one source insertion before batching. In 260908, near-30-fps source timing caused a one-frame difference when interpreting out points; inspect source/destination ticks and actual duration instead of copying a universal inclusive/exclusive keystroke rule.
- Selection Follows Playhead may select the source clip immediately after a paste or timecode change. Click empty timeline space, then the intended adjustment layer or clip. Clicking one member of a multiple selection may retain the others. Confirm Properties/Effect Controls names before changing parameters.
- Native Audio Track Mixer Copy Track Effects/Paste Track Effects worked. Locked target tracks can disable rack editing. Never unlock the master livestream for this; work on the requested edit or a clearly identified working sequence. A copied reference sequence is a working aid, not a deliverable.
- Make orientation variants with native Duplicate and Sequence Settings. Review the Scale Motion Proportionally checkbox; it changes how existing transforms respond. In 260908, widescreen variants required Motion reset to 100%, center 960/540, for picture and adjustment layers. Default Motion may be implicit in saved XML. Captions need their own position/font check after dimension changes.
- Native New Caption Track can place imported SRT at Timeline Start with a project track style. Caption styles can have local overrides. Do not push a widescreen override back to a shared vertical style.
- A saved XML parser may encounter repeated parameter names (e.g. multiple Contrast controls), omitted default components, and numeric plugin media identifiers. Do not collapse repeated names or report numeric IDs as missing filesystem paths. Resolve component/parameter identity and compare native UI when uncertain.

- Avoid reactivating an already frontmost Premiere app on every mouse click: it can dismiss dropdowns or steal focus. Activate only when needed, then send the intended native click. Dialogs such as Color Picker and Create Style may require a full desktop capture.
- To replace caption cues, confirm the correct short sequence and select only C1 with a narrow marquee. Delete the selected captions only, then drag the prepared SRT onto the empty existing C1 at timeline zero; this inherited the track style without creating a new track. Never use a broad Select All/Delete operation.
- For a keyword color, use the Text tool in the Program Monitor, select the word, and set its Fill through the native Color Picker. Exit to the Selection tool and verify the surrounding words remain white. Changing a shared style after this can erase character-level accents.

## Repeat the native edit, using fresh screen observations

1. Load the project-local recording in the Source Monitor. Confirm the intended
   edit/short is open in the Timeline, with linked V1/A1 patching and targeting.
2. Set the destination playhead explicitly. Focus the Source Monitor, enter the
   planned source In and Out via its timecode field, mark I/O, then use the native
   Insert command (comma in the observed layout). Confirm current shortcut mapping.
   Source Insert and sequence Extract showed different out-point rounding in this
   recording; verify one insertion and its exact source/destination span first.
3. For removals from an approved sequence plan, process ranges from the end backward
   so earlier timecodes remain stable. Focus that sequence, mark In/Out, then use
   native Extract. The September helper marked the last included frame (`end - 1`)
   for sequence Extract; this is observed behavior, not a universal source-Out rule.
4. Save after a small batch and compare actual ranges, duration, sync and packing
   with the expected result. Do not replay old coordinate scripts or use their stale
   `edit` name after the user renames the sequence.

For mixer effects, open Audio Track Mixer for the confirmed target, expose the
insert rack and set effect parameters in their native editor dialogs. Confirm the
track is editable before pasting copied track effects; never unlock the master.
For lighting, select only the intended adjustment layer, open Lumetri Basic
Correction and inspect actual values and frame coverage after changing orientation.
For Pan Left, locate the preset in Animation Composer, apply at the intended
junction and verify its graphic/sound components and playback. Avoid repeated
application after a slow panel update.

## Repeat the caption revision

Create the style in Properties → Track Style and save it as a project style.
Style creation and Fill Color Picker may be separate native windows: inspect the
full desktop when the main-window image does not show the dialog. Import corrected
SRT through native Import; use the file dialog's Go to Folder when appropriate.
Apply the track style before importing/pasting cues so later style assignment does
not discard word colors. An empty existing C1 can accept the SRT at zero directly.
When copying to wide, copy only C1, set the destination style first, remove only its
old C1 cues, paste at zero, then set size/Y as local overrides. Inspect counts,
text, timing and keyword colors after pasting. SRT itself cannot carry this rich
character styling or the native track style.

Full desktop/window bounds, control coordinates and app window IDs are ephemeral.
Use current computer-use screenshots and accessible controls. If a tool cannot
operate a panel, explain that specific limitation; use an alternative only within
existing authorization and that tool's rules. Never turn this guide into permission
to evade a computer-use tool's restrictions.

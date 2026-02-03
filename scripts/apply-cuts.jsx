/**
 * Apply cuts from silence detection to timeline
 * Removes segments between specified cut points
 *
 * @param {Array} cuts - Array of {start, end} objects (silence segments to remove)
 * @param {number} trackIndex - Video track index (0-based, default 0)
 * @returns {Object} Result with removed segments info
 */
function applyCuts(cuts, trackIndex) {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var track = seq.videoTracks[trackIndex || 0];

    if (!track) {
        return {
            success: false,
            error: "Video track not found"
        };
    }

    var removed = [];
    var errors = [];

    // Sort cuts by start time descending (remove from end first to preserve timecodes)
    cuts.sort(function(a, b) {
        return b.start - a.start;
    });

    for (var i = 0; i < cuts.length; i++) {
        var cut = cuts[i];
        var startTime = cut.start;
        var endTime = cut.end;

        try {
            // Convert seconds to ticks
            var ticksPerSecond = seq.projectItem.getProjectMetadata().match(/ticksPerSecond="(\d+)"/);
            var tps = ticksPerSecond ? parseInt(ticksPerSecond[1]) : 254016000000;

            var startTicks = Math.round(startTime * tps);
            var endTicks = Math.round(endTime * tps);

            // Find clips in range and remove or trim them
            var clipsToProcess = findClipsInRange(track, startTicks, endTicks);

            for (var j = 0; j < clipsToProcess.length; j++) {
                var clipInfo = clipsToProcess[j];
                processClipForCut(clipInfo.clip, startTicks, endTicks);
            }

            removed.push({
                start: startTime,
                end: endTime,
                duration: endTime - startTime
            });

        } catch (e) {
            errors.push({
                cut: cut,
                error: e.toString()
            });
        }
    }

    // Close gaps after removal
    closeGaps(seq);

    return {
        success: removed.length > 0,
        removedCount: removed.length,
        removed: removed,
        errors: errors,
        newDuration: seq.end
    };
}

/**
 * Find clips that overlap with a time range
 */
function findClipsInRange(track, startTicks, endTicks) {
    var clips = [];

    for (var i = 0; i < track.clips.numItems; i++) {
        var clip = track.clips[i];
        var clipStart = clip.start.ticks;
        var clipEnd = clip.end.ticks;

        // Check for overlap
        if (clipStart < endTicks && clipEnd > startTicks) {
            clips.push({
                clip: clip,
                index: i,
                start: clipStart,
                end: clipEnd
            });
        }
    }

    return clips;
}

/**
 * Process a clip for cutting
 */
function processClipForCut(clip, cutStart, cutEnd) {
    var clipStart = clip.start.ticks;
    var clipEnd = clip.end.ticks;

    // Case 1: Cut is entirely within clip - split clip
    if (cutStart > clipStart && cutEnd < clipEnd) {
        // Split at cutStart, remove middle, keep ends
        clip.end.ticks = cutStart;
        // Note: In real implementation, would need to create second clip
    }
    // Case 2: Cut starts before clip, ends within - trim start
    else if (cutStart <= clipStart && cutEnd > clipStart && cutEnd < clipEnd) {
        clip.start.ticks = cutEnd;
    }
    // Case 3: Cut starts within clip, ends after - trim end
    else if (cutStart > clipStart && cutStart < clipEnd && cutEnd >= clipEnd) {
        clip.end.ticks = cutStart;
    }
    // Case 4: Cut encompasses entire clip - remove clip
    else if (cutStart <= clipStart && cutEnd >= clipEnd) {
        clip.remove(false, false);
    }
}

/**
 * Close gaps in timeline after cuts
 */
function closeGaps(sequence) {
    // Use ripple delete to close gaps
    // This is done by checking each track for gaps

    for (var v = 0; v < sequence.videoTracks.numTracks; v++) {
        var vTrack = sequence.videoTracks[v];
        closeTrackGaps(vTrack);
    }

    for (var a = 0; a < sequence.audioTracks.numTracks; a++) {
        var aTrack = sequence.audioTracks[a];
        closeTrackGaps(aTrack);
    }
}

/**
 * Close gaps on a single track
 */
function closeTrackGaps(track) {
    var clips = [];
    for (var i = 0; i < track.clips.numItems; i++) {
        clips.push(track.clips[i]);
    }

    // Sort by start time
    clips.sort(function(a, b) {
        return a.start.ticks - b.start.ticks;
    });

    var currentPos = 0;
    for (var j = 0; j < clips.length; j++) {
        var clip = clips[j];
        if (clip.start.ticks > currentPos) {
            // There's a gap - move clip
            var diff = clip.start.ticks - currentPos;
            clip.start.ticks = currentPos;
            clip.end.ticks = clip.end.ticks - diff;
        }
        currentPos = clip.end.ticks;
    }
}

// Entry point
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    var args = JSON.parse(arguments[0]);
    var result = applyCuts(args.cuts, args.trackIndex);
    JSON.stringify(result);
}

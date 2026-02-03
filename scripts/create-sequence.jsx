/**
 * Create a new sequence in Premiere Pro
 *
 * @param {string} name - Sequence name
 * @param {string} preset - Preset name (optional)
 * @param {Object} settings - Optional custom settings
 * @returns {Object} Result with sequence info
 */
function createSequence(name, preset, settings) {
    var project = app.project;

    // Default sequence name
    var seqName = name || "Sequence_" + new Date().getTime();

    try {
        var newSeq;

        // Try to create from preset if specified
        if (preset) {
            // Look for preset in system presets
            var presetPath = findPreset(preset);
            if (presetPath) {
                newSeq = project.createNewSequenceFromPresetPath(seqName, presetPath);
            }
        }

        // Fallback to default creation
        if (!newSeq) {
            // Create using project item if available
            var firstVideo = findFirstVideoClip(project.rootItem);
            if (firstVideo) {
                newSeq = project.createNewSequenceFromClips(seqName, [firstVideo]);
            } else {
                // Create empty sequence with default settings
                newSeq = app.project.createNewSequence(seqName, "premiere-mcp-sequence");
            }
        }

        if (newSeq) {
            // Apply custom settings if provided
            if (settings) {
                applySequenceSettings(newSeq, settings);
            }

            return {
                success: true,
                sequenceId: newSeq.sequenceID,
                name: newSeq.name,
                duration: newSeq.end,
                videoTracks: newSeq.videoTracks.numTracks,
                audioTracks: newSeq.audioTracks.numTracks
            };
        } else {
            return {
                success: false,
                error: "Failed to create sequence"
            };
        }
    } catch (e) {
        return {
            success: false,
            error: e.toString()
        };
    }
}

/**
 * Find a sequence preset by name
 */
function findPreset(presetName) {
    // Common preset paths
    var presetPaths = [
        "/Applications/Adobe Premiere Pro 2024/Adobe Premiere Pro 2024.app/Contents/Settings/SequencePresets/",
        "C:\\Program Files\\Adobe\\Adobe Premiere Pro 2024\\Settings\\SequencePresets\\"
    ];

    // Map common names to files
    var presetMap = {
        "1080p30": "1080p30.sqpreset",
        "1080p60": "1080p60.sqpreset",
        "4k30": "4k30.sqpreset",
        "vertical": "1080x1920.sqpreset"
    };

    var presetFile = presetMap[presetName.toLowerCase()] || presetName + ".sqpreset";

    for (var i = 0; i < presetPaths.length; i++) {
        var fullPath = presetPaths[i] + presetFile;
        var f = new File(fullPath);
        if (f.exists) {
            return fullPath;
        }
    }

    return null;
}

/**
 * Find first video clip in project
 */
function findFirstVideoClip(parentItem) {
    for (var i = 0; i < parentItem.children.numItems; i++) {
        var child = parentItem.children[i];
        if (child.type === ProjectItemType.CLIP) {
            // Check if it's a video clip
            if (child.getMediaPath && child.getMediaPath()) {
                return child;
            }
        } else if (child.type === ProjectItemType.BIN) {
            var found = findFirstVideoClip(child);
            if (found) return found;
        }
    }
    return null;
}

/**
 * Apply custom settings to sequence
 */
function applySequenceSettings(sequence, settings) {
    // Settings can include:
    // - frameRate
    // - width, height
    // - pixelAspectRatio
    // These are read-only after creation in most cases
    // but we can add tracks if needed

    if (settings.videoTracks) {
        for (var i = sequence.videoTracks.numTracks; i < settings.videoTracks; i++) {
            sequence.videoTracks.addTrack();
        }
    }

    if (settings.audioTracks) {
        for (var j = sequence.audioTracks.numTracks; j < settings.audioTracks; j++) {
            sequence.audioTracks.addTrack();
        }
    }
}

// Entry point
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    var args = JSON.parse(arguments[0]);
    var result = createSequence(args.name, args.preset, args.settings);
    JSON.stringify(result);
}

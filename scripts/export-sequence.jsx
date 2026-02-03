/**
 * Export active sequence using Adobe Media Encoder
 *
 * @param {string} outputPath - Full output file path
 * @param {string} preset - Export preset name or path
 * @param {Object} options - Export options
 *   - format: 'h264', 'prores', 'dnxhd', etc.
 *   - quality: 'high', 'medium', 'low'
 *   - inPoint: Start time in seconds (optional)
 *   - outPoint: End time in seconds (optional)
 *   - useProxy: Use proxy media if available
 * @returns {Object} Result with export job info
 */
function exportSequence(outputPath, preset, options) {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    options = options || {};

    try {
        // Get preset path
        var presetPath = resolvePreset(preset, options);

        if (!presetPath) {
            return {
                success: false,
                error: "Could not find export preset: " + preset
            };
        }

        // Set in/out points if specified
        if (typeof options.inPoint !== 'undefined') {
            seq.setInPoint(options.inPoint);
        }
        if (typeof options.outPoint !== 'undefined') {
            seq.setOutPoint(options.outPoint);
        }

        // Queue export to Adobe Media Encoder
        var jobId = app.encoder.encodeSequence(
            seq,
            outputPath,
            presetPath,
            app.encoder.ENCODE_WORKAREA, // Use work area if set, otherwise full
            1 // removeOnComplete flag
        );

        if (jobId) {
            // Start the encoder queue
            app.encoder.startBatch();

            return {
                success: true,
                jobId: jobId,
                outputPath: outputPath,
                preset: preset,
                sequenceName: seq.name,
                duration: seq.end
            };
        } else {
            return {
                success: false,
                error: "Failed to queue export job"
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
 * Resolve preset name to file path
 */
function resolvePreset(preset, options) {
    // If it's already a full path, use it
    if (preset && (preset.indexOf('/') >= 0 || preset.indexOf('\\') >= 0)) {
        var f = new File(preset);
        if (f.exists) {
            return preset;
        }
    }

    // Common preset locations
    var presetPaths = [
        "/Applications/Adobe Premiere Pro 2024/Adobe Premiere Pro 2024.app/Contents/MediaIO/systempresets/",
        "C:\\Program Files\\Adobe\\Adobe Premiere Pro 2024\\MediaIO\\systempresets\\"
    ];

    // Map preset names to file paths
    var presetMap = {
        // H.264 presets
        'h264_high': '_H.264/_H.264 - Match Source - High Bitrate.epr',
        'h264_medium': '_H.264/_H.264 - Match Source - Medium Bitrate.epr',
        'h264_youtube_1080': '_H.264/YouTube 1080p HD.epr',
        'h264_youtube_4k': '_H.264/YouTube 2160p 4K.epr',
        'h264_vimeo_1080': '_H.264/Vimeo 1080p HD.epr',

        // ProRes presets
        'prores_422': 'QuickTime/Apple ProRes 422.epr',
        'prores_422hq': 'QuickTime/Apple ProRes 422 HQ.epr',
        'prores_4444': 'QuickTime/Apple ProRes 4444.epr',

        // Vertical/shorts
        'h264_vertical': '_H.264/_H.264 - Match Source - High Bitrate.epr',

        // Match source
        'match_source': '_H.264/_H.264 - Match Source - High Bitrate.epr'
    };

    // Determine preset file
    var presetFile = preset;

    // Use options to build preset name
    if (!preset && options.format) {
        var quality = options.quality || 'high';
        var key = options.format.toLowerCase() + '_' + quality;
        presetFile = presetMap[key] || presetMap['h264_high'];
    } else if (preset) {
        presetFile = presetMap[preset.toLowerCase()] || preset;
    }

    // Search in preset paths
    for (var i = 0; i < presetPaths.length; i++) {
        var fullPath = presetPaths[i] + presetFile;
        var f = new File(fullPath);
        if (f.exists) {
            return fullPath;
        }
    }

    // Return default if nothing found
    return null;
}

/**
 * Export work area only
 */
function exportWorkArea(outputPath, preset) {
    return exportSequence(outputPath, preset, {
        useWorkArea: true
    });
}

/**
 * Export clips (in/out marked region)
 */
function exportMarkedRegion(outputPath, preset, inPoint, outPoint) {
    return exportSequence(outputPath, preset, {
        inPoint: inPoint,
        outPoint: outPoint
    });
}

/**
 * Export multiple ranges as separate files
 *
 * @param {string} outputDir - Output directory
 * @param {Array} ranges - Array of {start, end, name} objects
 * @param {string} preset - Export preset
 * @returns {Object} Result with export jobs
 */
function exportRanges(outputDir, ranges, preset) {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var jobs = [];
    var errors = [];

    for (var i = 0; i < ranges.length; i++) {
        var range = ranges[i];
        var name = range.name || "clip_" + (i + 1);
        var outputPath = outputDir + "/" + name + ".mp4";

        var result = exportSequence(outputPath, preset, {
            inPoint: range.start,
            outPoint: range.end
        });

        if (result.success) {
            jobs.push({
                name: name,
                jobId: result.jobId,
                outputPath: outputPath,
                start: range.start,
                end: range.end
            });
        } else {
            errors.push({
                name: name,
                error: result.error
            });
        }
    }

    return {
        success: jobs.length > 0,
        jobsQueued: jobs.length,
        jobs: jobs,
        errors: errors
    };
}

/**
 * Check encoder status
 */
function getEncoderStatus() {
    try {
        return {
            success: true,
            encoding: app.encoder.encodeProgress,
            available: true
        };
    } catch (e) {
        return {
            success: false,
            error: "Media Encoder not available",
            available: false
        };
    }
}

// Entry point
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    var args = JSON.parse(arguments[0]);
    var result;

    switch (args.action) {
        case 'export':
            result = exportSequence(args.outputPath, args.preset, args.options);
            break;
        case 'exportWorkArea':
            result = exportWorkArea(args.outputPath, args.preset);
            break;
        case 'exportMarked':
            result = exportMarkedRegion(args.outputPath, args.preset, args.inPoint, args.outPoint);
            break;
        case 'exportRanges':
            result = exportRanges(args.outputDir, args.ranges, args.preset);
            break;
        case 'status':
            result = getEncoderStatus();
            break;
        default:
            result = exportSequence(args.outputPath, args.preset, args.options || args);
    }

    JSON.stringify(result);
}

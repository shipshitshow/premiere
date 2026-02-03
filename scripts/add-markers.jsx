/**
 * Add markers to the active sequence
 *
 * @param {Array} markers - Array of marker objects {time, name, comment, color}
 *   - time: Position in seconds
 *   - name: Marker name (optional)
 *   - comment: Marker comment/notes (optional)
 *   - color: Marker color index 0-7 (optional, default 0)
 *     0=Green, 1=Red, 2=Purple, 3=Orange, 4=Yellow, 5=White, 6=Blue, 7=Cyan
 * @returns {Object} Result with added markers info
 */
function addMarkers(markers) {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var added = [];
    var errors = [];

    for (var i = 0; i < markers.length; i++) {
        var markerData = markers[i];

        try {
            var marker = seq.markers.createMarker(markerData.time);

            if (markerData.name) {
                marker.name = markerData.name;
            }

            if (markerData.comment) {
                marker.comments = markerData.comment;
            }

            if (typeof markerData.color !== 'undefined') {
                marker.setColorByIndex(markerData.color);
            }

            // Set marker type if specified
            if (markerData.type === 'chapter') {
                marker.type = 'Chapter';
            }

            added.push({
                time: markerData.time,
                name: marker.name,
                guid: marker.guid
            });

        } catch (e) {
            errors.push({
                marker: markerData,
                error: e.toString()
            });
        }
    }

    return {
        success: added.length > 0,
        addedCount: added.length,
        added: added,
        errors: errors,
        totalMarkers: seq.markers.numMarkers
    };
}

/**
 * Add markers from clip detection results
 *
 * @param {Array} clips - Array of detected clips with start/end times and metadata
 * @returns {Object} Result with markers at clip boundaries
 */
function addClipMarkers(clips) {
    var markers = [];

    for (var i = 0; i < clips.length; i++) {
        var clip = clips[i];

        // Add marker at clip start
        markers.push({
            time: clip.start,
            name: "Clip " + (i + 1) + " Start",
            comment: clip.hook || clip.reason || "",
            color: 1  // Red for clip starts
        });

        // Add marker at clip end
        markers.push({
            time: clip.end,
            name: "Clip " + (i + 1) + " End",
            comment: "Score: " + (clip.score || "N/A"),
            color: 0  // Green for clip ends
        });
    }

    return addMarkers(markers);
}

/**
 * Add chapter markers from transcript segments
 *
 * @param {Array} chapters - Array of chapter objects {time, title}
 * @returns {Object} Result with chapter markers
 */
function addChapterMarkers(chapters) {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var added = [];
    var errors = [];

    for (var i = 0; i < chapters.length; i++) {
        var chapter = chapters[i];

        try {
            var marker = seq.markers.createMarker(chapter.time);
            marker.name = chapter.title;
            marker.type = 'Chapter';
            marker.setColorByIndex(5);  // White for chapters

            added.push({
                time: chapter.time,
                title: chapter.title,
                guid: marker.guid
            });

        } catch (e) {
            errors.push({
                chapter: chapter,
                error: e.toString()
            });
        }
    }

    return {
        success: added.length > 0,
        addedCount: added.length,
        added: added,
        errors: errors
    };
}

/**
 * Clear all markers from sequence
 *
 * @returns {Object} Result with cleared count
 */
function clearMarkers() {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var count = seq.markers.numMarkers;

    // Remove markers from end to preserve indices
    for (var i = count - 1; i >= 0; i--) {
        var marker = seq.markers[i];
        marker.remove();
    }

    return {
        success: true,
        clearedCount: count
    };
}

/**
 * List all markers in sequence
 *
 * @returns {Object} Result with markers array
 */
function listMarkers() {
    var seq = app.project.activeSequence;

    if (!seq) {
        return {
            success: false,
            error: "No active sequence"
        };
    }

    var markerList = [];

    for (var i = 0; i < seq.markers.numMarkers; i++) {
        var marker = seq.markers[i];
        markerList.push({
            index: i,
            time: marker.start.seconds,
            name: marker.name,
            comments: marker.comments,
            type: marker.type,
            guid: marker.guid
        });
    }

    return {
        success: true,
        markers: markerList,
        count: markerList.length
    };
}

// Entry point
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    var args = JSON.parse(arguments[0]);
    var result;

    switch (args.action) {
        case 'add':
            result = addMarkers(args.markers);
            break;
        case 'addClips':
            result = addClipMarkers(args.clips);
            break;
        case 'addChapters':
            result = addChapterMarkers(args.chapters);
            break;
        case 'clear':
            result = clearMarkers();
            break;
        case 'list':
            result = listMarkers();
            break;
        default:
            result = addMarkers(args.markers || args);
    }

    JSON.stringify(result);
}

/**
 * Batch operations for Premiere Pro automation
 * Combines multiple operations into efficient workflows
 */

/**
 * Full import and sequence creation workflow
 *
 * @param {string[]} filePaths - Files to import
 * @param {string} sequenceName - Name for new sequence
 * @param {Object} options - Workflow options
 * @returns {Object} Result with sequence and import info
 */
function importAndCreateSequence(filePaths, sequenceName, options) {
  options = options || {}

  // Import media
  var importResult = importMedia(filePaths, options.binName)

  if (!importResult.success) {
    return {
      success: false,
      error: 'Import failed',
      importResult: importResult,
    }
  }

  // Find imported items
  var project = app.project
  var importedItems = findImportedItems(project.rootItem, filePaths)

  if (importedItems.length === 0) {
    return {
      success: false,
      error: 'No items found after import',
    }
  }

  // Create sequence from first video
  var seq
  var seqName = sequenceName || 'Imported_' + new Date().getTime()

  try {
    seq = project.createNewSequenceFromClips(seqName, importedItems)
  } catch (e) {
    // Fallback to empty sequence
    seq = project.createNewSequence(seqName, 'premiere-mcp')

    // Insert clips manually
    for (var i = 0; i < importedItems.length; i++) {
      insertClipAtEnd(seq, importedItems[i])
    }
  }

  return {
    success: true,
    sequenceId: seq.sequenceID,
    sequenceName: seq.name,
    importedCount: importResult.importedCount,
    clipCount: importedItems.length,
  }
}

/**
 * Apply silence cuts and export workflow
 *
 * @param {Array} cuts - Silence segments to remove
 * @param {string} outputPath - Export path
 * @param {string} preset - Export preset
 * @returns {Object} Result with cut and export info
 */
function cutAndExport(cuts, outputPath, preset) {
  // Apply cuts
  var cutResult = applyCuts(cuts)

  if (!cutResult.success && cutResult.errors.length > 0) {
    return {
      success: false,
      error: 'Cut operation had errors',
      cutResult: cutResult,
    }
  }

  // Export
  var exportResult = exportSequence(outputPath, preset)

  return {
    success: exportResult.success,
    cutsApplied: cutResult.removedCount,
    exportJobId: exportResult.jobId,
    outputPath: outputPath,
  }
}

/**
 * Full processing workflow: import, create sequence, apply cuts, add markers, export
 *
 * @param {Object} workflow - Workflow configuration
 *   - filePaths: Files to import
 *   - sequenceName: Sequence name
 *   - cuts: Silence segments to remove (optional)
 *   - markers: Markers to add (optional)
 *   - clips: Clip markers to add (optional)
 *   - outputPath: Export path
 *   - preset: Export preset
 * @returns {Object} Result with full workflow info
 */
function runFullWorkflow(workflow) {
  var results = {
    steps: [],
    success: true,
  }

  // Step 1: Import
  if (workflow.filePaths && workflow.filePaths.length > 0) {
    var importResult = importAndCreateSequence(workflow.filePaths, workflow.sequenceName, {
      binName: workflow.binName,
    })
    results.steps.push({ step: 'import', result: importResult })

    if (!importResult.success) {
      results.success = false
      return results
    }
  }

  // Step 2: Apply cuts
  if (workflow.cuts && workflow.cuts.length > 0) {
    var cutResult = applyCuts(workflow.cuts)
    results.steps.push({ step: 'cuts', result: cutResult })
  }

  // Step 3: Add markers
  if (workflow.markers && workflow.markers.length > 0) {
    var markerResult = addMarkers(workflow.markers)
    results.steps.push({ step: 'markers', result: markerResult })
  }

  // Step 4: Add clip markers
  if (workflow.clips && workflow.clips.length > 0) {
    var clipMarkerResult = addClipMarkers(workflow.clips)
    results.steps.push({ step: 'clipMarkers', result: clipMarkerResult })
  }

  // Step 5: Export
  if (workflow.outputPath) {
    var exportResult = exportSequence(workflow.outputPath, workflow.preset, workflow.exportOptions)
    results.steps.push({ step: 'export', result: exportResult })
    results.exportJobId = exportResult.jobId
  }

  return results
}

/**
 * Find imported items by file path
 */
function findImportedItems(parentItem, filePaths) {
  var items = []

  for (var i = 0; i < parentItem.children.numItems; i++) {
    var child = parentItem.children[i]

    if (child.type === ProjectItemType.CLIP) {
      var mediaPath = child.getMediaPath ? child.getMediaPath() : null
      if (mediaPath) {
        for (var j = 0; j < filePaths.length; j++) {
          if (mediaPath.indexOf(getFileName(filePaths[j])) >= 0) {
            items.push(child)
            break
          }
        }
      }
    } else if (child.type === ProjectItemType.BIN) {
      var subItems = findImportedItems(child, filePaths)
      items = items.concat(subItems)
    }
  }

  return items
}

/**
 * Insert clip at end of sequence
 */
function insertClipAtEnd(sequence, projectItem) {
  var videoTrack = sequence.videoTracks[0]
  var audioTrack = sequence.audioTracks[0]

  var insertTime = sequence.end

  try {
    // Insert video
    videoTrack.insertClip(projectItem, insertTime)

    // Audio is usually linked, but can insert separately if needed
  } catch (e) {
    // Item might not be video-compatible
  }
}

/**
 * Get sequence info
 */
function getSequenceInfo() {
  var seq = app.project.activeSequence

  if (!seq) {
    return {
      success: false,
      error: 'No active sequence',
    }
  }

  var videoClips = 0
  var audioClips = 0

  for (var v = 0; v < seq.videoTracks.numTracks; v++) {
    videoClips += seq.videoTracks[v].clips.numItems
  }

  for (var a = 0; a < seq.audioTracks.numTracks; a++) {
    audioClips += seq.audioTracks[a].clips.numItems
  }

  return {
    success: true,
    name: seq.name,
    sequenceId: seq.sequenceID,
    duration: seq.end,
    videoTracks: seq.videoTracks.numTracks,
    audioTracks: seq.audioTracks.numTracks,
    videoClips: videoClips,
    audioClips: audioClips,
    markers: seq.markers.numMarkers,
    inPoint: seq.getInPoint(),
    outPoint: seq.getOutPoint(),
  }
}

/**
 * Get project info
 */
function getProjectInfo() {
  var project = app.project

  return {
    success: true,
    name: project.name,
    path: project.path,
    sequences: countSequences(project.rootItem),
    items: project.rootItem.children.numItems,
    activeSequence: project.activeSequence ? project.activeSequence.name : null,
  }
}

/**
 * Count sequences in project
 */
function countSequences(parentItem) {
  var count = 0

  for (var i = 0; i < parentItem.children.numItems; i++) {
    var child = parentItem.children[i]
    if (child.type === ProjectItemType.SEQUENCE) {
      count++
    } else if (child.type === ProjectItemType.BIN) {
      count += countSequences(child)
    }
  }

  return count
}

// Import helper functions from other scripts
function importMedia(filePaths, binName) {
  // Inline import logic or use $.evalFile to include
  var project = app.project
  var targetBin = binName ? findOrCreateBin(binName) : project.rootItem
  var imported = []

  for (var i = 0; i < filePaths.length; i++) {
    try {
      project.importFiles([filePaths[i]], true, targetBin, false)
      imported.push(filePaths[i])
    } catch (e) {
      // Continue on error
    }
  }

  return {
    success: imported.length > 0,
    importedCount: imported.length,
  }
}

function findOrCreateBin(name) {
  var project = app.project
  var root = project.rootItem

  for (var i = 0; i < root.children.numItems; i++) {
    var child = root.children[i]
    if (child.type === ProjectItemType.BIN && child.name === name) {
      return child
    }
  }

  return root.createBin(name)
}

function getFileName(path) {
  var parts = path.split(/[\/\\]/)
  return parts[parts.length - 1]
}

// Entry point
if (typeof arguments !== 'undefined' && arguments.length > 0) {
  var args = JSON.parse(arguments[0])
  var result

  switch (args.action) {
    case 'importAndCreate':
      result = importAndCreateSequence(args.filePaths, args.sequenceName, args.options)
      break
    case 'cutAndExport':
      result = cutAndExport(args.cuts, args.outputPath, args.preset)
      break
    case 'fullWorkflow':
      result = runFullWorkflow(args.workflow || args)
      break
    case 'sequenceInfo':
      result = getSequenceInfo()
      break
    case 'projectInfo':
      result = getProjectInfo()
      break
    default:
      result = { success: false, error: 'Unknown action: ' + args.action }
  }

  JSON.stringify(result)
}

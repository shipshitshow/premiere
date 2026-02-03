/**
 * Import media files into Premiere Pro project
 * Called by adobe-mcp with file paths
 *
 * @param {string[]} filePaths - Array of file paths to import
 * @param {string} binName - Optional bin name to import into
 * @returns {Object} Result with imported items
 */
function importMedia(filePaths, binName) {
    var project = app.project;
    var rootItem = project.rootItem;
    var targetBin = rootItem;

    // Create or find target bin if specified
    if (binName) {
        var existingBin = findBinByName(rootItem, binName);
        if (existingBin) {
            targetBin = existingBin;
        } else {
            targetBin = rootItem.createBin(binName);
        }
    }

    var imported = [];
    var errors = [];

    for (var i = 0; i < filePaths.length; i++) {
        var filePath = filePaths[i];
        try {
            var importSuccess = project.importFiles([filePath],
                true,  // suppress UI
                targetBin,
                false  // import as numbered stills
            );

            if (importSuccess) {
                imported.push({
                    path: filePath,
                    name: getFileName(filePath)
                });
            } else {
                errors.push({
                    path: filePath,
                    error: "Import failed"
                });
            }
        } catch (e) {
            errors.push({
                path: filePath,
                error: e.toString()
            });
        }
    }

    return {
        success: imported.length > 0,
        imported: imported,
        importedCount: imported.length,
        errors: errors,
        targetBin: binName || "Root"
    };
}

/**
 * Find a bin by name recursively
 */
function findBinByName(parentItem, name) {
    for (var i = 0; i < parentItem.children.numItems; i++) {
        var child = parentItem.children[i];
        if (child.type === ProjectItemType.BIN && child.name === name) {
            return child;
        }
        if (child.type === ProjectItemType.BIN) {
            var found = findBinByName(child, name);
            if (found) return found;
        }
    }
    return null;
}

/**
 * Get filename from path
 */
function getFileName(filePath) {
    var parts = filePath.split(/[\/\\]/);
    return parts[parts.length - 1];
}

// Entry point for MCP calls
// Arguments passed via app.parameters or evaluated directly
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    var args = JSON.parse(arguments[0]);
    var result = importMedia(args.filePaths, args.binName);
    JSON.stringify(result);
}

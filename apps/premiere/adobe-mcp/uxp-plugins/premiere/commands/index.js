/* MIT License
 *
 * Copyright (c) 2025 Mike Chambers
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

const fs = require("uxp").storage.localFileSystem;
//const openfs = require('fs')
const app = require("premierepro");
const {consts, BLEND_MODES} = require("./consts.js")

const createSequenceFromMedia = async (command) => {

    let options = command.options

    let itemNames = options.itemNames
    let sequenceName = options.sequenceName

    let project = await app.Project.getActiveProject()

    let found = false
    try {
        await findProjectItem(sequenceName, project)
        found  = true
    } catch {
        //do nothing
    }

    if(found) {
        throw Error(`createSequenceFromMedia : sequence name [${sequenceName}] is already in use`)
    }

    let items = []
    for (const name of itemNames) {

        //this is a little inefficient
        let insertItem = await findProjectItem(name, project)
        items.push(insertItem)
    }


    let root = await project.getRootItem()
    
    let sequence = await project.createSequenceFromMedia(sequenceName, items, root)

    await _setActiveSequence(sequence)
}

const findSequenceByName = async (sequenceName) => {
    let project = await app.Project.getActiveProject()
    let sequences = await project.getSequences()

    for(const s of sequences) {
        if(s.name == sequenceName) {
            return s
        }
    }

    return
}

const getProjectInfo = async (command) => {
    const project = await app.Project.getActiveProject()

    if (!project) {
        return { hasProject: false }
    }

    const sequences = await project.getSequences()
    const activeSeq = await project.getActiveSequence()

    return {
        hasProject: true,
        sequenceCount: sequences.length,
        activeSequenceId: activeSeq ? activeSeq.guid.toString() : null,
        activeSequenceName: activeSeq ? activeSeq.name : null
    }
}

const getFullProjectData = async (command) => {
    // This returns the full sequence and project item data
    // Use sparingly as it can be large for big projects
    return {
        sequences: await getSequences(),
        projectItems: await getProjectContentInfo()
    }
}

const _getSequenceFromId = async (id) => {
    let project = await app.Project.getActiveProject()

    let guid = app.Guid.fromString(id)
    let sequence = await project.getSequence(guid)

    if(!sequence) {
        throw new Error(`_getSequenceFromId : Could not find sequence with id : ${id}`)
    }

    return sequence
}


const _setActiveSequence = async (sequence) => {
    let project = await app.Project.getActiveProject()
    await project.setActiveSequence(sequence)

    let item = await findProjectItem(sequence.name, project)
    await app.SourceMonitor.openProjectItem(item)
}

const setActiveSequence = async (command) => {
    let options = command.options
    let id = options.sequenceId

    let sequence = await _getSequenceFromId(id)

    await _setActiveSequence(sequence)
}

const createProject = async (command) => {

    let options = command.options
    let path = options.path
    let name = options.name

    if (!path.endsWith('/')) {
        path = path + '/';
    }

    //todo: this will open a dialog if directory doesnt exist
    let project = await app.Project.createProject(`${path}${name}.prproj`) 


    if(!project) {
        throw new Error("createProject : Could not create project. Check that the directory path exists and try again.")
    }

    //create a default sequence and set it as active
    //let sequence = await project.createSequence("default")
    //await project.setActiveSequence(sequence)
}

const exportFrame = async (command) => {
    const options = command.options
    let id = options.sequenceId

    let sequence = await _getSequenceFromId(id)

    let size = await sequence.getFrameSize()

    let p = window.path.parse(options.filePath)

    let t = app.TickTime.createWithSeconds(options.seconds)

    let out = await app.Exporter.exportSequenceFrame(sequence, t, p.base, p.dir, size.width, size.height)

    let ps = `${p.dir}${window.path.sep}${p.base}`
    let outPath = `${ps}.png`

    if(!out) {
        throw new Error(`exportFrame : Could not save frame to [${outPath}]`);
    }
    //console.log(ps)
    //console.log(`${ps}.png`)

    //let tmp = await openfs.rename(`file:${ps}.png`, `file:${ps}`);

    return {"filePath": outPath}
}

const setAudioClipDisabled = async (command) => {

    let options = command.options
    let id = options.sequenceId

    let project = await app.Project.getActiveProject()
    let sequence = await _getSequenceFromId(id)

    if(!sequence) {
        throw new Error(`setAudioClipDisabled : Requires an active sequence.`)
    }

    let trackItem = await getAudioTrack(sequence, options.audioTrackIndex, options.trackItemIndex)

    execute(() => {
        let action = trackItem.createSetDisabledAction(options.disabled)
        return [action]
    }, project)

}

const setVideoClipDisabled = async (command) => {

    let options = command.options
    let id = options.sequenceId

    let project = await app.Project.getActiveProject()
    let sequence = await _getSequenceFromId(id)

    if(!sequence) {
        throw new Error(`setVideoClipDisabled : Requires an active sequence.`)
    }

    let trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    execute(() => {
        let action = trackItem.createSetDisabledAction(options.disabled)
        return [action]
    }, project)
}

const appendVideoTransition = async (command) => {

    let options = command.options
    let id = options.sequenceId

    let project = await app.Project.getActiveProject()
    let sequence = await _getSequenceFromId(id)

    if(!sequence) {
        throw new Error(`appendVideoTransition : Requires an active sequence.`)
    }

    let trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    let transition = await app.TransitionFactory.createVideoTransition(options.transitionName);

    let transitionOptions = new app.AddTransitionOptions()
    transitionOptions.setApplyToStart(false)

    const time = await app.TickTime.createWithSeconds(options.duration)
    transitionOptions.setDuration(time)
    transitionOptions.setTransitionAlignment(options.clipAlignment)

    execute(() => {
        let action = trackItem.createAddVideoTransitionAction(transition, transitionOptions)
        return [action]
    }, project)
}


const setParam = async(trackItem, componentName, paramName, value) => {

    const project = await app.Project.getActiveProject()

    let param = await getParam(trackItem, componentName, paramName)

    let keyframe = await param.createKeyframe(value)

    execute(() => {
        let action = param.createSetValueAction(keyframe);
        return [action]
    }, project)
}

const getParam = async (trackItem, componentName, paramName) => {

    let components = await trackItem.getComponentChain()

    const count = components.getComponentCount()
    for(let i = 0; i < count; i++) {
        const component =  components.getComponentAtIndex(i)

        //search for match name
        //component name AE.ADBE Opacity
        const matchName = await component.getMatchName()
        
        
        if(matchName == componentName) {
            console.log(matchName)
            let pCount = component.getParamCount()

            for (let j = 0; j < pCount; j++) {
                
                const param = component.getParam(j);

                console.log(param.type)
                console.log(param)
                if(param.displayName == paramName) {
                    return param
                }

            }
        }
    }
}


const setVideoClipProperties = async (command) => {

    const options = command.options
    let id = options.sequenceId

    let project = await app.Project.getActiveProject()
    let sequence = await _getSequenceFromId(id)

    if(!sequence) {
        throw new Error(`setVideoClipProperties : Requires an active sequence.`)
    }

    let trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    let opacityParam = await getParam(trackItem, "AE.ADBE Opacity", "Opacity")
    let opacityKeyframe = await opacityParam.createKeyframe(options.opacity)

    let blendModeParam = await getParam(trackItem, "AE.ADBE Opacity", "Blend Mode")

    let mode = BLEND_MODES[options.blendMode.toUpperCase()]
    let blendModeKeyframe = await blendModeParam.createKeyframe(mode)

    execute(() => {
        let opacityAction = opacityParam.createSetValueAction(opacityKeyframe);
        let blendModeAction = blendModeParam.createSetValueAction(blendModeKeyframe);
        return [opacityAction, blendModeAction]
    }, project)

    // /AE.ADBE Opacity
    //Opacity
    //Blend Mode

}

const appendVideoFilter = async (command) => {

    let options = command.options
    let id = options.sequenceId

    let sequence = await _getSequenceFromId(id)

    if(!sequence) {
        throw new Error(`appendVideoFilter : Requires an active sequence.`)
    }

    let trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    let effectName = options.effectName
    let properties = options.properties

    let d = await addEffect(trackItem, effectName)

    for(const p of properties) {
        console.log(p.value)
        await setParam(trackItem, effectName, p.name, p.value)
    }
}

const addEffect = async (trackItem, effectName) => {
    let project = await app.Project.getActiveProject()
    const effect = await app.VideoFilterFactory.createComponent(effectName);

    let componentChain = await trackItem.getComponentChain()
    
    execute(() => {
        let action = componentChain.createAppendComponentAction(
            effect, 0)//todo, second isnt needed
        return [action]
    }, project)
}


const setAudioTrackMute = async (command) => {

    let options = command.options
    let id = options.sequenceId

    let sequence = await _getSequenceFromId(id)

    let track = await sequence.getAudioTrack(options.audioTrackIndex)
    track.setMute(options.mute)
}


const findProjectItem = async (itemName, project) => {
    let root = await project.getRootItem()
    let rootItems = await root.getItems()

    let insertItem;
    for(const item of rootItems) {
        if (item.name == itemName) {
            insertItem = item;
            break;
        }
    }

    if(!insertItem) {
        throw new Error(
            `addItemToSequence : Could not find item named ${itemName}`
        );
    }

    return insertItem
}

//note: right now, we just always add to the active sequence. Need to add support
//for specifying sequence
const addMediaToSequence = async (command) => {

    let options = command.options
    let itemName = options.itemName
    let id = options.sequenceId

    let project = await app.Project.getActiveProject()
    let sequence = await _getSequenceFromId(id)

    let insertItem = await findProjectItem(itemName, project)

    let editor = await app.SequenceEditor.getEditor(sequence)
  
    const insertionTime = await app.TickTime.createWithTicks(options.insertionTimeTicks.toString());
    const videoTrackIndex = options.videoTrackIndex
    const audioTrackIndex = options.audioTrackIndex
  
    //not sure what this does
    const limitShift = false

    //let f = ((options.overwrite) ? editor.createOverwriteItemAction : editor.createInsertProjectItemAction).bind(editor)
    //let action = f(insertItem, insertionTime, videoTrackIndex, audioTrackIndex, limitShift)
    execute(() => {
        let action = editor.createOverwriteItemAction(insertItem, insertionTime, videoTrackIndex, audioTrackIndex)
        return [action]
    }, project)  
}

const execute = (getActions, project, undoLabel = "MCP Action") => {
    try {
        project.lockedAccess( () => {
            project.executeTransaction((compoundAction) => {
                let actions = getActions()

                for(const a of actions) {
                    compoundAction.addAction(a);
                }
            }, undoLabel);
          });
    } catch (e) {
        throw new Error(`Error executing locked transaction : ${e}`);
    }
}

const executeAction = (project, action) => {
    try {
        project.lockedAccess( () => {
            project.executeTransaction((compoundAction) => {
                compoundAction.addAction(action);
            });
          });
    } catch (e) {
        throw new Error(`Error executing locked transaction : ${e}`);
    }
};

const importMedia = async (command) => {

    let options = command.options
    let paths = command.options.filePaths

    let project = await app.Project.getActiveProject()

    let root = await project.getRootItem()
    let originalItems = await root.getItems()

    //import everything into root
    let rootFolderItems = await project.getRootItem()


    let success = await project.importFiles(paths, true, rootFolderItems)
    //TODO: what is not success?

    let updatedItems = await root.getItems()
    
    const addedItems = updatedItems.filter(
        updatedItem => !originalItems.some(originalItem => originalItem.name === updatedItem.name)
      );
      
    let addedProjectItems = [];
    for (const p of addedItems) { 
        addedProjectItems.push({ name: p.name });
    }
    
    return { addedProjectItems };
}


const getAudioTracks = async (sequence) => {
    let audioCount = await sequence.getAudioTrackCount()

    let audioTracks = []
    for(let i = 0; i < audioCount; i++) {
        let audioTrack = await sequence.getAudioTrack(i)

        let track = {
            index:i,
            tracks:[]
        }

        let clips = await audioTrack.getTrackItems(1, false)


        if(clips.length === 0) {
            continue
        }

        let k = 0
        for (const c of clips) {
            let startTimeTicks = (await c.getStartTime()).ticks
            let endTimeTicks = (await c.getEndTime()).ticks
            let durationTicks = (await c.getDuration()).ticks
            let durationSeconds = (await c.getDuration()).seconds
            let name = (await c.getProjectItem()).name
            let type = await c.getType()
            let index = k++

            track.tracks.push({
                startTimeTicks,
                endTimeTicks,
                durationTicks,
                durationSeconds,
                name,
                type,
                index
            })
        }

        audioTracks.push(track)
    }
    return audioTracks
}

const getSequences = async () => {
    let project = await app.Project.getActiveProject()
    let active = await project.getActiveSequence()

    let sequences = await project.getSequences()

    let out = []
    for(const sequence of sequences) {
        let size = await sequence.getFrameSize()
        //let settings = await sequence.getSettings()
    
        //let projectItem = await sequence.getProjectItem()
        //let name = projectItem.name
        let name = sequence.name
        let id = sequence.guid.toString()
    
        let videoTracks = await getVideoTracks(sequence)
        let audioTracks = await getAudioTracks(sequence)
    
        let isActive = active == sequence

        out.push( {
            isActive,
            name,
            id,
            frameSize:{width:size.width, height:size.height},
            videoTracks,
            audioTracks
        })
    }

    return out
}

const getVideoTracks = async (sequence) => {
    let videoCount = await sequence.getVideoTrackCount()

    let videoTracks = []
    for(let i = 0; i < videoCount; i++) {
        let videoTrack = await sequence.getVideoTrack(i)

        let track = {
            index:i,
            tracks:[]
        }

        let clips = await videoTrack.getTrackItems(1, false)


        if(clips.length === 0) {
            continue
        }


        let k = 0;
        for (const c of clips) {
            let startTimeTicks = (await c.getStartTime()).ticks
            let endTimeTicks = (await c.getEndTime()).ticks
            let durationTicks = (await c.getDuration()).ticks
            let durationSeconds = (await c.getDuration()).seconds
            let name = (await c.getProjectItem()).name
            let type = await c.getType()
            let index = k++

            track.tracks.push({
                startTimeTicks,
                endTimeTicks,
                durationTicks,
                durationSeconds,
                name,
                type,
                index
            })
        }
        
        videoTracks.push(track)
    }
    return videoTracks
}

const getAudioTrack = async (sequence, trackIndex, clipIndex) => {

    //todo: pass this in
    let audioTrack = await sequence.getAudioTrack(trackIndex)
 
    if(!audioTrack) {
        throw new Error(`getAudioTrack : audioTrackIndex [${trackIndex}] does not exist`)
    }


    let trackItems = await audioTrack.getTrackItems(1, false)

    let trackItem;
    let i = 0
    for(const t of trackItems) {
        let index = i++
        if(index === clipIndex) {
            trackItem = t
            break
        }
    }
    if(!trackItem) {
        throw new Error(`getAudioTrack : trackItemIndex [${clipIndex}] does not exist`)
    }

    return trackItem
}


const getVideoTrack = async (sequence, trackIndex, clipIndex) => {

    //todo: pass this in
    let videoTrack = await sequence.getVideoTrack(trackIndex)
 
    if(!videoTrack) {
        throw new Error(`getVideoTrack : videoTrackIndex [${trackIndex}] does not exist`)
    }

    let trackItems = await videoTrack.getTrackItems(1, false)

    let trackItem;
    let i = 0
    for(const t of trackItems) {
        let index = i++
        if(index === clipIndex) {
            trackItem = t
            break
        }
    }
    if(!trackItem) {
        throw new Error(`getVideoTrack : clipIndex [${clipIndex}] does not exist`)
    }

    return trackItem
}

const getProjectContentInfo = async () => {
    let project = await app.Project.getActiveProject()

    let root = await project.getRootItem()
    let items = await root.getItems()

    let out = []
    for(const item of items) {
        //todo: it would be good to get more data / info here
        out.push({name:item.name})
    }

    return out
}

const saveProject = async (command) => {
    let project = await app.Project.getActiveProject()

    project.save()
}

const saveProjectAs = async (command) => {
    let project = await app.Project.getActiveProject()

    const options = command.options;
    const filePath = options.filePath;

    project.saveAs(filePath)
}

const openProject = async (command) => {

    const options = command.options;
    const filePath = options.filePath;

    await app.Project.open(filePath);    
}

const parseAndRouteCommand = async (command) => {
    let action = command.action;

    let f = commandHandlers[action];

    if (typeof f !== "function") {
        throw new Error(`Unknown Command: ${action}`);
    }

    console.log(f.name)
    return f(command);
};

const splitVideoClip = async (command) => {
    const options = command.options
    const id = options.sequenceId
    const splitTimeTicks = options.splitTimeTicks
    const splitTimeSeconds = Number(BigInt(splitTimeTicks)) / 254016000000

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`splitVideoClip : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    // Get current clip timing
    const clipStart = await trackItem.getStartTime()
    const clipEnd = await trackItem.getEndTime()
    const clipInPoint = await trackItem.getInPoint()

    const splitTime = await app.TickTime.createWithTicks(splitTimeTicks.toString())

    // Validate split time is within clip bounds
    if (BigInt(splitTimeTicks) <= BigInt(clipStart.ticks) || BigInt(splitTimeTicks) >= BigInt(clipEnd.ticks)) {
        throw new Error(`splitVideoClip : Split time must be within clip bounds (${clipStart.ticks} - ${clipEnd.ticks})`)
    }

    // Calculate the offset into the source media where the split occurs
    const offsetFromStart = BigInt(splitTimeTicks) - BigInt(clipStart.ticks)
    const newInPointTicks = BigInt(clipInPoint.ticks) + offsetFromStart
    const newInPoint = await app.TickTime.createWithTicks(newInPointTicks.toString())

    // Get the editor for cloning
    const editor = await app.SequenceEditor.getEditor(sequence)

    execute(() => {
        const trimAction = trackItem.createSetEndAction(splitTime)
        const cloneAction = editor.createCloneTrackItemAction(
            trackItem, splitTime, 0, 0, true, false
        )
        return [trimAction, cloneAction]
    }, project, `Split video at ${splitTimeSeconds.toFixed(2)}s`)

    // Adjust the cloned clip's in-point
    const videoTrack = await sequence.getVideoTrack(options.videoTrackIndex)
    const trackItems = await videoTrack.getTrackItems(1, false)

    let clonedItem = null
    for (const item of trackItems) {
        const itemStart = await item.getStartTime()
        if (BigInt(itemStart.ticks) >= BigInt(splitTimeTicks)) {
            clonedItem = item
            break
        }
    }

    if (clonedItem) {
        execute(() => {
            const setInAction = clonedItem.createSetInPointAction(newInPoint)
            return [setInAction]
        }, project, `Adjust split clip in-point`)
    }

    return {
        message: "Clip split successfully",
        splitAt: splitTimeTicks
    }
}

// Combined split for both video and audio at once (single undo)
const splitClipAtTime = async (command) => {
    const options = command.options
    const id = options.sequenceId
    const splitTimeTicks = options.splitTimeTicks
    const splitTimeSeconds = Number(BigInt(splitTimeTicks)) / 254016000000

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`splitClipAtTime : Requires an active sequence.`)
    }

    const editor = await app.SequenceEditor.getEditor(sequence)
    const splitTime = await app.TickTime.createWithTicks(splitTimeTicks.toString())

    let actions = []
    let clipsToAdjust = []

    // Process video track if specified
    if (options.videoTrackIndex !== undefined && options.videoTrackIndex !== null) {
        const videoTrackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.videoClipIndex || 0)
        const vClipStart = await videoTrackItem.getStartTime()
        const vClipEnd = await videoTrackItem.getEndTime()
        const vClipInPoint = await videoTrackItem.getInPoint()

        if (BigInt(splitTimeTicks) > BigInt(vClipStart.ticks) && BigInt(splitTimeTicks) < BigInt(vClipEnd.ticks)) {
            const vOffsetFromStart = BigInt(splitTimeTicks) - BigInt(vClipStart.ticks)
            const vNewInPointTicks = BigInt(vClipInPoint.ticks) + vOffsetFromStart

            actions.push(videoTrackItem.createSetEndAction(splitTime))
            actions.push(editor.createCloneTrackItemAction(videoTrackItem, splitTime, 0, 0, true, false))

            clipsToAdjust.push({
                type: 'video',
                trackIndex: options.videoTrackIndex,
                newInPointTicks: vNewInPointTicks.toString()
            })
        }
    }

    // Process audio track if specified
    if (options.audioTrackIndex !== undefined && options.audioTrackIndex !== null) {
        const audioTrackItem = await getAudioTrack(sequence, options.audioTrackIndex, options.audioClipIndex || 0)
        const aClipStart = await audioTrackItem.getStartTime()
        const aClipEnd = await audioTrackItem.getEndTime()
        const aClipInPoint = await audioTrackItem.getInPoint()

        if (BigInt(splitTimeTicks) > BigInt(aClipStart.ticks) && BigInt(splitTimeTicks) < BigInt(aClipEnd.ticks)) {
            const aOffsetFromStart = BigInt(splitTimeTicks) - BigInt(aClipStart.ticks)
            const aNewInPointTicks = BigInt(aClipInPoint.ticks) + aOffsetFromStart

            actions.push(audioTrackItem.createSetEndAction(splitTime))
            actions.push(editor.createCloneTrackItemAction(audioTrackItem, splitTime, 0, 0, false, false))

            clipsToAdjust.push({
                type: 'audio',
                trackIndex: options.audioTrackIndex,
                newInPointTicks: aNewInPointTicks.toString()
            })
        }
    }

    if (actions.length === 0) {
        throw new Error(`splitClipAtTime : No clips found at the specified time`)
    }

    // Execute all splits in one transaction (single undo)
    execute(() => actions, project, `Split at ${splitTimeSeconds.toFixed(2)}s`)

    // Adjust in-points of cloned clips
    for (const clipInfo of clipsToAdjust) {
        let clonedItem = null

        if (clipInfo.type === 'video') {
            const track = await sequence.getVideoTrack(clipInfo.trackIndex)
            const items = await track.getTrackItems(1, false)
            for (const item of items) {
                const itemStart = await item.getStartTime()
                if (BigInt(itemStart.ticks) >= BigInt(splitTimeTicks)) {
                    clonedItem = item
                    break
                }
            }
        } else {
            const track = await sequence.getAudioTrack(clipInfo.trackIndex)
            const items = await track.getTrackItems(1, false)
            for (const item of items) {
                const itemStart = await item.getStartTime()
                if (BigInt(itemStart.ticks) >= BigInt(splitTimeTicks)) {
                    clonedItem = item
                    break
                }
            }
        }

        if (clonedItem) {
            const newInPoint = await app.TickTime.createWithTicks(clipInfo.newInPointTicks)
            execute(() => [clonedItem.createSetInPointAction(newInPoint)], project, `Adjust in-point`)
        }
    }

    return {
        message: "Clip(s) split successfully",
        splitAt: splitTimeTicks,
        tracksAffected: clipsToAdjust.length
    }
}

// Batch split - multiple splits in sequence
const batchSplitClips = async (command) => {
    const options = command.options
    const id = options.sequenceId
    const splitTimeTicksList = options.splitTimeTicksList // Array of tick values

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`batchSplitClips : Requires an active sequence.`)
    }

    // Sort split times in descending order (split from end to start to preserve indices)
    const sortedTimes = [...splitTimeTicksList].sort((a, b) => Number(BigInt(b) - BigInt(a)))

    let successCount = 0
    let errors = []

    for (const splitTimeTicks of sortedTimes) {
        try {
            // Create a sub-command for splitClipAtTime
            const subCommand = {
                options: {
                    sequenceId: id,
                    splitTimeTicks: splitTimeTicks,
                    videoTrackIndex: options.videoTrackIndex,
                    videoClipIndex: options.videoClipIndex,
                    audioTrackIndex: options.audioTrackIndex,
                    audioClipIndex: options.audioClipIndex
                }
            }
            await splitClipAtTime(subCommand)
            successCount++
        } catch (e) {
            errors.push({ time: splitTimeTicks, error: e.message })
        }
    }

    return {
        message: `Batch split completed: ${successCount}/${splitTimeTicksList.length} successful`,
        successCount,
        totalRequested: splitTimeTicksList.length,
        errors: errors.length > 0 ? errors : undefined
    }
}

const splitAudioClip = async (command) => {
    const options = command.options
    const id = options.sequenceId
    const splitTimeTicks = options.splitTimeTicks

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`splitAudioClip : Requires an active sequence.`)
    }

    const trackItem = await getAudioTrack(sequence, options.audioTrackIndex, options.trackItemIndex)

    const clipStart = await trackItem.getStartTime()
    const clipEnd = await trackItem.getEndTime()
    const clipInPoint = await trackItem.getInPoint()

    const splitTime = await app.TickTime.createWithTicks(splitTimeTicks.toString())

    if (BigInt(splitTimeTicks) <= BigInt(clipStart.ticks) || BigInt(splitTimeTicks) >= BigInt(clipEnd.ticks)) {
        throw new Error(`splitAudioClip : Split time must be within clip bounds (${clipStart.ticks} - ${clipEnd.ticks})`)
    }

    const offsetFromStart = BigInt(splitTimeTicks) - BigInt(clipStart.ticks)
    const newInPointTicks = BigInt(clipInPoint.ticks) + offsetFromStart
    const newInPoint = await app.TickTime.createWithTicks(newInPointTicks.toString())

    const editor = await app.SequenceEditor.getEditor(sequence)

    execute(() => {
        const trimAction = trackItem.createSetEndAction(splitTime)
        const cloneAction = editor.createCloneTrackItemAction(
            trackItem,
            splitTime,
            0,
            0,
            false,  // alignToVideo = false for audio
            false
        )
        return [trimAction, cloneAction]
    }, project)

    const audioTrack = await sequence.getAudioTrack(options.audioTrackIndex)
    const trackItems = await audioTrack.getTrackItems(1, false)

    let clonedItem = null
    for (const item of trackItems) {
        const itemStart = await item.getStartTime()
        if (BigInt(itemStart.ticks) >= BigInt(splitTimeTicks)) {
            clonedItem = item
            break
        }
    }

    if (clonedItem) {
        execute(() => {
            const setInAction = clonedItem.createSetInPointAction(newInPoint)
            return [setInAction]
        }, project)
    }

    return {
        message: "Audio clip split successfully",
        splitAt: splitTimeTicks
    }
}

const findLinkedClip = async (sequence, trackItem, isVideo, linkedTrackIndex) => {
    const startTime = await trackItem.getStartTime()
    const sourceTicks = BigInt(startTime.ticks)

    let counterpartTrack
    if (isVideo) {
        // Source is video, find on audio track
        counterpartTrack = await sequence.getAudioTrack(linkedTrackIndex)
    } else {
        // Source is audio, find on video track
        counterpartTrack = await sequence.getVideoTrack(linkedTrackIndex)
    }

    if (!counterpartTrack) return null

    const clips = await counterpartTrack.getTrackItems(1, false)
    for (const clip of clips) {
        const clipStart = await clip.getStartTime()
        const clipTicks = BigInt(clipStart.ticks)
        // Match within a small tolerance (1 tick)
        if (sourceTicks - clipTicks <= 1n && clipTicks - sourceTicks <= 1n) {
            return clip
        }
    }

    return null
}

const trimVideoClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`trimVideoClip : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0

    let actions = []

    if (options.newStartTicks !== undefined && options.newStartTicks !== null) {
        const newStart = await app.TickTime.createWithTicks(options.newStartTicks.toString())
        actions.push(trackItem.createSetStartAction(newStart))
    }

    if (options.newEndTicks !== undefined && options.newEndTicks !== null) {
        const newEnd = await app.TickTime.createWithTicks(options.newEndTicks.toString())
        actions.push(trackItem.createSetEndAction(newEnd))
    }

    if (options.newInPointTicks !== undefined && options.newInPointTicks !== null) {
        const newInPoint = await app.TickTime.createWithTicks(options.newInPointTicks.toString())
        actions.push(trackItem.createSetInPointAction(newInPoint))
    }

    if (options.newOutPointTicks !== undefined && options.newOutPointTicks !== null) {
        const newOutPoint = await app.TickTime.createWithTicks(options.newOutPointTicks.toString())
        actions.push(trackItem.createSetOutPointAction(newOutPoint))
    }

    // Also trim the linked audio clip
    if (linked) {
        const linkedClip = await findLinkedClip(sequence, trackItem, true, linkedTrackIndex)
        if (linkedClip) {
            if (options.newStartTicks !== undefined && options.newStartTicks !== null) {
                const newStart = await app.TickTime.createWithTicks(options.newStartTicks.toString())
                actions.push(linkedClip.createSetStartAction(newStart))
            }
            if (options.newEndTicks !== undefined && options.newEndTicks !== null) {
                const newEnd = await app.TickTime.createWithTicks(options.newEndTicks.toString())
                actions.push(linkedClip.createSetEndAction(newEnd))
            }
            if (options.newInPointTicks !== undefined && options.newInPointTicks !== null) {
                const newInPoint = await app.TickTime.createWithTicks(options.newInPointTicks.toString())
                actions.push(linkedClip.createSetInPointAction(newInPoint))
            }
            if (options.newOutPointTicks !== undefined && options.newOutPointTicks !== null) {
                const newOutPoint = await app.TickTime.createWithTicks(options.newOutPointTicks.toString())
                actions.push(linkedClip.createSetOutPointAction(newOutPoint))
            }
        }
    }

    if (actions.length > 0) {
        execute(() => actions, project, "Trim clip")
    }

    return { message: "Clip trimmed successfully" }
}

const trimAudioClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`trimAudioClip : Requires an active sequence.`)
    }

    const trackItem = await getAudioTrack(sequence, options.audioTrackIndex, options.trackItemIndex)

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0

    let actions = []

    if (options.newStartTicks !== undefined && options.newStartTicks !== null) {
        const newStart = await app.TickTime.createWithTicks(options.newStartTicks.toString())
        actions.push(trackItem.createSetStartAction(newStart))
    }

    if (options.newEndTicks !== undefined && options.newEndTicks !== null) {
        const newEnd = await app.TickTime.createWithTicks(options.newEndTicks.toString())
        actions.push(trackItem.createSetEndAction(newEnd))
    }

    if (options.newInPointTicks !== undefined && options.newInPointTicks !== null) {
        const newInPoint = await app.TickTime.createWithTicks(options.newInPointTicks.toString())
        actions.push(trackItem.createSetInPointAction(newInPoint))
    }

    if (options.newOutPointTicks !== undefined && options.newOutPointTicks !== null) {
        const newOutPoint = await app.TickTime.createWithTicks(options.newOutPointTicks.toString())
        actions.push(trackItem.createSetOutPointAction(newOutPoint))
    }

    // Also trim the linked video clip
    if (linked) {
        const linkedClip = await findLinkedClip(sequence, trackItem, false, linkedTrackIndex)
        if (linkedClip) {
            if (options.newStartTicks !== undefined && options.newStartTicks !== null) {
                const newStart = await app.TickTime.createWithTicks(options.newStartTicks.toString())
                actions.push(linkedClip.createSetStartAction(newStart))
            }
            if (options.newEndTicks !== undefined && options.newEndTicks !== null) {
                const newEnd = await app.TickTime.createWithTicks(options.newEndTicks.toString())
                actions.push(linkedClip.createSetEndAction(newEnd))
            }
            if (options.newInPointTicks !== undefined && options.newInPointTicks !== null) {
                const newInPoint = await app.TickTime.createWithTicks(options.newInPointTicks.toString())
                actions.push(linkedClip.createSetInPointAction(newInPoint))
            }
            if (options.newOutPointTicks !== undefined && options.newOutPointTicks !== null) {
                const newOutPoint = await app.TickTime.createWithTicks(options.newOutPointTicks.toString())
                actions.push(linkedClip.createSetOutPointAction(newOutPoint))
            }
        }
    }

    if (actions.length > 0) {
        execute(() => actions, project, "Trim clip")
    }

    return { message: "Audio clip trimmed successfully" }
}

const removeVideoClipRange = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeVideoClipRange : Requires an active sequence.`)
    }

    const editor = await app.SequenceEditor.getEditor(sequence)
    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    const clipStart = await trackItem.getStartTime()
    const clipEnd = await trackItem.getEndTime()
    const clipInPoint = await trackItem.getInPoint()
    const clipOutPoint = await trackItem.getOutPoint()

    const rangeStartTicks = BigInt(options.rangeStartTicks)
    const rangeEndTicks = BigInt(options.rangeEndTicks)

    // Validate range is within clip
    if (rangeStartTicks < BigInt(clipStart.ticks) || rangeEndTicks > BigInt(clipEnd.ticks)) {
        throw new Error(`removeVideoClipRange : Range must be within clip bounds`)
    }

    const rangeStart = await app.TickTime.createWithTicks(rangeStartTicks.toString())
    const rangeEnd = await app.TickTime.createWithTicks(rangeEndTicks.toString())

    // Calculate new in-point for the second part
    const offsetToRangeEnd = rangeEndTicks - BigInt(clipStart.ticks)
    const newInPointTicks = BigInt(clipInPoint.ticks) + offsetToRangeEnd
    const newInPoint = await app.TickTime.createWithTicks(newInPointTicks.toString())

    // Step 1: Clone the clip first
    execute(() => {
        const cloneAction = editor.createCloneTrackItemAction(
            trackItem,
            rangeStart,  // Place clone at range start (will be moved)
            0, 0, true, false
        )
        return [cloneAction]
    }, project)

    // Step 2: Trim the original to end at range start
    execute(() => {
        const trimAction = trackItem.createSetEndAction(rangeStart)
        return [trimAction]
    }, project)

    // Step 3: Find and adjust the cloned clip
    const videoTrack = await sequence.getVideoTrack(options.videoTrackIndex)
    const trackItems = await videoTrack.getTrackItems(1, false)

    let clonedItem = null
    for (const item of trackItems) {
        const itemStart = await item.getStartTime()
        // Find clip that starts at or after our range start (but not the original)
        if (BigInt(itemStart.ticks) >= rangeStartTicks && item !== trackItem) {
            clonedItem = item
            break
        }
    }

    if (clonedItem) {
        execute(() => {
            // Set its in-point to skip the removed range
            const setInAction = clonedItem.createSetInPointAction(newInPoint)
            // Move it to start right after the original clip ends (at rangeStart)
            const moveAction = clonedItem.createSetStartAction(rangeStart)
            return [setInAction, moveAction]
        }, project)
    }

    return {
        message: "Range removed successfully",
        rangeStart: options.rangeStartTicks,
        rangeEnd: options.rangeEndTicks
    }
}

const removeLinkedClipRange = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeLinkedClipRange : Requires an active sequence.`)
    }

    const editor = await app.SequenceEditor.getEditor(sequence)
    const videoTrackIndex = options.videoTrackIndex !== undefined ? options.videoTrackIndex : 0
    const audioTrackIndex = options.audioTrackIndex !== undefined ? options.audioTrackIndex : 0
    const trackItemIndex = options.trackItemIndex !== undefined ? options.trackItemIndex : 0

    // Get both video and audio track items
    const videoItem = await getVideoTrack(sequence, videoTrackIndex, trackItemIndex)
    const audioItem = await getAudioTrack(sequence, audioTrackIndex, trackItemIndex)

    const clipStart = await videoItem.getStartTime()
    const clipEnd = await videoItem.getEndTime()
    const videoInPoint = await videoItem.getInPoint()
    const audioInPoint = await audioItem.getInPoint()

    const rangeStartTicks = BigInt(options.rangeStartTicks)
    const rangeEndTicks = BigInt(options.rangeEndTicks)

    if (rangeStartTicks < BigInt(clipStart.ticks) || rangeEndTicks > BigInt(clipEnd.ticks)) {
        throw new Error(`removeLinkedClipRange : Range must be within clip bounds`)
    }

    const rangeStart = await app.TickTime.createWithTicks(rangeStartTicks.toString())

    // Calculate new in-points for the second parts
    const offsetToRangeEnd = rangeEndTicks - BigInt(clipStart.ticks)
    const newVideoInPointTicks = BigInt(videoInPoint.ticks) + offsetToRangeEnd
    const newAudioInPointTicks = BigInt(audioInPoint.ticks) + offsetToRangeEnd
    const newVideoInPoint = await app.TickTime.createWithTicks(newVideoInPointTicks.toString())
    const newAudioInPoint = await app.TickTime.createWithTicks(newAudioInPointTicks.toString())

    // Step 1: Clone both video and audio clips
    execute(() => {
        const cloneVideoAction = editor.createCloneTrackItemAction(
            videoItem, rangeStart, 0, 0, true, false
        )
        const cloneAudioAction = editor.createCloneTrackItemAction(
            audioItem, rangeStart, 0, 0, false, true
        )
        return [cloneVideoAction, cloneAudioAction]
    }, project, "Clone clips for range removal")

    // Step 2: Trim both originals to end at range start
    execute(() => {
        const trimVideoAction = videoItem.createSetEndAction(rangeStart)
        const trimAudioAction = audioItem.createSetEndAction(rangeStart)
        return [trimVideoAction, trimAudioAction]
    }, project, "Trim originals")

    // Step 3: Find and adjust cloned video clip
    const videoTrack = await sequence.getVideoTrack(videoTrackIndex)
    const videoItems = await videoTrack.getTrackItems(1, false)
    let clonedVideoItem = null
    for (const item of videoItems) {
        const itemStart = await item.getStartTime()
        if (BigInt(itemStart.ticks) >= rangeStartTicks && item !== videoItem) {
            clonedVideoItem = item
            break
        }
    }

    // Step 4: Find and adjust cloned audio clip
    const audioTrack = await sequence.getAudioTrack(audioTrackIndex)
    const audioItems = await audioTrack.getTrackItems(1, false)
    let clonedAudioItem = null
    for (const item of audioItems) {
        const itemStart = await item.getStartTime()
        if (BigInt(itemStart.ticks) >= rangeStartTicks && item !== audioItem) {
            clonedAudioItem = item
            break
        }
    }

    // Step 5: Adjust in-points and positions of cloned clips
    const actions = []
    if (clonedVideoItem) {
        execute(() => {
            return [
                clonedVideoItem.createSetInPointAction(newVideoInPoint),
                clonedVideoItem.createSetStartAction(rangeStart)
            ]
        }, project, "Adjust cloned video")
    }
    if (clonedAudioItem) {
        execute(() => {
            return [
                clonedAudioItem.createSetInPointAction(newAudioInPoint),
                clonedAudioItem.createSetStartAction(rangeStart)
            ]
        }, project, "Adjust cloned audio")
    }

    return {
        message: "Linked range removed successfully",
        rangeStart: options.rangeStartTicks,
        rangeEnd: options.rangeEndTicks
    }
}

const getPlayerPosition = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getPlayerPosition : Requires an active sequence.`)
    }

    const position = await sequence.getPlayerPosition()

    return {
        ticks: position.ticks,
        seconds: position.seconds
    }
}

const setPlayerPosition = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setPlayerPosition : Requires an active sequence.`)
    }

    const positionTime = await app.TickTime.createWithTicks(options.positionTicks.toString())
    await sequence.setPlayerPosition(positionTime)

    return { message: "Player position set successfully" }
}

const addMarker = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addMarker : Requires an active sequence.`)
    }

    const markers = await sequence.getMarkers()
    const startTime = await app.TickTime.createWithTicks(options.startTimeTicks.toString())

    let duration = null
    if (options.durationTicks) {
        duration = await app.TickTime.createWithTicks(options.durationTicks.toString())
    }

    execute(() => {
        const action = markers.createAddMarkerAction(
            options.name || "Marker",
            options.markerType || "Comment",
            startTime,
            duration,
            options.comments || ""
        )
        return [action]
    }, project)

    return { message: "Marker added successfully" }
}

const getMarkers = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getMarkers : Requires an active sequence.`)
    }

    const markers = await sequence.getMarkers()
    const count = markers.getMarkerCount()

    const markerList = []
    for (let i = 0; i < count; i++) {
        const marker = markers.getMarker(i)
        const startTime = await marker.getStartTime()
        const duration = await marker.getDuration()

        markerList.push({
            index: i,
            name: marker.name,
            type: marker.type,
            startTimeTicks: startTime.ticks,
            startTimeSeconds: startTime.seconds,
            durationTicks: duration.ticks,
            durationSeconds: duration.seconds,
            comments: marker.comments || ""
        })
    }

    return { markers: markerList }
}

const removeMarker = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeMarker : Requires an active sequence.`)
    }

    const markers = await sequence.getMarkers()
    const marker = markers.getMarker(options.markerIndex)

    if (!marker) {
        throw new Error(`removeMarker : Marker at index ${options.markerIndex} not found`)
    }

    execute(() => {
        const action = markers.createRemoveMarkerAction(marker)
        return [action]
    }, project)

    return { message: "Marker removed successfully" }
}

const removeClips = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeClips : Requires an active sequence.`)
    }

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0

    // Build track item selection
    const selection = new app.TrackItemSelection()
    let itemCount = 0
    let hasVideo = false
    let hasAudio = false

    if (options.videoItems && options.videoItems.length > 0) {
        for (const item of options.videoItems) {
            const trackItem = await getVideoTrack(sequence, item.trackIndex, item.clipIndex)
            selection.addItem(trackItem)
            itemCount++
            hasVideo = true

            if (linked) {
                const linkedClip = await findLinkedClip(sequence, trackItem, true, linkedTrackIndex)
                if (linkedClip) {
                    selection.addItem(linkedClip)
                    itemCount++
                    hasAudio = true
                }
            }
        }
    }

    if (options.audioItems && options.audioItems.length > 0) {
        for (const item of options.audioItems) {
            const trackItem = await getAudioTrack(sequence, item.trackIndex, item.clipIndex)
            selection.addItem(trackItem)
            itemCount++
            hasAudio = true

            if (linked) {
                const linkedClip = await findLinkedClip(sequence, trackItem, false, linkedTrackIndex)
                if (linkedClip) {
                    selection.addItem(linkedClip)
                    itemCount++
                    hasVideo = true
                }
            }
        }
    }

    if (itemCount === 0) {
        return { message: "No clips to remove" }
    }

    const editor = await app.SequenceEditor.getEditor(sequence)
    const ripple = options.ripple !== undefined ? options.ripple : false

    // Use correct MediaType based on what's in the selection
    const mediaType = hasVideo ? app.Constants.MediaType.VIDEO : app.Constants.MediaType.AUDIO

    execute(() => {
        const action = editor.createRemoveItemsAction(
            selection,
            ripple,
            mediaType
        )
        return [action]
    }, project, "Remove clips")

    return { message: `Removed ${itemCount} clips successfully` }
}

const duplicateClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`duplicateClip : Requires an active sequence.`)
    }

    const editor = await app.SequenceEditor.getEditor(sequence)

    let trackItem
    if (options.isVideo) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const timeOffset = await app.TickTime.createWithTicks(options.timeOffsetTicks.toString())

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0
    const insert = options.insert || false

    // INSERT MODE: 3-phase approach.
    // createCloneTrackItemAction places clones at the SOURCE's position, not at
    // an arbitrary absolute time. So we can't use it to place a clip at position 0
    // when the source is at 191.7s. Instead:
    //   Phase 1: Shift all clips forward by source duration (creates gap)
    //   Phase 2: Insert source's project item at target position (fills gap)
    //   Phase 3: Trim inserted clip to match source's in/out points
    if (insert) {
        const sourceDuration = await trackItem.getDuration()
        const sourceInPoint = await trackItem.getInPoint()
        const sourceProjectItem = await trackItem.getProjectItem()
        const insertionTicks = BigInt(options.timeOffsetTicks)

        // Determine track indices for insertion
        let videoTrackIdx, audioTrackIdx
        if (options.isVideo) {
            videoTrackIdx = options.trackIndex
            audioTrackIdx = linked ? linkedTrackIndex : 0
        } else {
            videoTrackIdx = linked ? linkedTrackIndex : 0
            audioTrackIdx = options.trackIndex
        }

        // Phase 1: Shift all clips at or after insertion point forward
        let shiftActions = []
        if (linked) {
            const videoTrackCount = await sequence.getVideoTrackCount()
            for (let i = 0; i < videoTrackCount; i++) {
                const track = await sequence.getVideoTrack(i)
                const clips = await track.getTrackItems(1, false)
                for (const clip of clips) {
                    const clipStart = await clip.getStartTime()
                    if (BigInt(clipStart.ticks) >= insertionTicks) {
                        shiftActions.push(clip.createMoveAction(sourceDuration))
                    }
                }
            }
            const audioTrackCount = await sequence.getAudioTrackCount()
            for (let i = 0; i < audioTrackCount; i++) {
                const track = await sequence.getAudioTrack(i)
                const clips = await track.getTrackItems(1, false)
                for (const clip of clips) {
                    const clipStart = await clip.getStartTime()
                    if (BigInt(clipStart.ticks) >= insertionTicks) {
                        shiftActions.push(clip.createMoveAction(sourceDuration))
                    }
                }
            }
        } else {
            let track
            if (options.isVideo) {
                track = await sequence.getVideoTrack(options.trackIndex)
            } else {
                track = await sequence.getAudioTrack(options.trackIndex)
            }
            const clips = await track.getTrackItems(1, false)
            for (const clip of clips) {
                const clipStart = await clip.getStartTime()
                if (BigInt(clipStart.ticks) >= insertionTicks) {
                    shiftActions.push(clip.createMoveAction(sourceDuration))
                }
            }
        }

        execute(() => shiftActions, project, "Insert duplicate clip - shift")

        // Phase 2: Place source media at the target position using overwrite
        // This uses absolute positioning (unlike createCloneTrackItemAction)
        execute(() => {
            const overwriteAction = editor.createOverwriteItemAction(
                sourceProjectItem, timeOffset, videoTrackIdx, audioTrackIdx
            )
            return [overwriteAction]
        }, project, "Insert duplicate clip - place")

        // Phase 3: Trim the inserted clip to match source's in/out and duration
        // The overwrite inserted the FULL media - trim to source's portion
        const endTicks = insertionTicks + BigInt(sourceDuration.ticks)
        const endTime = await app.TickTime.createWithTicks(endTicks.toString())

        let trimActions = []

        // Trim video clip at insertion point
        const vTrack = await sequence.getVideoTrack(videoTrackIdx)
        const vClips = await vTrack.getTrackItems(1, false)
        for (const clip of vClips) {
            const clipStart = await clip.getStartTime()
            if (BigInt(clipStart.ticks) === insertionTicks) {
                trimActions.push(clip.createSetInPointAction(sourceInPoint))
                trimActions.push(clip.createSetEndAction(endTime))
                break
            }
        }

        // Trim audio clip at insertion point
        if (linked) {
            const aTrack = await sequence.getAudioTrack(audioTrackIdx)
            const aClips = await aTrack.getTrackItems(1, false)
            for (const clip of aClips) {
                const clipStart = await clip.getStartTime()
                if (BigInt(clipStart.ticks) === insertionTicks) {
                    trimActions.push(clip.createSetInPointAction(sourceInPoint))
                    trimActions.push(clip.createSetEndAction(endTime))
                    break
                }
            }
        }

        if (trimActions.length > 0) {
            execute(() => trimActions, project, "Insert duplicate clip - trim")
        }

        return { message: "Clip duplicated (insert) successfully" }
    }

    // OVERWRITE MODE (insert=false)
    if (linked) {
        const linkedClip = await findLinkedClip(sequence, trackItem, options.isVideo, linkedTrackIndex)
        if (linkedClip) {
            execute(() => {
                const action1 = editor.createCloneTrackItemAction(
                    trackItem, timeOffset,
                    options.videoTrackOffset || 0, options.audioTrackOffset || 0,
                    options.isVideo, false
                )
                const action2 = editor.createCloneTrackItemAction(
                    linkedClip, timeOffset,
                    options.videoTrackOffset || 0, options.audioTrackOffset || 0,
                    !options.isVideo, false
                )
                return [action1, action2]
            }, project, "Duplicate linked clips")
            return { message: "Linked clips duplicated successfully" }
        }
    }

    execute(() => {
        const action = editor.createCloneTrackItemAction(
            trackItem, timeOffset,
            options.videoTrackOffset || 0, options.audioTrackOffset || 0,
            options.isVideo, false
        )
        return [action]
    }, project)

    return { message: "Clip duplicated successfully" }
}

const moveClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`moveClip : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const moveTime = await app.TickTime.createWithTicks(options.moveTimeTicks.toString())

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0

    if (linked) {
        const linkedClip = await findLinkedClip(sequence, trackItem, options.isVideo, linkedTrackIndex)
        if (linkedClip) {
            execute(() => {
                const action1 = trackItem.createMoveAction(moveTime)
                const action2 = linkedClip.createMoveAction(moveTime)
                return [action1, action2]
            }, project, "Move linked clips")
            return { message: "Linked clips moved successfully" }
        }
    }

    execute(() => {
        const action = trackItem.createMoveAction(moveTime)
        return [action]
    }, project, "Move clip")

    return { message: "Clip moved successfully" }
}

const setClipPosition = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setClipPosition : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const newStart = await app.TickTime.createWithTicks(options.newStartTicks.toString())

    const linked = options.linked || false
    const linkedTrackIndex = options.linkedTrackIndex !== undefined ? options.linkedTrackIndex : 0

    if (linked) {
        const linkedClip = await findLinkedClip(sequence, trackItem, options.isVideo, linkedTrackIndex)
        if (linkedClip) {
            execute(() => {
                const action1 = trackItem.createSetStartAction(newStart)
                const action2 = linkedClip.createSetStartAction(newStart)
                return [action1, action2]
            }, project, "Set linked clips position")
            return { message: "Linked clips position set successfully" }
        }
    }

    execute(() => {
        const action = trackItem.createSetStartAction(newStart)
        return [action]
    }, project, "Set clip position")

    return { message: "Clip position set successfully" }
}

const getSequenceSettings = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getSequenceSettings : Requires an active sequence.`)
    }

    const frameSize = await sequence.getFrameSize()
    const settings = await sequence.getSettings()

    // Get duration from end time of last clip
    const videoTrackCount = await sequence.getVideoTrackCount()
    let maxEndTicks = "0"

    for (let i = 0; i < videoTrackCount; i++) {
        const track = await sequence.getVideoTrack(i)
        const clips = await track.getTrackItems(1, false)
        for (const clip of clips) {
            const endTime = await clip.getEndTime()
            if (BigInt(endTime.ticks) > BigInt(maxEndTicks)) {
                maxEndTicks = endTime.ticks
            }
        }
    }

    return {
        name: sequence.name,
        id: sequence.guid.toString(),
        frameWidth: frameSize.width,
        frameHeight: frameSize.height,
        durationTicks: maxEndTicks,
        durationSeconds: Number(BigInt(maxEndTicks)) / 254016000000
    }
}

const renameClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`renameClip : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    execute(() => {
        const action = trackItem.createSetNameAction(options.newName)
        return [action]
    }, project)

    return { message: "Clip renamed successfully" }
}

const getClipInfo = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getClipInfo : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const startTime = await trackItem.getStartTime()
    const endTime = await trackItem.getEndTime()
    const duration = await trackItem.getDuration()
    const inPoint = await trackItem.getInPoint()
    const outPoint = await trackItem.getOutPoint()
    const projectItem = await trackItem.getProjectItem()
    const disabled = await trackItem.isDisabled()

    const TICKS_PER_SECOND = 254016000000

    return {
        name: projectItem ? projectItem.name : "Unknown",
        trackIndex: options.trackIndex,
        clipIndex: options.clipIndex,
        isVideo: options.isVideo,
        startTimeTicks: startTime.ticks,
        startTimeSeconds: Number(BigInt(startTime.ticks)) / TICKS_PER_SECOND,
        endTimeTicks: endTime.ticks,
        endTimeSeconds: Number(BigInt(endTime.ticks)) / TICKS_PER_SECOND,
        durationTicks: duration.ticks,
        durationSeconds: Number(BigInt(duration.ticks)) / TICKS_PER_SECOND,
        inPointTicks: inPoint.ticks,
        inPointSeconds: Number(BigInt(inPoint.ticks)) / TICKS_PER_SECOND,
        outPointTicks: outPoint.ticks,
        outPointSeconds: Number(BigInt(outPoint.ticks)) / TICKS_PER_SECOND,
        disabled: disabled
    }
}

// ============================================
// LAYOUT / VERIFICATION
// ============================================

// Returns a focused clip layout for a SINGLE sequence plus its frame rate.
// Used by the server to verify cuts (clip boundaries -> gap/desync detection)
// and to frame-snap removal ranges. Lighter than getFullProjectData, which
// walks every sequence in the project.
const getSequenceLayout = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getSequenceLayout : Requires an active sequence.`)
    }

    const videoTracks = await getVideoTracks(sequence)
    const audioTracks = await getAudioTracks(sequence)

    // Frame rate is used to frame-snap edits and to size gap tolerances.
    // Read it defensively across possible API shapes; callers fall back to
    // no frame-snapping when it is unavailable.
    let frameRateValue = null
    let ticksPerFrame = null
    try {
        const settings = await sequence.getSettings()
        const fr = await settings.getVideoFrameRate()
        if (fr) {
            if (typeof fr.value === "number") {
                frameRateValue = fr.value
            } else if (typeof fr.value === "function") {
                frameRateValue = fr.value()
            }
            if (typeof fr.ticksPerFrame !== "undefined" && fr.ticksPerFrame !== null) {
                ticksPerFrame = fr.ticksPerFrame.toString()
            }
        }
    } catch (e) {
        // optional
    }

    return {
        id: sequence.guid.toString(),
        name: sequence.name,
        frameRateValue,
        ticksPerFrame,
        videoTracks,
        audioTracks
    }
}

// ============================================
// EFFECT + PARAMS (tolerant)
// ============================================

const _findComponentByMatchName = async (trackItem, matchName) => {
    // Search from the END of the chain backwards. addEffect appends the new
    // component at the end, so when an effect of the same match name already
    // exists on the clip, the LAST one is the instance we just added — returning
    // the first (pre-existing) instance would make us configure the wrong effect.
    const components = await trackItem.getComponentChain()
    const count = components.getComponentCount()
    for (let i = count - 1; i >= 0; i--) {
        const component = components.getComponentAtIndex(i)
        const mn = await component.getMatchName()
        if (mn == matchName) {
            return component
        }
    }
    return null
}

// Adds a video effect (by match name) to a clip, then sets any provided params
// by display name. Unlike appendVideoFilter, unknown params are skipped (not
// thrown) and the response reports which params were applied/skipped plus the
// component's available param display names. This makes effects like Lumetri
// (whose exact param names vary by version) usable and self-documenting.
const addEffectWithParams = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addEffectWithParams : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)
    const effectName = options.effectName
    const properties = options.properties || []

    await addEffect(trackItem, effectName)

    const component = await _findComponentByMatchName(trackItem, effectName)

    const availableParams = []
    if (component) {
        const pCount = component.getParamCount()
        for (let j = 0; j < pCount; j++) {
            availableParams.push(component.getParam(j).displayName)
        }
    }

    const applied = []
    const skipped = []
    for (const p of properties) {
        let param = null
        if (component) {
            const pCount = component.getParamCount()
            for (let j = 0; j < pCount; j++) {
                const candidate = component.getParam(j)
                if (candidate.displayName == p.name) {
                    param = candidate
                    break
                }
            }
        }
        if (!param) {
            skipped.push(p.name)
            continue
        }
        try {
            const keyframe = await param.createKeyframe(p.value)
            execute(() => {
                const action = param.createSetValueAction(keyframe)
                return [action]
            }, project, "Set Effect Parameter")
            applied.push(p.name)
        } catch (e) {
            skipped.push(p.name)
        }
    }

    return {
        message: "Effect added",
        effectName,
        availableParams,
        appliedParams: applied,
        skippedParams: skipped
    }
}

// ============================================
// EXPORT FEATURES
// ============================================

const exportSequence = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`exportSequence : Requires an active sequence.`)
    }

    const presetPath = options.presetPath
    const outputPath = options.outputPath

    const encoder = await app.EncoderManager.getManager()

    // ExportType: IMMEDIATELY = export in Premiere, QUEUE = send to Media Encoder
    const exportType = options.useMediaEncoder
        ? app.Constants.ExportType.QUEUE
        : app.Constants.ExportType.IMMEDIATELY

    const result = await encoder.exportSequence(
        sequence,
        exportType,
        outputPath,
        presetPath
    )

    return {
        success: result,
        message: result ? "Export started successfully" : "Export failed",
        outputPath
    }
}

const getExportFileExtension = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)
    const presetPath = options.presetPath

    const extension = await app.EncoderManager.getExportFileExtension(sequence, presetPath)

    return { extension }
}

// ============================================
// TRANSCRIPT/CAPTION FEATURES
// ============================================

const importTranscript = async (command) => {
    const options = command.options

    const project = await app.Project.getActiveProject()

    // Get project item by name
    const projectItem = await findProjectItem(options.projectItemName, project)

    const clipProjectItem = await app.ClipProjectItem.cast(projectItem)
    if (!clipProjectItem) {
        throw new Error(`importTranscript : Could not cast to ClipProjectItem`)
    }

    const transcriptContent = options.transcriptJson

    execute(() => {
        const textSegments = app.Transcript.importFromJSON(transcriptContent)
        const action = app.Transcript.createImportTextSegmentsAction(textSegments, clipProjectItem)
        return [action]
    }, project, "Import Transcript")

    return { message: "Transcript imported successfully" }
}

const exportTranscript = async (command) => {
    const options = command.options

    const project = await app.Project.getActiveProject()

    const projectItem = await findProjectItem(options.projectItemName, project)

    const clipProjectItem = await app.ClipProjectItem.cast(projectItem)
    if (!clipProjectItem) {
        throw new Error(`exportTranscript : Could not cast to ClipProjectItem`)
    }

    const transcript = await app.Transcript.exportToJSON(clipProjectItem)

    return { transcript }
}

// ============================================
// KEYFRAME FEATURES
// ============================================

const getComponentParam = async (sequence, trackIndex, clipIndex, componentIndex, paramIndex, isVideo = true) => {
    let trackItem
    if (isVideo) {
        trackItem = await getVideoTrack(sequence, trackIndex, clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, trackIndex, clipIndex)
    }

    const componentChain = await trackItem.getComponentChain()
    const component = componentChain.getComponentAtIndex(componentIndex)
    const param = component.getParam(paramIndex)

    return { trackItem, componentChain, component, param }
}

const addKeyframe = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addKeyframe : Requires an active sequence.`)
    }

    const { param } = await getComponentParam(
        sequence,
        options.trackIndex,
        options.clipIndex,
        options.componentIndex,
        options.paramIndex,
        options.isVideo !== false
    )

    const keyframe = param.createKeyframe(options.value)
    keyframe.position = await app.TickTime.createWithTicks(options.positionTicks.toString())

    execute(() => {
        // Enable time-varying if not already
        const setTimeVaryingAction = param.createSetTimeVaryingAction(true)
        const addKeyframeAction = param.createAddKeyframeAction(keyframe)
        return [setTimeVaryingAction, addKeyframeAction]
    }, project, "Add Keyframe")

    return { message: "Keyframe added successfully" }
}

const getKeyframes = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getKeyframes : Requires an active sequence.`)
    }

    const { param } = await getComponentParam(
        sequence,
        options.trackIndex,
        options.clipIndex,
        options.componentIndex,
        options.paramIndex,
        options.isVideo !== false
    )

    const keyframeTimes = await param.getKeyframeListAsTickTimes()

    const keyframes = []
    for (const time of keyframeTimes) {
        keyframes.push({
            ticks: time.ticks,
            seconds: time.seconds
        })
    }

    return { keyframes }
}

const setKeyframeInterpolation = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setKeyframeInterpolation : Requires an active sequence.`)
    }

    const { param } = await getComponentParam(
        sequence,
        options.trackIndex,
        options.clipIndex,
        options.componentIndex,
        options.paramIndex,
        options.isVideo !== false
    )

    const position = await app.TickTime.createWithTicks(options.positionTicks.toString())

    // Interpolation modes: LINEAR=0, HOLD=4, BEZIER=5
    const interpMode = options.interpolationMode || app.Constants.InterpolationMode.LINEAR

    execute(() => {
        const action = param.createSetInterpolationAtKeyframeAction(position, interpMode)
        return [action]
    }, project, "Set Keyframe Interpolation")

    return { message: "Keyframe interpolation set successfully" }
}

const setParamValue = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setParamValue : Requires an active sequence.`)
    }

    const { param } = await getComponentParam(
        sequence,
        options.trackIndex,
        options.clipIndex,
        options.componentIndex,
        options.paramIndex,
        options.isVideo !== false
    )

    const keyframe = param.createKeyframe(options.value)

    execute(() => {
        const setTimeVaryingAction = param.createSetTimeVaryingAction(false)
        const setValueAction = param.createSetValueAction(keyframe, true)
        return [setTimeVaryingAction, setValueAction]
    }, project, "Set Parameter Value")

    return { message: "Parameter value set successfully" }
}

// ============================================
// TRANSITION FEATURES
// ============================================

const getTransitionNames = async (command) => {
    const transitionFactory = app.TransitionFactory
    const matchNames = await transitionFactory.getVideoTransitionMatchNames()
    return { transitions: matchNames }
}

const addTransitionToStart = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addTransitionToStart : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    const transitionFactory = app.TransitionFactory
    const videoTransition = await transitionFactory.createVideoTransition(options.transitionName)

    const addTransitionOptions = app.AddTransitionOptions()
    addTransitionOptions.setApplyToStart(true)

    if (options.duration) {
        const durationTime = await app.TickTime.createWithSeconds(options.duration)
        addTransitionOptions.setDuration(durationTime)
    }

    execute(() => {
        const action = trackItem.createAddVideoTransitionAction(videoTransition, addTransitionOptions)
        return [action]
    }, project, "Add Transition to Start")

    return { message: "Transition added to start successfully" }
}

const removeVideoTransition = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeVideoTransition : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)

    // TransitionPosition: START or END
    const position = options.fromStart
        ? app.Constants.TransitionPosition.START
        : app.Constants.TransitionPosition.END

    execute(() => {
        const action = trackItem.createRemoveVideoTransitionAction(position)
        return [action]
    }, project, "Remove Video Transition")

    return { message: "Video transition removed successfully" }
}

// ============================================
// EFFECTS FEATURES
// ============================================

const getEffectNames = async (command) => {
    const filterFactory = app.VideoFilterFactory
    const matchNames = await filterFactory.getMatchNames()
    return { effects: matchNames }
}

const getAudioEffectNames = async (command) => {
    const filterFactory = app.AudioFilterFactory
    // AudioFilterFactory exposes getDisplayNames() (NOT getMatchNames, which is
    // video-only). Audio effects are added by display name via
    // createComponentByDisplayName, so display names are what callers need.
    const displayNames = await filterFactory.getDisplayNames()
    return { effects: displayNames }
}

const addVideoEffect = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addVideoEffect : Requires an active sequence.`)
    }

    const trackItem = await getVideoTrack(sequence, options.videoTrackIndex, options.trackItemIndex)
    const componentChain = await trackItem.getComponentChain()

    const filterFactory = app.VideoFilterFactory
    const newComponent = await filterFactory.createComponent(options.effectMatchName)

    const insertIndex = options.insertIndex !== undefined ? options.insertIndex : 2

    execute(() => {
        const action = componentChain.createInsertComponentAction(newComponent, insertIndex)
        return [action]
    }, project, "Add Video Effect")

    return { message: "Video effect added successfully" }
}

const addAudioEffect = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addAudioEffect : Requires an active sequence.`)
    }

    const trackItem = await getAudioTrack(sequence, options.audioTrackIndex, options.trackItemIndex)
    const componentChain = await trackItem.getComponentChain()

    const filterFactory = app.AudioFilterFactory
    const newComponent = await filterFactory.createComponentByDisplayName(options.effectName, trackItem)

    const insertIndex = options.insertIndex !== undefined ? options.insertIndex : 2

    execute(() => {
        const action = componentChain.createInsertComponentAction(newComponent, insertIndex)
        return [action]
    }, project, "Add Audio Effect")

    return { message: "Audio effect added successfully" }
}

const removeEffect = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`removeEffect : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo !== false) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const componentChain = await trackItem.getComponentChain()
    const componentToRemove = componentChain.getComponentAtIndex(options.componentIndex)

    execute(() => {
        const action = componentChain.createRemoveComponentAction(componentToRemove)
        return [action]
    }, project, "Remove Effect")

    return { message: "Effect removed successfully" }
}

const getClipEffects = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getClipEffects : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo !== false) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const componentChain = await trackItem.getComponentChain()
    const count = componentChain.getComponentCount()

    const effects = []
    for (let i = 0; i < count; i++) {
        const component = componentChain.getComponentAtIndex(i)
        const matchName = await component.getMatchName()
        const displayName = component.displayName || matchName

        const params = []
        const paramCount = component.getParamCount()
        for (let j = 0; j < paramCount; j++) {
            const param = component.getParam(j)
            params.push({
                index: j,
                displayName: param.displayName,
                type: param.type
            })
        }

        effects.push({
            index: i,
            matchName,
            displayName,
            params
        })
    }

    return { effects }
}

// ============================================
// SEQUENCE FEATURES
// ============================================

const setSequenceInOutPoints = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setSequenceInOutPoints : Requires an active sequence.`)
    }

    const inPoint = await app.TickTime.createWithTicks(options.inPointTicks.toString())
    const outPoint = await app.TickTime.createWithTicks(options.outPointTicks.toString())

    execute(() => {
        const setInAction = sequence.createSetInPointAction(inPoint)
        const setOutAction = sequence.createSetOutPointAction(outPoint)
        return [setInAction, setOutAction]
    }, project, "Set Sequence In/Out Points")

    return { message: "Sequence in/out points set successfully" }
}

const clearSequenceInOutPoints = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`clearSequenceInOutPoints : Requires an active sequence.`)
    }

    const sequenceEnd = await sequence.getEndTime()

    execute(() => {
        const setInAction = sequence.createSetInPointAction(app.TickTime.TIME_ZERO)
        const setOutAction = sequence.createSetOutPointAction(sequenceEnd)
        return [setInAction, setOutAction]
    }, project, "Clear Sequence In/Out Points")

    return { message: "Sequence in/out points cleared" }
}

const createSubsequence = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`createSubsequence : Requires an active sequence.`)
    }

    const ignoreTrackTargeting = options.ignoreTrackTargeting !== false

    const subsequence = await sequence.createSubsequence(ignoreTrackTargeting)

    return {
        message: "Subsequence created successfully",
        subsequenceId: subsequence.guid.toString(),
        subsequenceName: subsequence.name
    }
}

const addHandlesToClip = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`addHandlesToClip : Requires an active sequence.`)
    }

    let trackItem
    if (options.isVideo !== false) {
        trackItem = await getVideoTrack(sequence, options.trackIndex, options.clipIndex)
    } else {
        trackItem = await getAudioTrack(sequence, options.trackIndex, options.clipIndex)
    }

    const TICKS_PER_SECOND = 254016000000

    // Get current in/out points
    const originalInPoint = await trackItem.getInPoint()
    const originalOutPoint = await trackItem.getOutPoint()

    // Calculate new in/out points based on handle frames
    const inPointOffsetTicks = BigInt(options.inPointFrames || 0) * BigInt(TICKS_PER_SECOND / 24) // Assuming 24fps, adjust as needed
    const outPointOffsetTicks = BigInt(options.outPointFrames || 0) * BigInt(TICKS_PER_SECOND / 24)

    const newInPointTicks = BigInt(originalInPoint.ticks) - inPointOffsetTicks
    const newOutPointTicks = BigInt(originalOutPoint.ticks) + outPointOffsetTicks

    const newInPoint = await app.TickTime.createWithTicks(newInPointTicks.toString())
    const newOutPoint = await app.TickTime.createWithTicks(newOutPointTicks.toString())

    execute(() => {
        const setInAction = trackItem.createSetInPointAction(newInPoint)
        const setOutAction = trackItem.createSetOutPointAction(newOutPoint)
        return [setInAction, setOutAction]
    }, project, "Add Handles to Clip")

    return { message: "Handles added to clip successfully" }
}

const createSequence = async (command) => {
    const options = command.options

    const project = await app.Project.getActiveProject()

    if (!project) {
        throw new Error(`createSequence : Requires an open project.`)
    }

    const sequence = await project.createSequence(options.sequenceName)

    return {
        message: "Sequence created successfully",
        sequenceId: sequence.guid.toString(),
        sequenceName: sequence.name
    }
}

const setSequenceVideoSettings = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const project = await app.Project.getActiveProject()
    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setSequenceVideoSettings : Requires an active sequence.`)
    }

    const settings = await sequence.getSettings()

    if (options.pixelAspectRatio) {
        await settings.setVideoPixelAspectRatio(options.pixelAspectRatio)
    }

    if (options.frameRate) {
        const newFrameRate = app.FrameRate.createWithValue(options.frameRate)
        await settings.setVideoFrameRate(newFrameRate)
    }

    execute(() => {
        const action = sequence.createSetSettingsAction(settings)
        return [action]
    }, project, "Set Sequence Settings")

    return { message: "Sequence settings updated successfully" }
}

// ============================================
// SELECTION FEATURES
// ============================================

const getSequenceSelection = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`getSequenceSelection : Requires an active sequence.`)
    }

    const selection = await sequence.getSelection()
    const items = await selection.getTrackItems()

    const selectedItems = []
    for (const item of items) {
        const startTime = await item.getStartTime()
        const endTime = await item.getEndTime()
        const projectItem = await item.getProjectItem()

        selectedItems.push({
            name: projectItem ? projectItem.name : "Unknown",
            startTicks: startTime.ticks,
            endTicks: endTime.ticks
        })
    }

    return { selectedItems }
}

const setSequenceSelection = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`setSequenceSelection : Requires an active sequence.`)
    }

    const selection = new app.TrackItemSelection()

    if (options.videoItems && options.videoItems.length > 0) {
        for (const item of options.videoItems) {
            const trackItem = await getVideoTrack(sequence, item.trackIndex, item.clipIndex)
            selection.addItem(trackItem, false)
        }
    }

    if (options.audioItems && options.audioItems.length > 0) {
        for (const item of options.audioItems) {
            const trackItem = await getAudioTrack(sequence, item.trackIndex, item.clipIndex)
            selection.addItem(trackItem, false)
        }
    }

    await sequence.setSelection(selection)

    return { message: "Selection set successfully" }
}

// ============================================
// MOGRT FEATURES
// ============================================

const insertMogrt = async (command) => {
    const options = command.options
    const id = options.sequenceId

    const sequence = await _getSequenceFromId(id)

    if (!sequence) {
        throw new Error(`insertMogrt : Requires an active sequence.`)
    }

    const editor = await app.SequenceEditor.getEditor(sequence)

    const insertTime = options.insertTimeTicks
        ? await app.TickTime.createWithTicks(options.insertTimeTicks.toString())
        : app.TickTime.TIME_ZERO

    let mogrtItems
    const project = await app.Project.getActiveProject()

    project.lockedAccess(() => {
        mogrtItems = editor.insertMogrtFromPath(
            options.mogrtPath,
            insertTime,
            options.videoTrackIndex || 0,
            options.audioTrackIndex || 0
        )
    })

    return {
        message: "MOGRT inserted successfully",
        itemCount: mogrtItems ? mogrtItems.length : 0
    }
}

const commandHandlers = {
    openProject,
    saveProjectAs,
    saveProject,
    getProjectInfo,
    getFullProjectData,
    setActiveSequence,
    exportFrame,
    setVideoClipProperties,
    createSequenceFromMedia,
    setAudioTrackMute,
    setAudioClipDisabled,
    setVideoClipDisabled,
    appendVideoTransition,
    appendVideoFilter,
    addMediaToSequence,
    importMedia,
    createProject,
    splitVideoClip,
    splitAudioClip,
    splitClipAtTime,
    batchSplitClips,
    trimVideoClip,
    trimAudioClip,
    removeVideoClipRange,
    removeLinkedClipRange,
    getPlayerPosition,
    setPlayerPosition,
    addMarker,
    getMarkers,
    removeMarker,
    removeClips,
    duplicateClip,
    moveClip,
    setClipPosition,
    getSequenceSettings,
    renameClip,
    getClipInfo,
    // Layout / verification
    getSequenceLayout,
    // Export features
    exportSequence,
    getExportFileExtension,
    // Transcript features
    importTranscript,
    exportTranscript,
    // Keyframe features
    addKeyframe,
    getKeyframes,
    setKeyframeInterpolation,
    setParamValue,
    // Transition features
    getTransitionNames,
    addTransitionToStart,
    removeVideoTransition,
    // Effect features
    getEffectNames,
    getAudioEffectNames,
    addVideoEffect,
    addAudioEffect,
    addEffectWithParams,
    removeEffect,
    getClipEffects,
    // Sequence features
    setSequenceInOutPoints,
    clearSequenceInOutPoints,
    createSubsequence,
    addHandlesToClip,
    createSequence,
    setSequenceVideoSettings,
    // Selection features
    getSequenceSelection,
    setSequenceSelection,
    // MOGRT features
    insertMogrt,
};

const checkRequiresActiveProject = async (command) => {
    if (!requiresActiveProject(command)) {
        return;
    }

    let project = await app.Project.getActiveProject()
    if (!project) {
        throw new Error(
            `${command.action} : Requires an open Premiere Project`
        );
    }
};

const requiresActiveProject = (command) => {
    return !["createProject", "openProject"].includes(command.action);
};

module.exports = {
    getSequences,
    getProjectContentInfo,
    getAudioTracks,
    getVideoTracks,
    checkRequiresActiveProject,
    parseAndRouteCommand
};

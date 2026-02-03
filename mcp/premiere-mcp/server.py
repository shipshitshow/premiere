"""Premiere MCP Server - Video processing pipeline for Claude Code."""

import asyncio
import sys
from pathlib import Path

# Add app/src to path for premiere imports
app_src = Path(__file__).parent.parent.parent / "app" / "src"
sys.path.insert(0, str(app_src))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from tools.analyze import detect_segments, detect_viral_moments, get_video_info
from tools.download import download_video
from tools.export import export_clips, export_video
from tools.process import cut_silence, enhance_audio, process_video, transcribe


server = Server("premiere")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="premiere_info",
            description="Get video file information (duration, resolution, codecs, file size)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to video file"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_download",
            description="Download video from YouTube or other platforms",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Video URL"},
                    "output_dir": {"type": "string", "description": "Output directory"},
                    "quality": {"type": "string", "description": "Quality (best, 1080, 720, 480)", "default": "best"},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="premiere_detect_segments",
            description="Detect silence and speech segments in video for editing",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to video file"},
                    "threshold_db": {"type": "number", "description": "Silence threshold in dB", "default": -40},
                    "min_duration": {"type": "number", "description": "Minimum silence duration", "default": 0.5},
                    "padding": {"type": "number", "description": "Padding around cuts", "default": 0.1},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_detect_clips",
            description="Detect viral moments in video using AI analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to video file"},
                    "max_clips": {"type": "integer", "description": "Max clips to detect", "default": 5},
                    "min_duration": {"type": "integer", "description": "Min clip duration (seconds)", "default": 15},
                    "max_duration": {"type": "integer", "description": "Max clip duration (seconds)", "default": 60},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_process",
            description="Process video through the full pipeline (silence removal, audio/video enhancement, transcription, metadata)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to input video"},
                    "output": {"type": "string", "description": "Output path (optional)"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Steps to run: silence, audio, video, transcribe, metadata, thumbnail",
                    },
                    "generate_clips": {"type": "boolean", "description": "Generate viral clips", "default": False},
                    "max_clips": {"type": "integer", "description": "Max clips to generate", "default": 5},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_cut_silence",
            description="Remove silence from video",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to input video"},
                    "output": {"type": "string", "description": "Output path (optional)"},
                    "threshold_db": {"type": "number", "description": "Silence threshold in dB", "default": -40},
                    "min_duration": {"type": "number", "description": "Minimum silence duration", "default": 0.5},
                    "padding": {"type": "number", "description": "Padding around cuts", "default": 0.1},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_enhance_audio",
            description="Enhance audio quality (normalize, denoise)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to input video"},
                    "output": {"type": "string", "description": "Output path (optional)"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_transcribe",
            description="Transcribe video audio to text using Whisper",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to input video"},
                    "output": {"type": "string", "description": "Output transcript path (optional)"},
                    "model": {"type": "string", "description": "Whisper model (tiny, base, small, medium, large)", "default": "base"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="premiere_export",
            description="Export video with specified settings",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to input video"},
                    "output": {"type": "string", "description": "Output path"},
                    "format": {"type": "string", "description": "Format (mp4, mov, webm)", "default": "mp4"},
                    "resolution": {"type": "string", "description": "Resolution (1080p, 720p, 480p, WxH)"},
                    "quality": {"type": "string", "description": "Quality (high, medium, low)", "default": "high"},
                },
                "required": ["path", "output"],
            },
        ),
        Tool(
            name="premiere_export_clips",
            description="Export multiple clips from video",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_path": {"type": "string", "description": "Path to source video"},
                    "clips": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "number"},
                                "end": {"type": "number"},
                                "name": {"type": "string"},
                            },
                            "required": ["start", "end"],
                        },
                        "description": "Clip definitions with start/end times",
                    },
                    "output_dir": {"type": "string", "description": "Output directory"},
                    "vertical": {"type": "boolean", "description": "Convert to 9:16 vertical", "default": True},
                },
                "required": ["video_path", "clips", "output_dir"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    import json

    try:
        if name == "premiere_info":
            result = await get_video_info(arguments["path"])
        elif name == "premiere_download":
            result = await download_video(
                arguments["url"],
                arguments.get("output_dir"),
                arguments.get("quality", "best"),
            )
        elif name == "premiere_detect_segments":
            result = await detect_segments(
                arguments["path"],
                arguments.get("threshold_db", -40),
                arguments.get("min_duration", 0.5),
                arguments.get("padding", 0.1),
            )
        elif name == "premiere_detect_clips":
            result = await detect_viral_moments(
                arguments["path"],
                arguments.get("max_clips", 5),
                arguments.get("min_duration", 15),
                arguments.get("max_duration", 60),
            )
        elif name == "premiere_process":
            result = await process_video(
                arguments["path"],
                arguments.get("output"),
                arguments.get("steps"),
                arguments.get("generate_clips", False),
                arguments.get("max_clips", 5),
            )
        elif name == "premiere_cut_silence":
            result = await cut_silence(
                arguments["path"],
                arguments.get("output"),
                arguments.get("threshold_db", -40),
                arguments.get("min_duration", 0.5),
                arguments.get("padding", 0.1),
            )
        elif name == "premiere_enhance_audio":
            result = await enhance_audio(
                arguments["path"],
                arguments.get("output"),
            )
        elif name == "premiere_transcribe":
            result = await transcribe(
                arguments["path"],
                arguments.get("output"),
                arguments.get("model", "base"),
            )
        elif name == "premiere_export":
            result = await export_video(
                arguments["path"],
                arguments["output"],
                arguments.get("format", "mp4"),
                arguments.get("resolution"),
                arguments.get("quality", "high"),
            )
        elif name == "premiere_export_clips":
            result = await export_clips(
                arguments["video_path"],
                arguments["clips"],
                arguments["output_dir"],
                arguments.get("vertical", True),
                arguments.get("with_captions", False),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

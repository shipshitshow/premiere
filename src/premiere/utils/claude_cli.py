"""Claude CLI integration for AI processing."""

import subprocess
from pathlib import Path

from premiere.utils.logger import get_logger


class ClaudeCliError(Exception):
    """Claude CLI execution error."""


def check_claude_cli() -> bool:
    """Check if Claude CLI is installed and authenticated.

    Returns:
        True if Claude CLI is available.

    Raises:
        ClaudeCliError: If Claude CLI is not found or not authenticated.
    """
    import shutil

    if shutil.which("claude") is None:
        raise ClaudeCliError(
            "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        )
    return True


def run_claude_prompt(
    prompt: str,
    context_files: list[Path] | None = None,
    output_format: str = "text",
) -> str:
    """Run a prompt through Claude CLI.

    Args:
        prompt: The prompt to send to Claude.
        context_files: Optional list of files to include as context.
        output_format: Expected output format (text, json, md).

    Returns:
        Claude's response as string.

    Raises:
        ClaudeCliError: If Claude CLI fails.
    """
    check_claude_cli()
    logger = get_logger()

    # Build the full prompt with file contents
    full_prompt_parts = []

    if context_files:
        for file_path in context_files:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                full_prompt_parts.append(f"## File: {file_path.name}\n\n{content}\n")

    full_prompt_parts.append(f"## Task\n\n{prompt}")
    full_prompt = "\n".join(full_prompt_parts)

    logger.debug(f"Running Claude CLI with prompt ({len(full_prompt)} chars)")

    # Run claude CLI with --print flag for non-interactive output
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise ClaudeCliError(f"Claude CLI failed: {result.stderr}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired as e:
        raise ClaudeCliError("Claude CLI timed out after 120 seconds") from e
    except FileNotFoundError as e:
        raise ClaudeCliError("Claude CLI not found") from e


def run_claude_with_file(
    prompt_file: Path,
    context_files: list[Path] | None = None,
) -> str:
    """Run Claude CLI with a prompt file.

    Args:
        prompt_file: Markdown file containing the prompt.
        context_files: Additional context files.

    Returns:
        Claude's response.
    """
    prompt = prompt_file.read_text(encoding="utf-8")
    return run_claude_prompt(prompt, context_files)


def process_transcript_for_metadata(
    transcript_path: Path,
    video_name: str,
    tone: str = "professional",
    title_count: int = 5,
) -> str:
    """Process transcript to generate YouTube metadata using Claude CLI.

    Args:
        transcript_path: Path to transcript markdown file.
        video_name: Original video filename.
        tone: Content tone (professional, casual, clickbait).
        title_count: Number of title options to generate.

    Returns:
        Claude's metadata response.
    """
    tone_desc = {
        "professional": "professional and informative",
        "casual": "friendly and conversational",
        "clickbait": "attention-grabbing and exciting (but not misleading)",
    }.get(tone, "professional")

    prompt = f"""Analyze the video transcript and generate YouTube metadata.

Video filename: {video_name}
Tone: {tone_desc}

Generate:
1. {title_count} title options (50-60 chars each, engaging, SEO-friendly)
2. A description (200-300 words, hook at start, key points, CTA at end)
3. 10-15 relevant tags for SEO
4. 3-5 relevant hashtags

Format your response EXACTLY as:

TITLES:
1. [title]
2. [title]
...

DESCRIPTION:
[full description text]

TAGS:
tag1, tag2, tag3, ...

HASHTAGS:
#hashtag1 #hashtag2 ...
"""

    return run_claude_prompt(prompt, [transcript_path])


def find_viral_clips(
    transcript_path: Path,
    video_duration: float,
    max_clips: int = 5,
    target_duration: tuple[int, int] = (30, 60),
) -> str:
    """Find viral clip candidates from transcript using Claude CLI.

    Args:
        transcript_path: Path to transcript markdown file.
        video_duration: Total video duration in seconds.
        max_clips: Maximum number of clips to find.
        target_duration: Target clip duration range (min, max) in seconds.

    Returns:
        Claude's response with clip recommendations.
    """
    min_dur, max_dur = target_duration

    prompt = f"""Analyze this video transcript to find the most viral/engaging moments for YouTube Shorts or TikTok clips.

Video duration: {video_duration:.0f} seconds
Target clip length: {min_dur}-{max_dur} seconds
Number of clips needed: {max_clips}

Find segments that have:
- Strong hooks (surprising statements, questions, bold claims)
- Emotional peaks (excitement, humor, insight)
- Quotable moments (concise, memorable statements)
- Complete thoughts (don't cut mid-sentence)
- Standalone value (makes sense without full context)

For each clip, provide:
1. Start timestamp (MM:SS format)
2. End timestamp (MM:SS format)
3. Hook text (first few words to grab attention)
4. Viral potential score (1-10)
5. Suggested caption for short-form

Format your response EXACTLY as:

CLIP 1:
- Start: MM:SS
- End: MM:SS
- Duration: XXs
- Hook: "first words of the clip..."
- Score: X/10
- Caption: suggested caption text
- Why viral: brief explanation

CLIP 2:
...

Rank clips by viral potential (best first).
"""

    return run_claude_prompt(prompt, [transcript_path])


def generate_clip_metadata(
    clip_transcript: str,
    platform: str = "youtube_shorts",
) -> str:
    """Generate metadata for a single clip.

    Args:
        clip_transcript: Transcript text of the clip.
        platform: Target platform (youtube_shorts, tiktok, instagram).

    Returns:
        Claude's response with clip metadata.
    """
    platform_tips = {
        "youtube_shorts": "max 60 seconds, vertical 9:16, hook in first 3 seconds",
        "tiktok": "15-60 seconds, trending sounds, fast pace",
        "instagram": "15-90 seconds, aesthetic focus, story format",
    }

    prompt = f"""Generate engaging metadata for this short-form video clip.

Platform: {platform}
Guidelines: {platform_tips.get(platform, platform_tips['youtube_shorts'])}

Clip transcript:
{clip_transcript}

Generate:
1. Hook title (under 40 chars, curiosity-inducing)
2. Caption with emojis and hashtags
3. 5 relevant hashtags for discovery

Format:
TITLE: [title]
CAPTION: [caption with emojis]
HASHTAGS: #tag1 #tag2 ...
"""

    return run_claude_prompt(prompt)

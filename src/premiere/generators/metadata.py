"""AI-powered metadata generation for YouTube."""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from premiere.generators.transcription import Transcript, generate_chapters, save_transcript
from premiere.utils.config import get_config, get_temp_dir
from premiere.utils.logger import get_logger


@dataclass
class VideoMetadata:
    """Generated video metadata."""

    titles: list[str]
    description: str
    tags: list[str]
    chapters: list[dict]
    hashtags: list[str] | None = None


def generate_metadata(
    transcript: Transcript,
    video_path: Path | None = None,
    keywords: list[str] | None = None,
    use_claude_cli: bool = True,
) -> VideoMetadata:
    """Generate YouTube metadata using AI.

    Args:
        transcript: Video transcript.
        video_path: Original video path (for context).
        keywords: Target keywords for SEO.
        use_claude_cli: Use Claude CLI instead of API (default True).

    Returns:
        Generated metadata.
    """
    logger = get_logger()
    config = get_config().ai

    logger.info("Generating video metadata with AI")

    if use_claude_cli:
        return _generate_with_claude_cli(transcript, video_path, keywords, config)

    # Fallback to API-based generation
    if config.provider == "anthropic":
        return _generate_with_anthropic(transcript, video_path, keywords, config)
    elif config.provider == "openai":
        return _generate_with_openai(transcript, video_path, keywords, config)
    else:
        raise ValueError(f"Unknown AI provider: {config.provider}")


def _generate_with_claude_cli(
    transcript: Transcript,
    video_path: Path | None,
    keywords: list[str] | None,
    config,
) -> VideoMetadata:
    """Generate metadata using Claude CLI."""
    from premiere.utils.claude_cli import process_transcript_for_metadata

    logger = get_logger()
    logger.info("Using Claude CLI for metadata generation")

    # Save transcript to workspace temp file
    temp_base = get_temp_dir()
    temp_path = temp_base / f"metadata_{int(time.time())}"
    temp_path.mkdir(parents=True, exist_ok=True)
    transcript_path = temp_path / "transcript.md"
    
    try:
        save_transcript(transcript, transcript_path, format="md")

        video_name = video_path.stem if video_path else "video"

        # Get response from Claude CLI
        response = process_transcript_for_metadata(
            transcript_path,
            video_name,
            config.tone,
            config.title_count,
        )
    finally:
        # Clean up temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)

    # Parse response
    return _parse_metadata_response(response, transcript, config)


def _generate_with_anthropic(
    transcript: Transcript,
    video_path: Path | None,
    keywords: list[str] | None,
    config,
) -> VideoMetadata:
    """Generate metadata using Anthropic Claude API."""
    logger = get_logger()

    try:
        import anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic not installed. Run: pip install anthropic"
        ) from e

    api_key = get_config().anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Use Claude CLI instead (default).")

    client = anthropic.Anthropic(api_key=api_key)

    filename = video_path.stem if video_path else "video"
    keywords_str = ", ".join(keywords) if keywords else "none specified"
    tone_desc = {
        "professional": "professional and informative",
        "casual": "friendly and conversational",
        "clickbait": "attention-grabbing and exciting (but not misleading)",
    }.get(config.tone, "professional")

    prompt = f"""Analyze this video transcript and generate YouTube metadata.

Video filename: {filename}
Target keywords: {keywords_str}
Tone: {tone_desc}

Transcript:
{transcript.full_text[:4000]}

Generate:
1. {config.title_count} title options (50-60 chars each, engaging, includes main topic)
2. A description (200-300 words, starts with hook, includes key points, ends with CTA)
3. 10-15 relevant tags for SEO
{"4. Include relevant hashtags at the end of description" if config.include_hashtags else ""}

Format your response as:
TITLES:
1. [title]
2. [title]
...

DESCRIPTION:
[full description]

TAGS:
tag1, tag2, tag3, ...
"""

    message = client.messages.create(
        model=config.model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    logger.debug(f"AI response: {response_text[:500]}...")

    return _parse_metadata_response(response_text, transcript, config)


def _generate_with_openai(
    transcript: Transcript,
    video_path: Path | None,
    keywords: list[str] | None,
    config,
) -> VideoMetadata:
    """Generate metadata using OpenAI."""
    logger = get_logger()

    try:
        import openai
    except ImportError as e:
        raise ImportError(
            "openai not installed. Run: pip install openai"
        ) from e

    api_key = get_config().openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Use Claude CLI instead (default).")

    client = openai.OpenAI(api_key=api_key)

    filename = video_path.stem if video_path else "video"
    keywords_str = ", ".join(keywords) if keywords else "none specified"

    prompt = f"""Analyze this video transcript and generate YouTube metadata.

Video filename: {filename}
Target keywords: {keywords_str}

Transcript:
{transcript.full_text[:4000]}

Generate {config.title_count} title options, a description, and 10-15 tags.

Format:
TITLES:
1. [title]
...

DESCRIPTION:
[description]

TAGS:
tag1, tag2, ...
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )

    response_text = response.choices[0].message.content
    return _parse_metadata_response(response_text, transcript, config)


def _parse_metadata_response(
    response: str,
    transcript: Transcript,
    config,
) -> VideoMetadata:
    """Parse AI response into metadata structure."""
    import re

    logger = get_logger()

    titles = []
    description = ""
    tags = []
    hashtags = []

    # Parse sections
    current_section = None
    lines = response.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        upper = line.upper()
        if upper.startswith("TITLE"):
            current_section = "titles"
        elif upper.startswith("DESCRIPTION"):
            current_section = "description"
        elif upper.startswith("TAG") and not upper.startswith("HASHTAG"):
            current_section = "tags"
        elif upper.startswith("HASHTAG"):
            current_section = "hashtags"
        elif current_section == "titles" and line[0].isdigit():
            title = line.lstrip("0123456789.-) ").strip()
            if title:
                titles.append(title)
        elif current_section == "description":
            description += line + "\n"
        elif current_section == "tags":
            for tag in line.split(","):
                tag = tag.strip().lstrip("#")
                if tag and tag not in tags:
                    tags.append(tag)
        elif current_section == "hashtags":
            found = re.findall(r"#\w+", line)
            hashtags.extend(found)

    description = description.strip()

    # Generate chapters if enabled
    chapters = []
    if config.include_chapters:
        chapters = generate_chapters(transcript)

    logger.info(f"Generated {len(titles)} titles, {len(tags)} tags")

    return VideoMetadata(
        titles=titles,
        description=description,
        tags=tags,
        chapters=chapters,
        hashtags=hashtags if hashtags else None,
    )


def format_description_with_chapters(
    description: str,
    chapters: list[dict],
) -> str:
    """Add chapter timestamps to description.

    Args:
        description: Base description text.
        chapters: List of chapter dicts with 'time' and 'title'.

    Returns:
        Description with chapters section.
    """
    if not chapters:
        return description

    def format_time(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    chapter_lines = ["\n\nChapters:"]
    for chapter in chapters:
        chapter_lines.append(f"{format_time(chapter['time'])} - {chapter['title']}")

    return description + "\n".join(chapter_lines)

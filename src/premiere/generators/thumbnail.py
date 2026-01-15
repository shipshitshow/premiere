"""Thumbnail generation for YouTube videos."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from premiere.processors.video import extract_keyframes
from premiere.utils.config import ThumbnailConfig, get_config
from premiere.utils.logger import get_logger


def generate_thumbnail(
    video_path: Path,
    output_path: Path,
    title: str | None = None,
    config: ThumbnailConfig | None = None,
) -> Path:
    """Generate a YouTube thumbnail from video.

    Args:
        video_path: Path to video file.
        output_path: Path for output thumbnail.
        title: Optional title text to overlay.
        config: Thumbnail configuration.

    Returns:
        Path to generated thumbnail.
    """
    logger = get_logger()
    cfg = config or get_config().thumbnail

    logger.info(f"Generating thumbnail for {video_path.name}")

    # Extract candidate frames to workspace temp
    from premiere.utils.config import get_temp_dir
    import shutil
    import time
    
    temp_base = get_temp_dir()
    temp_path = temp_base / f"thumbnail_{int(time.time())}"
    temp_path.mkdir(parents=True, exist_ok=True)
    frames_dir = temp_path
    
    try:
        frames = extract_keyframes(video_path, frames_dir, count=10)

        if not frames:
            raise ValueError("No frames extracted from video")

        # Select best frame
        best_frame = _select_best_frame(frames, cfg)
        logger.info(f"Selected frame: {best_frame.name}")

        # Load and process frame
        img = Image.open(best_frame)

        # Resize to thumbnail dimensions
        img = _resize_and_crop(img, cfg.width, cfg.height)

        # Apply style enhancements
        img = _apply_style(img, cfg.style)

        # Add text overlay
        if cfg.text_overlay and title:
            img = _add_text_overlay(img, title, cfg.style)

        # Save
        img.save(output_path, "JPEG", quality=95)
    finally:
        # Clean up temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)

    logger.info(f"Thumbnail generated: {output_path}")
    return output_path


def _select_best_frame(frames: list[Path], config: ThumbnailConfig) -> Path:
    """Select the best frame for thumbnail.

    Args:
        frames: List of candidate frame paths.
        config: Thumbnail configuration.

    Returns:
        Path to best frame.
    """
    logger = get_logger()

    if not frames:
        raise ValueError("No frames to select from")

    scored_frames = []

    for frame_path in frames:
        try:
            img = Image.open(frame_path)
            score = _score_frame(img, config)
            scored_frames.append((frame_path, score))
        except Exception as e:
            logger.warning(f"Failed to score frame {frame_path}: {e}")
            continue

    if not scored_frames:
        return frames[0]

    # Sort by score descending
    scored_frames.sort(key=lambda x: x[1], reverse=True)
    return scored_frames[0][0]


def _score_frame(img: Image.Image, config: ThumbnailConfig) -> float:
    """Score a frame for thumbnail suitability.

    Higher scores = better thumbnails.
    Considers: sharpness, brightness, contrast, face presence.
    """
    score = 0.0

    # Sharpness (laplacian variance approximation)
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_data = list(edges.getdata())
    variance = sum((x - sum(edge_data) / len(edge_data)) ** 2 for x in edge_data) / len(edge_data)
    sharpness_score = min(variance / 1000, 30)  # Cap at 30
    score += sharpness_score

    # Brightness (prefer mid-range)
    brightness = sum(gray.getdata()) / len(list(gray.getdata()))
    brightness_score = 20 - abs(brightness - 128) / 6.4  # Peak at 128
    score += brightness_score

    # Contrast
    min_val = min(gray.getdata())
    max_val = max(gray.getdata())
    contrast = max_val - min_val
    contrast_score = contrast / 10  # Higher contrast = higher score
    score += min(contrast_score, 20)

    # Face detection bonus (if enabled)
    if config.face_detection:
        # Simple approximation: check for skin tones
        rgb = img.convert("RGB")
        skin_pixels = 0
        for r, g, b in rgb.getdata():
            if _is_skin_tone(r, g, b):
                skin_pixels += 1
        skin_ratio = skin_pixels / (img.width * img.height)
        if 0.05 < skin_ratio < 0.3:  # Reasonable face coverage
            score += 20

    return score


def _is_skin_tone(r: int, g: int, b: int) -> bool:
    """Check if RGB values could be skin tone."""
    return (
        r > 95 and g > 40 and b > 20 and
        max(r, g, b) - min(r, g, b) > 15 and
        abs(r - g) > 15 and r > g and r > b
    )


def _resize_and_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize and center-crop to target dimensions."""
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider, scale by height
        new_height = height
        new_width = int(img.width * (height / img.height))
    else:
        # Image is taller, scale by width
        new_width = width
        new_height = int(img.height * (width / img.width))

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Center crop
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    right = left + width
    bottom = top + height

    return img.crop((left, top, right, bottom))


def _apply_style(img: Image.Image, style: str) -> Image.Image:
    """Apply style enhancements to image."""
    if style == "bold":
        # High contrast, saturated
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.05)
    elif style == "minimal":
        # Subtle, clean
        img = ImageEnhance.Contrast(img).enhance(1.1)
    elif style == "cinematic":
        # Slight desaturation, added contrast
        img = ImageEnhance.Color(img).enhance(0.85)
        img = ImageEnhance.Contrast(img).enhance(1.25)

    return img


def _add_text_overlay(img: Image.Image, title: str, style: str) -> Image.Image:
    """Add title text overlay to thumbnail."""
    draw = ImageDraw.Draw(img)

    # Use system fonts
    font_size = img.height // 6
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    # Wrap text if too long
    max_width = img.width * 0.8
    lines = _wrap_text(title, font, max_width, draw)

    # Calculate text position (bottom third of image)
    text = "\n".join(lines)
    bbox = draw.multiline_textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (img.width - text_width) // 2
    y = img.height - text_height - (img.height // 8)

    # Draw text shadow
    shadow_offset = max(2, font_size // 20)
    draw.multiline_text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=(0, 0, 0, 180),
        align="center",
    )

    # Draw main text
    if style == "bold":
        fill = (255, 255, 0)  # Yellow
    elif style == "cinematic":
        fill = (255, 255, 255)  # White
    else:
        fill = (255, 255, 255)  # White

    draw.multiline_text((x, y), text, font=font, fill=fill, align="center")

    return img


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines[:3]  # Max 3 lines

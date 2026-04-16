# Contributing to Premiere

Thank you for your interest in contributing to Premiere! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Work Tracking

- Use GitHub issues for bugs, features, and tracked work.
- Do not create `.agents/TASKS` or `.agents/PRDS` entries for repo work.
- If a change is small, clear, and can be implemented safely right away, implement it directly.
- Use GitHub issues when the work needs discussion, tracking, prioritization, or a broader scope.

## Development Setup

### Prerequisites

- **Python 3.11+** - Required for modern type hints and features
- **FFmpeg** - Core video processing dependency
- **Git** - Version control

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/premiere.git
   cd premiere
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install FFmpeg:**

   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # Windows (via Chocolatey)
   choco install ffmpeg
   ```

4. **Install the package in development mode:**

   ```bash
   pip install -e ".[dev]"
   ```

5. **Verify installation:**

   ```bash
   premiere --version
   pytest tests/ -v
   ```

### Environment Variables

Create a `.env` file for local development (optional):

```bash
# AI API keys (optional - Claude CLI is used by default)
PREMIERE_ANTHROPIC_API_KEY=your-key-here

# Logging
PREMIERE_LOG_LEVEL=DEBUG
```

## Project Structure

```
premiere/
├── .github/workflows/    # CI/CD configuration
├── config/
│   └── default.yaml      # Default configuration
├── docs/
│   ├── PRD.md           # Product requirements
│   └── WORKFLOW.md      # User workflow guide
├── src/premiere/
│   ├── __init__.py
│   ├── main.py          # CLI entry point
│   ├── pipeline.py      # Processing orchestration
│   ├── jobs.py          # Job queue system
│   ├── worker.py        # Background processor
│   ├── ui.py            # Streamlit interface
│   ├── processors/      # Video/audio processing
│   │   ├── silence.py   # Silence detection/removal
│   │   ├── audio.py     # Audio enhancement
│   │   ├── video.py     # Video enhancement
│   │   └── music.py     # Background music
│   ├── generators/      # Content generation
│   │   ├── transcription.py
│   │   ├── metadata.py
│   │   ├── clips.py
│   │   └── thumbnail.py
│   ├── uploaders/       # Platform uploaders
│   │   └── youtube.py
│   ├── downloaders/     # Content downloaders
│   │   └── youtube_dl.py
│   └── utils/           # Utilities
│       ├── config.py    # Configuration management
│       ├── ffmpeg.py    # FFmpeg wrapper
│       ├── logger.py    # Logging configuration
│       └── retry.py     # Retry utilities
├── tests/               # Test suite
├── pyproject.toml       # Project configuration
└── CONTRIBUTING.md      # This file
```

## Code Style

We use **Ruff** for linting and formatting. The configuration is in `pyproject.toml`.

### Running Linters

```bash
# Check for linting issues
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Check formatting
ruff format --check src/

# Auto-format
ruff format src/
```

### Style Guidelines

1. **Type hints** - Use type hints for all function parameters and return values
2. **Docstrings** - Use Google-style docstrings for all public functions
3. **Line length** - Maximum 100 characters
4. **Imports** - Sorted automatically by Ruff (isort rules)

### Example Function

```python
def process_video(
    video_path: Path,
    output_path: Path,
    config: VideoConfig | None = None,
) -> Path:
    """Process a video file with configured enhancements.

    Args:
        video_path: Path to input video file.
        output_path: Path for output video.
        config: Optional video configuration (uses global if None).

    Returns:
        Path to the processed video file.

    Raises:
        FFmpegError: If video processing fails.
    """
    ...
```

## Testing

We use **pytest** for testing. Tests are located in the `tests/` directory.

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/premiere --cov-report=term-missing

# Run specific test file
pytest tests/test_silence.py

# Run specific test
pytest tests/test_silence.py::TestDetectSilence::test_detect_silence_parses_ffmpeg_output

# Run tests matching a pattern
pytest tests/ -k "test_config"
```

### Writing Tests

1. **Use fixtures** from `conftest.py` for common setup
2. **Mock external dependencies** (FFmpeg, APIs) to ensure tests are fast and reliable
3. **Test edge cases** - empty inputs, invalid data, error conditions
4. **Use descriptive names** - `test_<function>_<scenario>_<expected_result>`

### Example Test

```python
def test_detect_silence_parses_ffmpeg_output(self, mock_video_path, test_config):
    """Test that silence detection parses FFmpeg output correctly."""
    mock_stderr = """
    [silencedetect @ 0x1234] silence_start: 5.0
    [silencedetect @ 0x1234] silence_end: 8.0 | silence_duration: 3.0
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=mock_stderr)
        segments = detect_silence(mock_video_path)

    assert len(segments) == 1
    assert segments[0].start == 5.0
    assert segments[0].end == 8.0
```

## Submitting Changes

### Pull Request Process

1. **Fork the repository** and create a feature branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines

3. **Add/update tests** for your changes

4. **Run the test suite:**

   ```bash
   pytest tests/
   ruff check src/
   ruff format --check src/
   ```

5. **Commit your changes** with a descriptive message:

   ```bash
   git commit -m "Add feature: description of the feature"
   ```

6. **Push to your fork:**

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request** with:
   - Clear description of the changes
   - Reference to any related issues
   - Screenshots/examples if applicable

### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be 50 characters or less
- Reference issues and PRs when relevant

Examples:
- `Add silence detection threshold validation`
- `Fix audio normalization for stereo tracks`
- `Update transcription to use faster-whisper v1.1`

## Release Process

Releases are managed through GitHub releases and follow semantic versioning.

### Version Numbers

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Creating a Release

1. Update version in `src/premiere/__init__.py`
2. Update CHANGELOG.md (if exists)
3. Create a git tag: `git tag v1.2.3`
4. Push the tag: `git push origin v1.2.3`
5. Create a GitHub release from the tag

## Getting Help

- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas

Thank you for contributing to Premiere!

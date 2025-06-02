# 🗣️ Voxtus

**Voxtus is a command-line tool for transcribing Internet videos and media files to text using [faster-whisper](https://github.com/guillaumekln/faster-whisper).**

It supports multiple output formats and can download, transcribe, and optionally retain the original audio. It's built in Python and installable as a proper CLI via PyPI or from source.

## ✨ Features

- 🎥 **Download & transcribe** videos from YouTube, Vimeo, and 1000+ sites
- 📁 **Local file support** for audio/video files  
- 📝 **Multiple output formats**: TXT, JSON, SRT, VTT
- 🎛️ **Model selection** - Choose from tiny to large models for speed/accuracy trade-offs
- 🔄 **Batch processing** multiple formats in one run
- 📊 **Rich metadata** in JSON format (title, source, duration, language)
- 🚀 **Stdout mode** for pipeline integration
- 🎯 **LLM-friendly** default text format
- ⚡ **Fast** transcription via faster-whisper

---

## ⚙️ Installation

### 1. Install system dependency: ffmpeg

Voxtus uses `ffmpeg` under the hood to extract audio from video files.

#### macOS:

```bash
brew install ffmpeg
```

#### Ubuntu/Debian:

```bash
sudo apt update && sudo apt install ffmpeg
```

---

### 2. Recommended for end users (via pipx)

```bash
pipx install voxtus
```

After that, simply run:

```bash
voxtus --help
```

---

## 🧪 Development Setup

### Quick Start for Contributors

```bash
git clone https://github.com/johanthoren/voxtus.git
cd voxtus

# Install uv (fast Python package manager)
brew install uv         # macOS
# or: pip install uv    # any platform

# Setup development environment
make dev-install

# Run tests
make test
```

### Development Workflow

The project uses a simple Makefile for development tasks. All targets automatically verify dependencies and provide helpful installation instructions if tools are missing.

```bash
make help              # Show all available commands with dynamic version examples
make install           # Install package and dependencies
make dev-install       # Install with development dependencies
make run               # Run development version (e.g., make run -- -f json file.mp4)
make test              # Run tests (fast)
make test-coverage     # Run tests with coverage report
make test-ci           # Run GitHub Actions workflow locally (requires act)

# Dependency verification
make verify-uv         # Check if uv is installed
make verify-act        # Check if act is installed

# Release (bumps version, commits, tags, and pushes)
make release           # Patch release (e.g., 0.1.9 -> 0.1.10)
make release patch     # Patch release (same as above)
make release minor     # Minor release (e.g., 0.1.9 -> 0.2.0)
make release major     # Major release (e.g., 0.1.9 -> 1.0.0)
```

### Dependencies

The Makefile automatically checks for required tools:

- **uv** - Fast Python package manager (required for most targets)
  - Install: `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`
- **act** - Run GitHub Actions locally (optional, only for `test-ci`)
  - Install: `brew install act` or see [installation guide](https://github.com/nektos/act#installation)

### Enhanced Release Process

The release process includes comprehensive safety checks:

1. **Git Status Check** - Offers to stage and commit pending changes
2. **Test Suite** - Runs tests with coverage reporting  
3. **Coverage Validation** - Prompts if coverage is below 80%
4. **Version Bump** - Updates `pyproject.toml` and commits the change
5. **Git Operations** - Creates tag and pushes to trigger CI/CD

### Local CI Testing

Use `make test-ci` to run the exact same GitHub Actions workflow locally:

```bash
make test-ci    # Runs .github/workflows/test.yml with act
```

This ensures your changes work in the CI environment before pushing.

---

### 🧪 For contributors / running from source

```bash
git clone https://github.com/johanthoren/voxtus.git
cd voxtus
brew install uv         # or: pip install uv
uv venv
source .venv/bin/activate
uv pip install .
```

Then run:

```bash
voxtus --help
```

---

## 📋 Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **TXT** | Plain text with timestamps | Default, LLM processing, reading |
| **JSON** | Structured data with metadata | APIs, data analysis, archival |
| **SRT** | SubRip subtitle format | Video subtitles, media players |
| **VTT** | WebVTT subtitle format | Web browsers, HTML5 video |

*Additional formats (CSV) are planned for future releases.*

### 🔧 Extensible Format System

Voxtus uses a modular format system that makes adding new output formats straightforward. Each format is implemented as a separate module with its own writer class, making the codebase maintainable and extensible.

---

## 🎛️ Model Selection

Voxtus supports multiple Whisper models with different trade-offs between speed, accuracy, and resource usage:

### Available Models

| Model | Parameters | VRAM | Languages | Best For |
|-------|------------|------|-----------|----------|
| **tiny** | 39M | ~1GB | Multilingual | Fastest inference, low resources |
| **tiny.en** | 39M | ~1GB | English only | Fastest English-only transcription |
| **base** | 74M | ~1GB | Multilingual | Good balance for minimal resources |
| **base.en** | 74M | ~1GB | English only | Balanced English-only |
| **small** | 244M | ~2GB | Multilingual | **Default balance** |
| **small.en** | 244M | ~2GB | English only | Higher accuracy English |
| **medium** | 769M | ~5GB | Multilingual | Good accuracy, slower |
| **medium.en** | 769M | ~5GB | English only | Good accuracy English |
| **distil-large-v3** | 756M | ~6GB | Multilingual | Faster with good accuracy |
| **large** | 1550M | ~10GB | Multilingual | Highest accuracy |
| **large-v2** | 1550M | ~10GB | Multilingual | Improved large model |
| **large-v3** | 1550M | ~10GB | Multilingual | Latest large model |
| **turbo** | 809M | ~6GB | Multilingual | Optimized for speed |

*VRAM requirements are from OpenAI's official specifications. Actual performance varies by hardware and audio content.*

### Model Selection Guide

```bash
# List all available models with characteristics
voxtus --list-models

# Speed-optimized (fastest)
voxtus --model tiny video.mp4

# Balanced (default)
voxtus --model small video.mp4

# Better accuracy with speed
voxtus --model distil-large-v3 video.mp4

# Quality-optimized (most accurate)
voxtus --model large-v3 video.mp4

# English-only (faster for English content)
voxtus --model small.en video.mp4
```

**💡 Tip**: English-only models (`.en`) are faster and more accurate for English content, while multilingual models work with 99+ languages.

---

## 🧪 Examples

### Basic Usage

```bash
# Transcribe to default TXT format
voxtus https://www.youtube.com/watch?v=abc123

# Transcribe local file
voxtus recording.mp3
```

### Format Selection

```bash
# Single format
voxtus -f json video.mp4

# Multiple formats at once
voxtus -f txt,json,srt,vtt video.mp4

# SRT format for video subtitles
voxtus -f srt video.mp4

# VTT format for web video
voxtus -f vtt video.mp4
```

### Advanced Usage

```bash
# Custom name and output directory
voxtus -f json -n "meeting_notes" -o ~/transcripts video.mp4

# Verbose output with audio retention
voxtus -v -k -f txt,json https://youtu.be/example

# Pipeline integration
voxtus -f json --stdout video.mp4 | jq '.metadata.duration'

# Overwrite existing files
voxtus -f json --overwrite video.mp4

# Model selection for different use cases
voxtus --model tiny -f txt video.mp4     # Fast transcription
voxtus --model large-v3 video.mp4        # Best quality
voxtus --model small.en podcast.mp3      # English podcast
```

### Real-world Examples

```bash
# Generate data for analysis
voxtus -f json -o ~/podcast_analysis podcast.mp3

# LLM processing pipeline
voxtus -f txt --stdout lecture.mp4 | llm "summarize this lecture"

# Both formats for different uses
voxtus -f txt,json -n "interview_2024" interview.mp4
```

---

## 🔧 Options

| Option | Description |
|--------|-------------|
| `-f`, `--format FORMAT` | Output format(s): txt, json, srt, vtt (comma-separated) |
| `-n, --name NAME` | Base name for output files (no extension) |
| `-o, --output DIR` | Output directory (default: current directory) |
| `-v, --verbose` | Increase verbosity (-v, -vv for debug) |
| `-k, --keep` | Keep the downloaded/converted audio file |
| `--model MODEL` | Whisper model to use (default: small) |
| `--list-models` | List available models and their characteristics |
| `--overwrite` | Overwrite existing files without confirmation |
| `--stdout` | Output to stdout (single format only) |
| `--version` | Show version and exit |

---

## 📊 JSON Format Structure

The JSON format includes rich metadata for advanced use cases:

```json
{
  "transcript": [
    {
      "id": 1,
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to our podcast."
    }
  ],
  "metadata": {
    "title": "Podcast Episode 42",
    "source": "https://youtube.com/watch?v=...",
    "duration": 1523.5,
    "model": "base",
    "language": "en"
  }
}
```

---

## 📦 Packaging

Voxtus is structured as a proper Python CLI package using `pyproject.toml` with a `voxtus` entry point.

After installation (via pip or pipx), the `voxtus` command is available directly from your shell.

---

## 🔐 License

Licensed under the **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**.

See `LICENSE` or visit [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) for more.

---

## 🔗 Project Links

- 📦 [PyPI: voxtus](https://pypi.org/project/voxtus/)
- 🧑‍💻 [Source on GitHub](https://github.com/johanthoren/voxtus)
- 🐛 [Report Issues](https://github.com/johanthoren/voxtus/issues)
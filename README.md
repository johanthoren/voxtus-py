# 🗣️ Voxtus

**Voxtus is a command-line tool for transcribing Internet videos and media files to text using [faster-whisper](https://github.com/guillaumekln/faster-whisper).**

It supports multiple output formats and can download, transcribe, and optionally retain the original audio. It's built in Python and installable as a proper CLI via PyPI or from source.

## ✨ Features

- 🎥 **Download & transcribe** videos from YouTube, Vimeo, and 1000+ sites
- 📁 **Local file support** for audio/video files  
- 📝 **Multiple output formats**: TXT, JSON
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

The project uses a simple Makefile for development tasks:

```bash
make help              # Show all available commands
make install           # Install package and dependencies
make dev-install       # Install with development dependencies
make test              # Run tests
make test-coverage     # Run tests with coverage report

# Release (bumps version, commits, tags, and pushes)
make release           # Patch release (0.1.9 -> 0.1.10)
make release patch     # Patch release (0.1.9 -> 0.1.10)
make release minor     # Minor release (0.1.9 -> 0.2.0)
make release major     # Major release (0.1.9 -> 1.0.0)
```

The release process automatically:
1. Checks that working directory is clean
2. Runs tests
3. Bumps the version in `pyproject.toml`
4. Commits the version change
5. Creates a git tag
6. Pushes commit and tag to trigger GitHub Actions CI/CD

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

*Additional formats (SRT, VTT, CSV) are planned for future releases.*

### 🔧 Extensible Format System

Voxtus uses a modular format system that makes adding new output formats straightforward. Each format is implemented as a separate module with its own writer class, making the codebase maintainable and extensible.

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
voxtus video.mp4 -f json

# Multiple formats at once
voxtus video.mp4 -f txt,json
```

### Advanced Usage

```bash
# Custom name and output directory
voxtus -f json -n "meeting_notes" -o ~/transcripts video.mp4

# Verbose output with audio retention
voxtus -v -k -f txt,json https://youtu.be/example

# Pipeline integration
voxtus video.mp4 -f json --stdout | jq '.metadata.duration'

# Overwrite existing files
voxtus video.mp4 -f json --overwrite
```

### Real-world Examples

```bash
# Generate data for analysis
voxtus podcast.mp3 -f json -o ~/podcast_analysis

# LLM processing pipeline
voxtus lecture.mp4 -f txt --stdout | llm "summarize this lecture"

# Both formats for different uses
voxtus interview.mp4 -f txt,json -n "interview_2024"
```

---

## 🔧 Options

| Option | Description |
|--------|-------------|
| `-f`, `--format FORMAT` | Output format(s): txt, json (comma-separated) |
| `-n, --name NAME` | Base name for output files (no extension) |
| `-o, --output DIR` | Output directory (default: current directory) |
| `-v, --verbose` | Increase verbosity (-v, -vv for debug) |
| `-k, --keep` | Keep the downloaded/converted audio file |
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

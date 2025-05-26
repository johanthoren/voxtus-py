# 🗣️ Voxtus

**Voxtus is a command-line tool for transcribing Internet videos and media files to text using [faster-whisper](https://github.com/guillaumekln/faster-whisper).**

It supports `.mp3` files and can download, transcribe, and optionally retain the original audio. It's built in Python and installable as a proper CLI via PyPI or from source.

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

## 🧪 Examples

```bash
# Transcribe a YouTube video to myfile.txt
voxtus -n myfile https://www.youtube.com/watch?v=abc123

# Transcribe and show output live
voxtus -v https://youtu.be/example

# Transcribe a local mp3 file and keep the audio
voxtus -k -n interview recording.mp3

# Output to a custom folder
voxtus -n meeting -o transcripts https://youtu.be/abc123
```

---

## 🔧 Options

| Option         | Description                                 |
|----------------|---------------------------------------------|
| `-v`, `--verbose` | Print each line of transcription to stdout |
| `-k`, `--keep`    | Retain the downloaded or copied audio file |
| `-n <name>`       | Base name for transcript/audio output (no extension) |
| `-o <dir>`        | Output directory (default: current working directory) |
| `-f`, `--force`   | Overwrite existing transcript without prompt |

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

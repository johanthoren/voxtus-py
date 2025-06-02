"""
Voxtus: Transcribe Internet videos and media files to text using faster-whisper.

This CLI tool supports:
- Downloading media from the Internet via the yt_dlp library
- Processing local media files (audio/video formats)
- Transcribing using the Whisper model via faster-whisper
- Multiple output formats: TXT, JSON, SRT, VTT
- Rich metadata in JSON, and VTT formats
- Multiple format output in a single run
- Optional verbose output and audio retention
- Output directory customization
- Stdout mode for pipeline integration

Output Formats:
- TXT: Plain text with timestamps (default, LLM-friendly)
- JSON: Structured data with metadata (title, source, duration, etc.)
- SRT: SubRip subtitle format for video players
- VTT: WebVTT subtitle format for web browsers with metadata (title, source, duration, etc.)

Examples:
    # Basic transcription (default TXT format)
    voxtus -f txt video.mp4

    # Basic transcription of online video
    voxtus https://youtu.be/dQw4w9WgXcQ

    # Multiple formats
    voxtus -f txt,json,srt,vtt video.mp4

    # SRT format for subtitles
    voxtus -f srt video.mp4

    # VTT format for web video
    voxtus -f vtt video.mp4

    # JSON format to stdout for processing
    voxtus -f json --stdout video.mp4 | jq '.metadata.duration'

    # Custom output name and directory
    voxtus -f json -n "my_transcript" -o ~/transcripts video.mp4

Author: Johan Thorén
License: GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

See <https://www.gnu.org/licenses/agpl-3.0.html> for full license text.
"""
import argparse
import importlib.metadata
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TypeVar, Union

from returns.pipeline import flow, is_successful
from returns.result import Failure, Result, Success, safe
from yt_dlp import YoutubeDL

from .formats import (get_supported_formats, write_format,
                      write_format_to_stdout)

__version__ = importlib.metadata.version("voxtus")

# Global context for cleanup on signal interruption
_cleanup_context: Optional['ProcessingContext'] = None

# Available Whisper models with their characteristics
AVAILABLE_MODELS = {
    "tiny": {
        "description": "Fastest model, 39M parameters",
        "params": "39M",
        "vram": "~1GB",
        "languages": "multilingual"
    },
    "tiny.en": {
        "description": "English-only tiny model",
        "params": "39M", 
        "vram": "~1GB",
        "languages": "English only"
    },
    "base": {
        "description": "Smaller balanced model, 74M parameters",
        "params": "74M",
        "vram": "~1GB", 
        "languages": "multilingual"
    },
    "base.en": {
        "description": "English-only base model",
        "params": "74M",
        "vram": "~1GB",
        "languages": "English only"
    },
    "small": {
        "description": "Default balanced model, 244M parameters",
        "params": "244M",
        "vram": "~2GB",
        "languages": "multilingual"
    },
    "small.en": {
        "description": "English-only small model",
        "params": "244M",
        "vram": "~2GB",
        "languages": "English only"
    },
    "medium": {
        "description": "Good accuracy model, 769M parameters",
        "params": "769M",
        "vram": "~5GB",
        "languages": "multilingual"
    },
    "medium.en": {
        "description": "English-only medium model", 
        "params": "769M",
        "vram": "~5GB",
        "languages": "English only"
    },
    "large": {
        "description": "Highest accuracy model, 1550M parameters",
        "params": "1550M",
        "vram": "~10GB",
        "languages": "multilingual"
    },
    "large-v2": {
        "description": "Improved large model, 1550M parameters",
        "params": "1550M",
        "vram": "~10GB", 
        "languages": "multilingual"
    },
    "large-v3": {
        "description": "Latest large model, 1550M parameters",
        "params": "1550M",
        "vram": "~10GB",
        "languages": "multilingual"
    },
    "distil-large-v3": {
        "description": "Distilled large model, faster with good accuracy, 756M parameters",
        "params": "756M",
        "vram": "~6GB",
        "languages": "multilingual"
    },
    "turbo": {
        "description": "Optimized for speed, 809M parameters",
        "params": "809M",
        "vram": "~6GB",
        "languages": "multilingual"
    }
}

def signal_handler(signum: int, frame) -> None:
    """Handle CTRL+C (SIGINT) and SIGTERM gracefully."""
    signal_names = {
        signal.SIGINT: "SIGINT (CTRL+C)",
        signal.SIGTERM: "SIGTERM"
    }
    signal_name = signal_names.get(signum, f"signal {signum}")
    print(f"\n⚠️  Received {signal_name}. Cleaning up and exiting...", file=sys.stderr)
    
    # Clean up temporary directory if context exists
    if _cleanup_context and _cleanup_context.workdir.exists():
        try:
            shutil.rmtree(_cleanup_context.workdir, ignore_errors=True)
            print(f"🗑️  Cleaned up temporary directory: {_cleanup_context.workdir}", file=sys.stderr)
        except Exception:
            pass  # Ignore cleanup errors during signal handling
    
    print("👋 Goodbye!", file=sys.stderr)
    exit_code = 130 if signum == signal.SIGINT else 143  # Standard exit codes
    sys.exit(exit_code)


@dataclass
class Config:
    """Configuration for the transcription process."""
    custom_name: Optional[str]
    formats: list[str]
    input_path: str
    keep_audio: bool
    model: str
    output_dir: Path
    overwrite_files: bool
    stdout_mode: bool
    verbose_level: int


@dataclass
class ProcessingContext:
    """Context for the processing workflow."""
    config: Config
    is_url: bool
    token: str
    vprint: Callable[[str, int], None]
    workdir: Path


def create_print_wrapper(verbose_level: int, stdout_mode: bool) -> Callable[[str, int], None]:
    """Create a print wrapper that respects verbosity and stdout mode."""
    def vprint(message: str, level: int = 0):
        """Print message if verbosity level is sufficient and not in stdout mode.
        
        Args:
            message: The message to print
            level: Required verbosity level (0=always, 1=-v, 2=-vv)
        """
        if not stdout_mode and verbose_level >= level:
            print(message, file=sys.stderr)
    
    return vprint


def create_ydl_options(debug: bool, stdout_mode: bool, output_path: Path) -> dict:
    """Create yt-dlp options based on configuration."""
    base_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'enable_file_urls': True,
    }
    
    if stdout_mode:
        base_opts.update({
            'quiet': True,
            'no_warnings': True,
            'verbose': False,
            'noprogress': True
        })
    else:
        base_opts.update({
            'quiet': not debug,
            'no_warnings': not debug,
            'verbose': debug
        })
    
    return base_opts


@safe
def extract_and_download_media(input_path: str, output_path: Path, debug: bool, stdout_mode: bool) -> str:
    """Extract media info and download audio."""
    ydl_opts = create_ydl_options(debug, stdout_mode, output_path)
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(input_path, download=False)
        title = info.get('title', 'video')
        ydl.download([input_path])
        return title


def download_audio(input_path: str, output_path: Path, debug: bool, stdout_mode: bool = False, vprint_func=None) -> Result[str, str]:
    """Download and convert audio from URL or local file."""
    result = extract_and_download_media(input_path, output_path, debug, stdout_mode)
    if not is_successful(result) and debug and not stdout_mode and vprint_func:
        vprint_func(f"❌ yt-dlp error: {result.failure()}")
        # Retry with verbose output for debugging
        return extract_and_download_media(input_path, output_path, False, stdout_mode)
    return result

def transcribe_to_formats(audio_file: Path, base_output_path: Path, formats: list[str], title: str, source: str, verbose: bool, verbose_level: int, vprint_func: Callable[[str, int], None], model_name: str = "small") -> list[Path]:
    """Transcribe audio to multiple formats using specified Whisper model.
    
    Args:
        audio_file: Path to the audio file to transcribe
        base_output_path: Base path for output files (without extension)
        formats: List of output formats to generate
        title: Title for the transcript metadata
        source: Source identifier for the media
        verbose: Whether to show verbose output
        verbose_level: Verbosity level (0=normal, 1=verbose, 2=debug)
        vprint_func: Function for verbose printing
        model_name: Whisper model to use (default: "small")
        
    Returns:
        List of paths to the generated output files
    """
    from faster_whisper import WhisperModel
    
    vprint_func("⏳ Loading transcription model (this may take a few seconds the first time)...")
    
    # Suppress faster-whisper RuntimeWarnings during model loading and transcription
    # unless in debug mode (-vv)
    if verbose_level < 2:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            model = WhisperModel(model_name, compute_type="auto")
            segments, info = model.transcribe(str(audio_file))
    else:
        model = WhisperModel(model_name, compute_type="auto")
        segments, info = model.transcribe(str(audio_file))

    vprint_func("🎤 Starting transcription...")
    total_duration = info.duration if hasattr(info, 'duration') else None
    
    # Collect all segments for format writers
    segments_list = []
    for segment in segments:
        segments_list.append(segment)
        
        # Show progress based on segment timing (but not in verbose mode to avoid interference)
        if not verbose and total_duration and segment.end > 0:
            progress_percent = min(100, (segment.end / total_duration) * 100)
            # Use \r to overwrite the same line instead of creating new lines
            print(f"\r📝 Transcribing... {progress_percent:.1f}% ({segment.end:.1f}s / {total_duration:.1f}s)", end="", file=sys.stderr)
    
    # Ensure we show 100% completion at the end (only if we were showing progress)
    if not verbose and total_duration:
        print(f"\r📝 Transcribing... 100.0% ({total_duration:.1f}s / {total_duration:.1f}s)", file=sys.stderr)
    
    # Write all requested formats using the new format system
    output_files = []
    for fmt in formats:
        output_file = base_output_path.with_suffix(f".{fmt}")
        write_format(fmt, segments_list, output_file, title, source, info, verbose, vprint_func, model_name)
        output_files.append(output_file)
    
    return output_files


def transcribe_to_stdout(audio_file: Path, format_type: str, title: str, source: str, verbose_level: int, model_name: str = "small"):
    """Transcribe audio directly to stdout in specified format using Whisper model.
    
    Args:
        audio_file: Path to the audio file to transcribe
        format_type: Output format (txt, json, srt, vtt)
        title: Title for the transcript metadata
        source: Source identifier for the media
        verbose_level: Verbosity level (0=normal, 1=verbose, 2=debug)
        model_name: Whisper model to use (default: "small")
    """
    from faster_whisper import WhisperModel

    # Suppress faster-whisper RuntimeWarnings during model loading and transcription
    # unless in debug mode (-vv)
    if verbose_level < 2:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            model = WhisperModel(model_name, compute_type="auto")
            segments, info = model.transcribe(str(audio_file))
    else:
        model = WhisperModel(model_name, compute_type="auto")
        segments, info = model.transcribe(str(audio_file))

    segments_list = list(segments)
    write_format_to_stdout(format_type, segments_list, title, source, info, model_name)


def check_ffmpeg(vprint_func: Callable[[str, int], None]):
    """Check if ffmpeg is available."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        vprint_func("❌ ffmpeg is required but not found. Please install ffmpeg:")
        vprint_func("  - macOS: brew install ffmpeg")
        vprint_func("  - Ubuntu/Debian: sudo apt install ffmpeg")
        vprint_func("  - Windows: Download from https://ffmpeg.org/download.html")
        sys.exit(1)


@safe
def validate_input_file(file_path: str) -> Path:
    """Validate that input file exists and return resolved path."""
    source_file = Path(file_path).expanduser().resolve()
    if not source_file.exists():
        raise ValueError(f"File not found: {source_file}")
    return source_file


def create_output_template(workdir: Path, token: str) -> Path:
    """Create output template path for yt-dlp."""
    return workdir / f"{token}.%(ext)s"


@safe
def find_audio_file(workdir: Path, token: str) -> Path:
    """Find the generated audio file and validate it exists."""
    audio_file = workdir / f"{token}.mp3"
    if not audio_file.exists():
        raise ValueError("Audio file not found")
    return audio_file


def download_media_from_url(ctx: ProcessingContext, output_template: Path) -> Result[str, str]:
    """Download media from URL."""
    return download_audio(
        ctx.config.input_path, 
        output_template, 
        ctx.config.verbose_level >= 2 and not ctx.config.stdout_mode, 
        ctx.config.stdout_mode, 
        ctx.vprint
    )


def find_audio_file_with_context(ctx: ProcessingContext) -> Result[Path, str]:
    """Find audio file using context."""
    return find_audio_file(ctx.workdir, ctx.token)


def log_and_combine_results(ctx: ProcessingContext, title: str, audio_file: Path) -> tuple[str, Path]:
    """Log and combine results."""
    ctx.vprint(f"📁 Found audio file: '{audio_file}'", 2)
    return title, audio_file


def process_url_input(ctx: ProcessingContext) -> Result[tuple[str, Path], str]:
    """Process URL input and return title and audio file path."""
    ctx.vprint(f"🎧 Downloading media from: {ctx.config.input_path}")
    output_template = create_output_template(ctx.workdir, ctx.token)
    
    return (
        download_media_from_url(ctx, output_template)
        .bind(lambda title: 
            find_audio_file_with_context(ctx)
            .map(lambda audio_file: log_and_combine_results(ctx, title, audio_file))
        )
    )


def convert_local_file(ctx: ProcessingContext, source_file: Path) -> Result[str, str]:
    """Convert a validated local file to audio."""
    ctx.vprint(f"🎧 Converting media file: '{source_file}'")
    output_template = create_output_template(ctx.workdir, ctx.token)
    file_url = f"file://{source_file}"
    
    return download_audio(
        file_url, 
        output_template, 
        ctx.config.verbose_level >= 2 and not ctx.config.stdout_mode, 
        ctx.config.stdout_mode, 
        ctx.vprint
    )


def process_file_input(ctx: ProcessingContext) -> Result[tuple[str, Path], str]:
    """Process local file input and return title and audio file path."""
    return (
        validate_input_file(ctx.config.input_path)
        .bind(lambda source_file: 
            convert_local_file(ctx, source_file)
            .bind(lambda title:
                find_audio_file_with_context(ctx)
                .map(lambda audio_file: log_and_combine_results(ctx, title, audio_file))
            )
        )
    )


def get_final_name(title: str, custom_name: Optional[str]) -> str:
    """Determine the final name for output files."""
    return custom_name if custom_name else title


@safe
def check_file_overwrite(final_transcript: Path, overwrite_files: bool) -> None:
    """Check if file should be overwritten and handle user confirmation."""
    if final_transcript.exists() and not overwrite_files:
        try:
            response = input(f"⚠️ Transcript file '{final_transcript}' already exists. Overwrite? [y/N] ").lower()
            if response != 'y':
                raise ValueError("User aborted")
        except EOFError:
            # Handle CTRL+D (EOF) gracefully
            print("\n⚠️  EOF received. Aborting operation.", file=sys.stderr)
            raise ValueError("User aborted with EOF")
        except KeyboardInterrupt:
            # Handle CTRL+C gracefully (though signal handler should catch this)
            print("\n⚠️  Interrupted by user. Aborting operation.", file=sys.stderr)
            raise ValueError("User interrupted")


def create_transcript_file(audio_file: Path, ctx: ProcessingContext, title: str) -> list[Path]:
    """Create transcript files in all requested formats."""
    base_name = audio_file.with_suffix("")
    return transcribe_to_formats(
        audio_file, 
        base_name, 
        ctx.config.formats, 
        title, 
        ctx.config.input_path, 
        ctx.config.verbose_level >= 1, 
        ctx.config.verbose_level, 
        ctx.vprint,
        ctx.config.model
    )


def move_files_and_log(ctx: ProcessingContext, audio_file: Path, transcript_files: list[Path], final_name: str) -> None:
    """Handle file moving and logging for multiple format files."""
    # Move all transcript files
    final_files = []
    for transcript_file in transcript_files:
        final_transcript = ctx.config.output_dir / f"{final_name}{transcript_file.suffix}"
        shutil.move(str(transcript_file), final_transcript)
        final_files.append(final_transcript)
    
    if ctx.config.keep_audio:
        final_audio = ctx.config.output_dir / f"{final_name}.mp3"
        shutil.move(str(audio_file), final_audio)
        ctx.vprint(f"📁 Audio file kept: '{final_audio}'")
    else:
        ctx.vprint(f"🗑️ Audio file discarded", 2)
    
    for final_file in final_files:
        ctx.vprint(f"✅ Transcript saved to: '{final_file}'")


def transcribe_and_save(ctx: ProcessingContext, audio_file: Path, title: str) -> Result[None, str]:
    """Transcribe audio and save files after validation."""
    final_name = get_final_name(title, ctx.config.custom_name)
    ctx.vprint(f"📝 Transcribing to multiple formats...", 2)
    ctx.vprint("📝 Transcribing audio...", 1)
    
    transcript_files = create_transcript_file(audio_file, ctx, title)
    move_files_and_log(ctx, audio_file, transcript_files, final_name)
    return Success(None)


def handle_file_output(ctx: ProcessingContext, audio_file: Path, title: str) -> Result[None, str]:
    """Handle file-based output (non-stdout mode)."""
    final_name = get_final_name(title, ctx.config.custom_name)
    
    # Check if any output files would be overwritten
    for fmt in ctx.config.formats:
        final_file = ctx.config.output_dir / f"{final_name}.{fmt}"
        overwrite_check = check_file_overwrite(final_file, ctx.config.overwrite_files)
        if not is_successful(overwrite_check):
            return overwrite_check
    
    return transcribe_and_save(ctx, audio_file, title)


def handle_stdout_output(ctx: ProcessingContext, audio_file: Path, title: str):
    """Handle stdout-based output."""
    format_type = ctx.config.formats[0]  # Already validated to be single format
    transcribe_to_stdout(audio_file, format_type, title, ctx.config.input_path, ctx.config.verbose_level, ctx.config.model)


def process_audio(ctx: ProcessingContext) -> Result[None, str]:
    """Main audio processing workflow."""
    input_processor = process_url_input if ctx.is_url else process_file_input
    
    return (
        input_processor(ctx)
        .bind(lambda result: 
            Success(handle_stdout_output(ctx, result[1], result[0])) if ctx.config.stdout_mode
            else handle_file_output(ctx, result[1], result[0])
        )
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Transcribe Internet videos and media files to text using faster-whisper.")
    parser.add_argument("input", nargs='?', help="Internet URL or local media file (optional if --version is used)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (use -vv for debug output)")
    parser.add_argument("-k", "--keep", action="store_true", help="Keep the audio file")
    parser.add_argument("-f", "--format", default="txt", help="Output format(s) (comma-separated): txt, json, srt, vtt")
    parser.add_argument("-n", "--name", help="Base name for audio and transcript file (no extension)")
    parser.add_argument("-o", "--output", help="Directory to save output files to (default: current directory)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite any existing transcript file without confirmation")
    parser.add_argument("--stdout", action="store_true", help="Output transcript to stdout only (no file written, all other output silenced)")
    parser.add_argument("--model", help="Whisper model to use (default: small). Use --list-models to see available options")
    parser.add_argument("--list-models", action="store_true", help="List available Whisper models and their characteristics")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help="Show program's version number and exit")
    return parser.parse_args()


def validate_arguments(args: argparse.Namespace):
    """Validate parsed arguments."""
    if not args.input and not any(arg in sys.argv for arg in ['--version', '-h', '--help', '--list-models']):
        parser = argparse.ArgumentParser()
        parser.print_help(sys.stderr)
        sys.exit(1)


def parse_and_validate_formats(format_string: str, stdout_mode: bool) -> list[str]:
    """Parse and validate format string."""
    supported_formats = set(get_supported_formats())
    
    formats = [fmt.strip().lower() for fmt in format_string.split(',')]
    
    # Validate formats
    invalid_formats = [fmt for fmt in formats if fmt not in supported_formats]
    if invalid_formats:
        print(f"Error: Invalid format(s): {', '.join(invalid_formats)}", file=sys.stderr)
        print(f"Supported formats: {', '.join(sorted(supported_formats))}", file=sys.stderr)
        sys.exit(1)
    
    # Check stdout compatibility
    if stdout_mode and len(formats) > 1:
        print("Error: Only one format allowed when using --stdout", file=sys.stderr)
        sys.exit(1)
    
    return formats


def create_config(args: argparse.Namespace) -> Config:
    """Create configuration from parsed arguments."""
    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    custom_name = args.name
    if custom_name and custom_name.endswith('.txt'):
        custom_name = custom_name[:-4]  # Remove .txt extension
    
    model = args.model or "small"  # Default to "small" if no model specified
    if model:
        model = validate_model(model)
    
    return Config(
        input_path=args.input,
        verbose_level=args.verbose,
        keep_audio=args.keep,
        overwrite_files=args.overwrite,
        custom_name=custom_name,
        output_dir=output_dir,
        stdout_mode=args.stdout,
        formats=parse_and_validate_formats(args.format, args.stdout),
        model=model
    )


def create_processing_context(config: Config) -> ProcessingContext:
    """Create processing context."""
    vprint = create_print_wrapper(config.verbose_level, config.stdout_mode)
    workdir = Path(tempfile.mkdtemp())
    is_url = config.input_path.startswith("http")
    token = str(uuid.uuid4())
    
    return ProcessingContext(
        config=config,
        vprint=vprint,
        workdir=workdir,
        is_url=is_url,
        token=token
    )


def list_available_models() -> None:
    """Display available Whisper models with their characteristics."""
    print("🎤 Available Whisper Models:\n")
    
    # Group models by size for better display
    model_groups = {
        "Tiny Models": ["tiny", "tiny.en"],
        "Base Models": ["base", "base.en"], 
        "Small Models": ["small", "small.en"],
        "Medium Models": ["medium", "medium.en"],
        "Large Models": ["distil-large-v3", "large-v3", "large", "turbo"]
    }
    
    for group_name, models in model_groups.items():
        print(f"📂 {group_name}:")
        for model in models:
            if model in AVAILABLE_MODELS:
                info = AVAILABLE_MODELS[model]
                print(f"   {model:<18} - {info['description']}")
                print(f"                      📊 {info['params']} params, {info['vram']} VRAM, {info['languages']}")
        print()
    
    print("💡 Usage examples:")
    print("   voxtus --model tiny video.mp4            # Fastest transcription")
    print("   voxtus --model small video.mp4           # Good balance (default)")
    print("   voxtus --model distil-large-v3 video.mp4 # Better accuracy, faster than large")
    print("   voxtus --model large-v3 video.mp4        # Best accuracy")
    print("   voxtus --model small.en audio.mp3        # English-only, faster")


def validate_model(model: str) -> str:
    """Validate and normalize the model name."""
    if model not in AVAILABLE_MODELS:
        print(f"❌ Error: Unknown model '{model}'", file=sys.stderr)
        print("\n📋 Available models:", file=sys.stderr)
        for model_name in AVAILABLE_MODELS.keys():
            print(f"   - {model_name}", file=sys.stderr)
        print("\n💡 Use 'voxtus --list-models' to see detailed information", file=sys.stderr)
        sys.exit(1)
    
    # Normalize "large" to "large-v3"
    if model == "large":
        return "large-v3"
    
    return model


def main() -> None:
    """Main entry point."""
    global _cleanup_context
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        args = parse_arguments()
        
        # Handle --list-models before other validation
        if args.list_models:
            list_available_models()
            sys.exit(0)
        
        validate_arguments(args)
        config = create_config(args)
        ctx = create_processing_context(config)
        
        # Set global context for signal handler cleanup
        _cleanup_context = ctx
        
        check_ffmpeg(ctx.vprint)
        
        try:
            result = process_audio(ctx)
            if not is_successful(result):
                print(f"Error: {result.failure()}", file=sys.stderr)
                sys.exit(1)
        except KeyboardInterrupt:
            # Additional KeyboardInterrupt handling (backup to signal handler)
            print(f"\n⚠️  Operation interrupted by user.", file=sys.stderr)
            sys.exit(130)
            
    except KeyboardInterrupt:
        # Handle interruption during setup phase
        print(f"\n⚠️  Setup interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except EOFError:
        # Handle EOF during any input operations
        print(f"\n⚠️  EOF received during input. Exiting.", file=sys.stderr)
        sys.exit(1)
    finally:
        # Always clean up, even if _cleanup_context is None
        if _cleanup_context and _cleanup_context.workdir.exists():
            shutil.rmtree(_cleanup_context.workdir, ignore_errors=True)
        _cleanup_context = None


if __name__ == "__main__":
    main()

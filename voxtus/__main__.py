"""
Voxtus: Transcribe Internet videos and media files to text using faster-whisper.

This CLI tool supports:
- Downloading media from the Internet via the yt_dlp library
- Converting local media files to mp3 format
- Transcribing using the Whisper model via faster-whisper
- Saving transcripts in .txt format
- Optional verbose output and audio retention
- Output directory customization

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
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TypeVar, Union

from faster_whisper import WhisperModel
from returns.pipeline import flow, is_successful
from returns.result import Failure, Result, Success, safe
from yt_dlp import YoutubeDL

__version__ = importlib.metadata.version("voxtus")


@dataclass
class Config:
    """Configuration for the transcription process."""
    custom_name: Optional[str]
    force_overwrite: bool
    input_path: str
    keep_audio: bool
    output_dir: Path
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
            'preferredquality': '192',
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


def format_transcript_line(segment) -> str:
    """Format a transcript segment into a line."""
    return f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"


def transcribe_to_file(audio_file: Path, output_file: Path, verbose: bool, vprint_func: Callable[[str, int], None]):
    """Transcribe audio to a file."""
    vprint_func("⏳ Loading transcription model (this may take a few seconds the first time)...")
    model = WhisperModel("base", compute_type="auto")
    segments, _ = model.transcribe(str(audio_file))

    with output_file.open("w", encoding="utf-8") as f:
        for segment in segments:
            line = format_transcript_line(segment)
            f.write(line + "\n")
            if verbose:
                vprint_func(line, 1)


def transcribe_to_stdout(audio_file: Path):
    """Transcribe audio directly to stdout."""
    model = WhisperModel("base", compute_type="auto")
    segments, _ = model.transcribe(str(audio_file))

    for segment in segments:
        line = format_transcript_line(segment)
        print(line)


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
def check_file_overwrite(final_transcript: Path, force_overwrite: bool) -> None:
    """Check if file should be overwritten and handle user confirmation."""
    if final_transcript.exists() and not force_overwrite:
        response = input(f"⚠️ Transcript file '{final_transcript}' already exists. Overwrite? [y/N] ").lower()
        if response != 'y':
            raise ValueError("User aborted")


def create_transcript_file(audio_file: Path, ctx: ProcessingContext) -> Path:
    """Create transcript file."""
    transcript_file = audio_file.with_suffix(".txt")
    transcribe_to_file(audio_file, transcript_file, ctx.config.verbose_level >= 1, ctx.vprint)
    return transcript_file


def move_files_and_log(ctx: ProcessingContext, audio_file: Path, transcript_file: Path, final_name: str) -> None:
    """Handle file moving and logging."""
    final_transcript = ctx.config.output_dir / f"{final_name}.txt"
    shutil.move(str(transcript_file), final_transcript)
    
    if ctx.config.keep_audio:
        final_audio = ctx.config.output_dir / f"{final_name}.mp3"
        shutil.move(str(audio_file), final_audio)
        ctx.vprint(f"📁 Audio file kept: '{final_audio}'")
    else:
        ctx.vprint(f"🗑️ Audio file discarded", 2)
    
    ctx.vprint(f"✅ Transcript saved to: '{final_transcript}'")


def transcribe_and_save(ctx: ProcessingContext, audio_file: Path, title: str) -> Result[None, str]:
    """Transcribe audio and save files after validation."""
    final_name = get_final_name(title, ctx.config.custom_name)
    ctx.vprint(f"📝 Transcribing to '{audio_file.with_suffix('.txt').name}'...", 2)
    ctx.vprint("📝 Transcribing audio...", 1)
    
    transcript_file = create_transcript_file(audio_file, ctx)
    move_files_and_log(ctx, audio_file, transcript_file, final_name)
    return Success(None)


def handle_file_output(ctx: ProcessingContext, audio_file: Path, title: str) -> Result[None, str]:
    """Handle file-based output (non-stdout mode)."""
    final_name = get_final_name(title, ctx.config.custom_name)
    final_transcript = ctx.config.output_dir / f"{final_name}.txt"
    
    return (
        check_file_overwrite(final_transcript, ctx.config.force_overwrite)
        .bind(lambda _: transcribe_and_save(ctx, audio_file, title))
    )


def handle_stdout_output(audio_file: Path):
    """Handle stdout-based output."""
    transcribe_to_stdout(audio_file)


def process_audio(ctx: ProcessingContext) -> Result[None, str]:
    """Main audio processing workflow."""
    input_processor = process_url_input if ctx.is_url else process_file_input
    
    return (
        input_processor(ctx)
        .bind(lambda result: 
            Success(handle_stdout_output(result[1])) if ctx.config.stdout_mode
            else handle_file_output(ctx, result[1], result[0])
        )
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Transcribe Internet videos and media files to text using faster-whisper.")
    parser.add_argument("input", nargs='?', help="Internet URL or local media file (optional if --version is used)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (use -vv for debug output)")
    parser.add_argument("-k", "--keep", action="store_true", help="Keep the audio file")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite any existing transcript file without confirmation")
    parser.add_argument("-n", "--name", help="Base name for audio and transcript file (no extension)")
    parser.add_argument("-o", "--output", help="Directory to save output files to (default: current directory)")
    parser.add_argument("--stdout", action="store_true", help="Output transcript to stdout only (no file written, all other output silenced)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help="Show program's version number and exit")
    return parser.parse_args()


def validate_arguments(args: argparse.Namespace):
    """Validate parsed arguments."""
    if not args.input and not any(arg in sys.argv for arg in ['--version', '-h', '--help']):
        parser = argparse.ArgumentParser()
        parser.print_help(sys.stderr)
        sys.exit(1)


def create_config(args: argparse.Namespace) -> Config:
    """Create configuration from parsed arguments."""
    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    custom_name = args.name
    if custom_name and custom_name.endswith('.txt'):
        custom_name = custom_name[:-4]  # Remove .txt extension
    
    return Config(
        input_path=args.input,
        verbose_level=args.verbose,
        keep_audio=args.keep,
        force_overwrite=args.force,
        custom_name=custom_name,
        output_dir=output_dir,
        stdout_mode=args.stdout
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


def main() -> None:
    """Main entry point."""
    args = parse_arguments()
    validate_arguments(args)
    config = create_config(args)
    ctx = create_processing_context(config)
    check_ffmpeg(ctx.vprint)
    
    try:
        result = process_audio(ctx)
        if not is_successful(result):
            print(f"Error: {result.failure()}", file=sys.stderr)
            sys.exit(1)
    finally:
        shutil.rmtree(ctx.workdir, ignore_errors=True)


if __name__ == "__main__":
    main()

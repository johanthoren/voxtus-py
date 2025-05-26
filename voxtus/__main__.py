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
from typing import Callable, Optional

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL

__version__ = importlib.metadata.version("voxtus")


@dataclass
class Config:
    """Configuration for the transcription process."""
    input_path: str
    verbose_level: int
    keep_audio: bool
    force_overwrite: bool
    custom_name: Optional[str]
    output_dir: Path
    stdout_mode: bool


@dataclass
class ProcessingContext:
    """Context for the processing workflow."""
    config: Config
    vprint: Callable[[str, int], None]
    workdir: Path
    is_url: bool
    token: str


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


def extract_and_download_media(input_path: str, output_path: Path, debug: bool, stdout_mode: bool) -> str:
    """Extract media info and download audio."""
    ydl_opts = create_ydl_options(debug, stdout_mode, output_path)
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(input_path, download=False)
        title = info.get('title', 'video')
        ydl.download([input_path])
        return title


def download_audio(input_path: str, output_path: Path, debug: bool, stdout_mode: bool = False, vprint_func=None) -> str:
    """Download and convert audio from URL or local file."""
    try:
        return extract_and_download_media(input_path, output_path, debug, stdout_mode)
    except Exception as e:
        if debug and not stdout_mode and vprint_func:
            vprint_func(f"❌ yt-dlp error: {e}")
            # Retry with verbose output for debugging
            return extract_and_download_media(input_path, output_path, False, stdout_mode)
        raise


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


def validate_input_file(file_path: str, vprint_func: Callable[[str, int], None]) -> Path:
    """Validate that input file exists and return resolved path."""
    source_file = Path(file_path).expanduser().resolve()
    if not source_file.exists():
        vprint_func(f"❌ Local file not found: '{source_file}'")
        sys.exit(1)
    return source_file


def create_output_template(workdir: Path, token: str) -> Path:
    """Create output template path for yt-dlp."""
    return workdir / f"{token}.%(ext)s"


def find_audio_file(workdir: Path, token: str, vprint_func: Callable[[str, int], None]) -> Path:
    """Find the generated audio file and validate it exists."""
    audio_file = workdir / f"{token}.mp3"
    if not audio_file.exists():
        vprint_func("❌ No audio file found after processing.")
        vprint_func(f"Expected file: '{audio_file}'", 2)
        vprint_func(f"Files in workdir: {[str(f) for f in workdir.glob('*')]}", 2)
        sys.exit(1)
    return audio_file


def process_url_input(ctx: ProcessingContext) -> tuple[str, Path]:
    """Process URL input and return title and audio file path."""
    ctx.vprint(f"🎧 Downloading media from: {ctx.config.input_path}")
    output_template = create_output_template(ctx.workdir, ctx.token)
    
    try:
        title = download_audio(
            ctx.config.input_path, 
            output_template, 
            ctx.config.verbose_level >= 2 and not ctx.config.stdout_mode, 
            ctx.config.stdout_mode, 
            ctx.vprint
        )
    except Exception as e:
        ctx.vprint(f"❌ Error downloading media: {e}")
        sys.exit(1)

    audio_file = find_audio_file(ctx.workdir, ctx.token, ctx.vprint)
    ctx.vprint(f"📁 Found audio file: '{audio_file}'", 2)
    return title, audio_file


def process_file_input(ctx: ProcessingContext) -> tuple[str, Path]:
    """Process local file input and return title and audio file path."""
    source_file = validate_input_file(ctx.config.input_path, ctx.vprint)
    ctx.vprint(f"🎧 Converting media file: '{source_file}'")
    
    output_template = create_output_template(ctx.workdir, ctx.token)
    file_url = f"file://{source_file}"
    
    try:
        title = download_audio(
            file_url, 
            output_template, 
            ctx.config.verbose_level >= 2 and not ctx.config.stdout_mode, 
            ctx.config.stdout_mode, 
            ctx.vprint
        )
    except Exception as e:
        ctx.vprint(f"❌ Error processing media file: {e}")
        ctx.vprint("The file format may not be supported. Please ensure it's a valid media file.")
        sys.exit(1)

    audio_file = find_audio_file(ctx.workdir, ctx.token, ctx.vprint)
    return title, audio_file


def get_final_name(title: str, custom_name: Optional[str]) -> str:
    """Determine the final name for output files."""
    return custom_name if custom_name else title


def check_file_overwrite(final_transcript: Path, force_overwrite: bool, vprint_func: Callable[[str, int], None]):
    """Check if file should be overwritten and handle user confirmation."""
    if final_transcript.exists() and not force_overwrite:
        response = input(f"⚠️ Transcript file '{final_transcript}' already exists. Overwrite? [y/N] ").lower()
        if response != 'y':
            vprint_func("Aborted.")
            sys.exit(0)
    elif final_transcript.exists() and force_overwrite:
        vprint_func(f"⚠️ Option --force used. Overwriting existing '{final_transcript}' without confirmation.")


def handle_file_output(ctx: ProcessingContext, audio_file: Path, title: str):
    """Handle file-based output (non-stdout mode)."""
    final_name = get_final_name(title, ctx.config.custom_name)
    final_transcript = ctx.config.output_dir / f"{final_name}.txt"
    
    check_file_overwrite(final_transcript, ctx.config.force_overwrite, ctx.vprint)
    
    ctx.vprint(f"📝 Transcribing to '{audio_file.with_suffix('.txt').name}'...", 2)
    ctx.vprint("📝 Transcribing audio...", 1)
    
    # Transcribe to temporary file
    transcript_file = audio_file.with_suffix(".txt")
    transcribe_to_file(audio_file, transcript_file, ctx.config.verbose_level >= 1, ctx.vprint)
    
    # Move to final location
    shutil.move(str(transcript_file), final_transcript)
    
    # Handle audio file
    if ctx.config.keep_audio:
        final_audio = ctx.config.output_dir / f"{final_name}.mp3"
        shutil.move(str(audio_file), final_audio)
        ctx.vprint(f"📁 Audio file kept: '{final_audio}'")
    else:
        ctx.vprint(f"🗑️ Audio file discarded", 2)
    
    ctx.vprint(f"✅ Transcript saved to: '{final_transcript}'")


def handle_stdout_output(audio_file: Path):
    """Handle stdout-based output."""
    transcribe_to_stdout(audio_file)


def process_audio(ctx: ProcessingContext):
    """Main audio processing workflow."""
    # Process input based on type
    if ctx.is_url:
        title, audio_file = process_url_input(ctx)
    else:
        title, audio_file = process_file_input(ctx)
    
    # Handle output based on mode
    if ctx.config.stdout_mode:
        handle_stdout_output(audio_file)
    else:
        handle_file_output(ctx, audio_file, title)


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


def main():
    """Main entry point."""
    args = parse_arguments()
    validate_arguments(args)
    
    config = create_config(args)
    ctx = create_processing_context(config)
    
    check_ffmpeg(ctx.vprint)
    
    try:
        process_audio(ctx)
    finally:
        shutil.rmtree(ctx.workdir, ignore_errors=True)


if __name__ == "__main__":
    main()

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
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL

__version__ = importlib.metadata.version("voxtus")


def create_print_wrapper(verbose_level: int, stdout_mode: bool):
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


def download_audio(input_path: str, output_path: Path, debug: bool, stdout_mode: bool = False, vprint_func=None):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': not debug or stdout_mode,
        'no_warnings': not debug or stdout_mode,
        'enable_file_urls': True,
        'verbose': debug and not stdout_mode
    }
    
    # In stdout mode, completely suppress all output
    if stdout_mode:
        ydl_opts['quiet'] = True
        ydl_opts['no_warnings'] = True
        ydl_opts['verbose'] = False
        ydl_opts['noprogress'] = True

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(input_path, download=False)
            title = info.get('title', 'video')
            ydl.download([input_path])
            return title
    except Exception as e:
        if debug and not stdout_mode and vprint_func:
            vprint_func(f"❌ yt-dlp error: {e}")
            # Try again with verbose output to see what's happening
            ydl_opts['quiet'] = False
            ydl_opts['no_warnings'] = False
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(input_path, download=False)
                title = info.get('title', 'video')
                ydl.download([input_path])
                return title
        raise

def transcribe_audio(audio_file: Path, output_file: Path, verbose: bool, vprint_func=None):
    if vprint_func:
        vprint_func("⏳ Loading transcription model (this may take a few seconds the first time)...")
    else:
        print("⏳ Loading transcription model (this may take a few seconds the first time)...", file=sys.stderr)
    model = WhisperModel("base", compute_type="auto")
    segments, _ = model.transcribe(str(audio_file))

    with output_file.open("w", encoding="utf-8") as f:
        for segment in segments:
            line = f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"
            f.write(line + "\n")
            if verbose:
                if vprint_func:
                    vprint_func(line, 1)
                else:
                    print(line, file=sys.stderr)

def check_ffmpeg(vprint_func=None):
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        if vprint_func:
            vprint_func("❌ ffmpeg is required but not found. Please install ffmpeg:")
            vprint_func("  - macOS: brew install ffmpeg")
            vprint_func("  - Ubuntu/Debian: sudo apt install ffmpeg")
            vprint_func("  - Windows: Download from https://ffmpeg.org/download.html")
        else:
            print("❌ ffmpeg is required but not found. Please install ffmpeg:", file=sys.stderr)
            print("  - macOS: brew install ffmpeg", file=sys.stderr)
            print("  - Ubuntu/Debian: sudo apt install ffmpeg", file=sys.stderr)
            print("  - Windows: Download from https://ffmpeg.org/download.html", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Transcribe Internet videos and media files to text using faster-whisper.")
    parser.add_argument("input", nargs='?', help="Internet URL or local media file (optional if --version is used)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (use -vv for debug output)")
    parser.add_argument("-k", "--keep", action="store_true", help="Keep the audio file")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite any existing transcript file without confirmation")
    parser.add_argument("-n", "--name", help="Base name for audio and transcript file (no extension)")
    parser.add_argument("-o", "--output", help="Directory to save output files to (default: current directory)")
    parser.add_argument("--stdout", action="store_true", help="Output transcript to stdout only (no file written, all other output silenced)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help="Show program's version number and exit")

    args = parser.parse_args()
    
    # If --version is used, argparse handles it and exits.
    # If no input is provided and --version is not used, print help and exit.
    if not args.input and not any(arg in sys.argv for arg in ['--version', '-h', '--help']):
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Create print wrapper
    vprint = create_print_wrapper(args.verbose, args.stdout)
    
    check_ffmpeg(vprint)  # Check for ffmpeg before proceeding
    input_arg = args.input
    custom_name = args.name
    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    if custom_name and custom_name.endswith('.txt'):
        custom_name = custom_name[:-4]  # Remove .txt extension

    is_url = input_arg.startswith("http")
    workdir = Path(tempfile.mkdtemp())
    force_overwrite = args.force
    audio_file = None
    transcript_file = None
    stdout_mode = args.stdout

    try:
        # Determine the final transcript path early
        if is_url:
            base = custom_name or "%(title)s"
        else:
            source_file = Path(input_arg).expanduser().resolve()
            if not source_file.exists():
                vprint(f"❌ Local file not found: '{source_file}'")
                sys.exit(1)
            base = custom_name or source_file.stem

        if is_url:
            vprint(f"🎧 Downloading media from: {input_arg}")
            token = str(uuid.uuid4())
            output_template = workdir / f"{token}.%(ext)s"
            try:
                title = download_audio(input_arg, output_template, args.verbose >= 2 and not stdout_mode, stdout_mode, vprint)
            except Exception as e:
                vprint(f"❌ Error downloading media: {e}")
                sys.exit(1)

            # Look for the mp3 file
            audio_file = workdir / f"{token}.mp3"
            if not audio_file.exists():
                vprint("❌ No audio file found after processing.")
                vprint(f"Expected file: '{audio_file}'", 2)
                vprint(f"Files in workdir: {[str(f) for f in workdir.glob('*')]}", 2)
                sys.exit(1)

            vprint(f"📁 Found audio file: '{audio_file}'", 2)
        else:
            source_file = Path(input_arg).expanduser().resolve()
            if not source_file.exists():
                vprint(f"❌ Local file not found: '{source_file}'")
                sys.exit(1)
            
            vprint(f"🎧 Converting media file: '{source_file}'")
            token = str(uuid.uuid4())
            output_template = workdir / f"{token}.%(ext)s"
            file_url = f"file://{source_file}"
            try:
                title = download_audio(file_url, output_template, args.verbose >= 2 and not stdout_mode, stdout_mode, vprint)
            except Exception as e:
                vprint(f"❌ Error processing media file: {e}")
                vprint("The file format may not be supported. Please ensure it's a valid media file.")
                sys.exit(1)

        # Look for the specific mp3 file we created
        audio_file = workdir / f"{token}.mp3"
        if not audio_file.exists():
            vprint("❌ No audio file found after processing.")
            sys.exit(1)

        if not stdout_mode:
            # Use custom name if provided, otherwise use the extracted title
            final_name = custom_name if custom_name else title
            final_transcript = output_dir / f"{final_name}.txt"
            if final_transcript.exists() and not force_overwrite:
                response = input(f"⚠️ Transcript file '{final_transcript}' already exists. Overwrite? [y/N] ").lower()
                if response != 'y':
                    vprint("Aborted.")
                    sys.exit(0)
            elif final_transcript.exists() and force_overwrite:
                vprint(f"⚠️ Option --force used. Overwriting existing '{final_transcript}' without confirmation.")

        vprint(f"📝 Transcribing to '{audio_file.with_suffix('.txt').name}'...", 2)
        vprint("📝 Transcribing audio...", 1)

        if stdout_mode:
            # For stdout mode, transcribe directly to stdout
            model = WhisperModel("base", compute_type="auto")
            segments, _ = model.transcribe(str(audio_file))

            for segment in segments:
                line = f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"
                print(line)
        else:
            # Normal file mode
            transcript_file = audio_file.with_suffix(".txt")
            transcribe_audio(audio_file, transcript_file, args.verbose >= 1, vprint)

            # Move result to output directory with the actual title
            shutil.move(str(transcript_file), final_transcript)

            if args.keep:
                final_audio = output_dir / f"{final_name}.mp3"
                shutil.move(str(audio_file), final_audio)
                vprint(f"📁 Audio file kept: '{final_audio}'")
            else:
                vprint(f"🗑️ Audio file discarded", 2)

            vprint(f"✅ Transcript saved to: '{final_transcript}'")

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

if __name__ == "__main__":
    main()

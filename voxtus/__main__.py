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
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL


def download_audio(input_path: str, output_path: Path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'enable_file_urls': True
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([input_path])

def transcribe_audio(audio_file: Path, output_file: Path, verbose: bool):
    print("⏳ Loading transcription model (this may take a few seconds the first time)...")
    model = WhisperModel("base", compute_type="auto")
    segments, _ = model.transcribe(str(audio_file))

    with output_file.open("w", encoding="utf-8") as f:
        for segment in segments:
            line = f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"
            f.write(line + "\n")
            if verbose:
                print(line)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("❌ ffmpeg is required but not found. Please install ffmpeg:")
        print("  - macOS: brew install ffmpeg")
        print("  - Ubuntu/Debian: sudo apt install ffmpeg")
        print("  - Windows: Download from https://ffmpeg.org/download.html")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Transcribe Internet videos and media files to text using faster-whisper.")
    parser.add_argument("input", help="Internet URL or local media file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print transcript to stdout")
    parser.add_argument("-k", "--keep", action="store_true", help="Keep the audio file")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite any existing transcript file without confirmation")
    parser.add_argument("-n", "--name", help="Base name for audio and transcript file (no extension)")
    parser.add_argument("-o", "--output", help="Directory to save output files to (default: current directory)")

    args = parser.parse_args()
    check_ffmpeg()  # Check for ffmpeg before proceeding
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

    try:
        # Determine the final transcript path early
        if is_url:
            base = custom_name or "%(title)s"
        else:
            source_file = Path(input_arg).expanduser().resolve()
            if not source_file.exists():
                print(f"❌ Local file not found: {source_file}")
                sys.exit(1)
            base = custom_name or source_file.stem

        final_transcript = output_dir / f"{base}.txt"

        if final_transcript.exists() and not force_overwrite:
            response = input(f"⚠️ Transcript file {final_transcript} already exists. Overwrite? [y/N] ").lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        elif final_transcript.exists() and force_overwrite:
            print(f"⚠️ Option --force used. Overwriting existing {final_transcript} without confirmation.")

        if is_url:
            print(f"🎧 Downloading media from: {input_arg}")
            output_template = workdir / f"{base}.%(ext)s"
            download_audio(input_arg, output_template)
        else:
            source_file = Path(input_arg).expanduser().resolve()
            if not source_file.exists():
                print(f"❌ Local file not found: {source_file}")
                sys.exit(1)
            
            print(f"🎧 Converting media file: {source_file}")
            output_template = workdir / f"{base}.%(ext)s"
            file_url = f"file://{source_file}"
            try:
                download_audio(file_url, output_template)
            except Exception as e:
                print(f"❌ Error processing media file: {e}")
                print("The file format may not be supported. Please ensure it's a valid media file.")
                sys.exit(1)

        # Look for the specific mp3 file we created
        audio_file = workdir / f"{base}.mp3"
        if not audio_file.exists():
            print("❌ No audio file found after processing.")
            sys.exit(1)

        transcript_file = audio_file.with_suffix(".txt")
        print(f"📝 Transcribing to {transcript_file.name}...")

        transcribe_audio(audio_file, transcript_file, args.verbose)

        # Move result to output directory
        shutil.move(str(transcript_file), final_transcript)

        if args.keep:
            final_audio = output_dir / audio_file.name
            shutil.move(str(audio_file), final_audio)
            print(f"📁 Audio file kept: {final_audio}")
        else:
            print(f"🗑️ Audio file discarded")

        print(f"✅ Transcript saved to: {final_transcript}")

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

if __name__ == "__main__":
    main()

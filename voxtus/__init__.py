"""
Voxtus: Transcribe Internet videos and media files to text using faster-whisper.

This package provides a command-line tool for transcribing audio and video content
from the internet or local files using OpenAI's Whisper model via faster-whisper.

Package Structure:
    voxtus.formats: Modular format system for different output types
        - txt: Plain text format with timestamps (default)
        - json: Structured format with rich metadata
        - (Future formats: srt, vtt, csv)
    
    voxtus.__main__: Main CLI application and orchestration logic

Key Features:
    - Multiple output formats with extensible format system
    - Internet video downloading via yt-dlp
    - Local media file processing
    - Rich metadata extraction and inclusion
    - Pipeline-friendly stdout mode
    - Batch format processing

Usage:
    From command line:
        voxtus video.mp4 -f txt,json
    
    As module:
        python -m voxtus video.mp4 -f json --stdout

Author: Johan Thorén
License: AGPL-3.0-or-later
"""

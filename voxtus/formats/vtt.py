"""
VTT format writer for WebVTT subtitle output with metadata support.

This format creates standard WebVTT subtitle files compatible with web browsers
and HTML5 video players. WebVTT is the modern web standard for video subtitles,
supporting enhanced styling and positioning features. This implementation includes
metadata as NOTE blocks following the WebVTT specification.
"""

from pathlib import Path
from typing import Any, Callable, List

from . import FormatWriter, register_format


def format_timestamp(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = round((seconds % 1) * 1000)
    # Handle case where rounding takes us to 1000ms
    if milliseconds >= 1000:
        milliseconds = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def format_vtt_segment(segment) -> str:
    """Format a transcript segment as a WebVTT subtitle block."""
    start_time = format_timestamp(segment.start)
    end_time = format_timestamp(segment.end)
    return f"{start_time} --> {end_time}\n{segment.text.strip()}\n"


def format_metadata_notes(title: str, source: str, info: Any) -> str:
    """Format metadata as WebVTT NOTE blocks."""
    notes = []
    
    # Always add title note
    title_value = title if title and title != "unknown" else "unknown"
    notes.append(f"NOTE Title\n{title_value}\n")
    
    # Always add source note
    source_value = source if source and source != "unknown" else "unknown"
    notes.append(f"NOTE Source\n{source_value}\n")
    
    # Always add duration note
    if hasattr(info, 'duration') and info.duration:
        duration_formatted = format_timestamp(info.duration)
        notes.append(f"NOTE Duration\n{duration_formatted}\n")
    else:
        notes.append(f"NOTE Duration\nunknown\n")
    
    # Always add language note
    language = info.language if hasattr(info, 'language') else "unknown"
    notes.append(f"NOTE Language\n{language}\n")
    
    # Always add model note
    notes.append(f"NOTE Model\nbase\n")
    
    return "\n".join(notes)


class VttFormatWriter(FormatWriter):
    """Writer for WebVTT subtitle format output with metadata support."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
        """Write transcript in WebVTT format with metadata."""
        with output_file.open("w", encoding="utf-8") as f:
            # WebVTT files must start with the header
            f.write("WEBVTT\n\n")
            
            # Add metadata as NOTE blocks
            metadata_notes = format_metadata_notes(title, source, info)
            if metadata_notes:
                f.write(metadata_notes + "\n\n")
            
            for i, segment in enumerate(segments, 1):
                vtt_block = format_vtt_segment(segment)
                f.write(vtt_block + "\n")
                if verbose:
                    vprint_func(f"VTT segment {i}: {segment.start:.2f}s - {segment.end:.2f}s", 2)
        
        if verbose:
            vprint_func(f"VTT format written with {len(segments)} subtitle segments and metadata", 1)
    
    def write_to_stdout(self, segments: List[Any], title: str, source: str, info: Any) -> None:
        """Write transcript to stdout in WebVTT format with metadata."""
        # WebVTT files must start with the header
        print("WEBVTT\n")
        
        # Add metadata as NOTE blocks
        metadata_notes = format_metadata_notes(title, source, info)
        if metadata_notes:
            print(metadata_notes + "\n")
        
        for i, segment in enumerate(segments, 1):
            vtt_block = format_vtt_segment(segment)
            print(vtt_block)


# Register the format
register_format("vtt", VttFormatWriter()) 
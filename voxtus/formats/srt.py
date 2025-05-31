"""
SRT format writer for SubRip subtitle output.

This format creates standard SRT subtitle files compatible with video players
and subtitle editing software. Each segment becomes a subtitle with sequential
numbering and proper HH:MM:SS,mmm timestamp formatting.
"""

from pathlib import Path
from typing import Any, Callable, List

from . import FormatWriter, register_format


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = round((seconds % 1) * 1000)
    # Handle case where rounding takes us to 1000ms
    if milliseconds >= 1000:
        milliseconds = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_srt_segment(segment, segment_number: int) -> str:
    """Format a transcript segment as an SRT subtitle block."""
    start_time = format_timestamp(segment.start)
    end_time = format_timestamp(segment.end)
    return f"{segment_number}\n{start_time} --> {end_time}\n{segment.text.strip()}\n"


class SrtFormatWriter(FormatWriter):
    """Writer for SRT subtitle format output."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
        """Write transcript in SRT format."""
        with output_file.open("w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                srt_block = format_srt_segment(segment, i)
                f.write(srt_block + "\n")
                if verbose:
                    vprint_func(f"SRT segment {i}: {segment.start:.2f}s - {segment.end:.2f}s", 2)
        
        if verbose:
            vprint_func(f"SRT format written with {len(segments)} subtitle segments", 1)
    
    def write_to_stdout(self, segments: List[Any], title: str, source: str, info: Any) -> None:
        """Write transcript to stdout in SRT format."""
        for i, segment in enumerate(segments, 1):
            srt_block = format_srt_segment(segment, i)
            print(srt_block)


# Register the format
register_format("srt", SrtFormatWriter()) 
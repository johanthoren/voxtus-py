"""
TXT format writer for plain text output with timestamps.

This format is the default output format, designed to be LLM-friendly
with clear timestamp markers for each segment.
"""

from pathlib import Path
from typing import Any, Callable, List

from . import FormatWriter, register_format


def format_transcript_line(segment) -> str:
    """Format a transcript segment into a line."""
    return f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"


class TxtFormatWriter(FormatWriter):
    """Writer for TXT format output."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
        """Write transcript in TXT format."""
        with output_file.open("w", encoding="utf-8") as f:
            for segment in segments:
                line = format_transcript_line(segment)
                f.write(line + "\n")
                if verbose:
                    vprint_func(line, 1)
    
    def write_to_stdout(self, segments: List[Any], info: Any) -> None:
        """Write transcript to stdout in TXT format."""
        for segment in segments:
            line = format_transcript_line(segment)
            print(line)


# Register the format
register_format("txt", TxtFormatWriter()) 
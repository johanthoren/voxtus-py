"""
TXT format writer for plain text output with timestamps.

This format is the default output format, designed to be LLM-friendly
with clear timestamp markers for each segment.
"""

import sys
from pathlib import Path
from typing import Any, Callable, List

from . import FormatWriter, register_format


def format_transcript_line(segment) -> str:
    """Format a transcript segment into a line."""
    return f"[{segment.start:.2f} - {segment.end:.2f}]: {segment.text}"


class TxtFormatWriter(FormatWriter):
    """Writer for TXT format output."""
    
    def _format_complete_output(self, segments: List[Any]) -> str:
        """Format complete TXT output as a string."""
        lines = []
        for segment in segments:
            line = format_transcript_line(segment)
            lines.append(line)
        return "\n".join(lines)
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None], model: str = "base") -> None:
        """Write transcript in TXT format."""
        content = self._format_complete_output(segments)
        
        with output_file.open("w", encoding="utf-8") as f:
            f.write(content + "\n")
            
        if verbose:
            for line in content.split("\n"):
                vprint_func(line, 1)
    
    def write_to_stdout(self, segments: List[Any], title: str, source: str, info: Any, model: str = "base") -> None:
        """Write transcript to stdout in TXT format."""
        content = self._format_complete_output(segments)
        sys.stdout.write(content + "\n")


# Register the format
register_format("txt", TxtFormatWriter()) 
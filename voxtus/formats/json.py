"""
JSON format writer for structured output with metadata.

This format provides rich metadata alongside the transcript data,
including title, source, duration, model, and language information.
Each segment includes sequential IDs for easy reference.
"""

import json
from pathlib import Path
from typing import Any, Callable, List

from . import FormatWriter, register_format


class JsonFormatWriter(FormatWriter):
    """Writer for JSON format output."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
        """Write transcript in JSON format with metadata."""
        transcript_data = {
            "transcript": [
                {
                    "id": i + 1,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                for i, segment in enumerate(segments)
            ],
            "metadata": {
                "title": title,
                "source": source,
                "duration": info.duration if hasattr(info, 'duration') else None,
                "model": "base",
                "language": info.language if hasattr(info, 'language') else "en"
            }
        }
        
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        
        if verbose:
            vprint_func(f"JSON format written with {len(transcript_data['transcript'])} segments", 1)
    
    def write_to_stdout(self, segments: List[Any], info: Any) -> None:
        """Write transcript to stdout in JSON format."""
        transcript_data = {
            "transcript": [
                {
                    "id": i + 1,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                for i, segment in enumerate(segments)
            ],
            "metadata": {
                "title": "unknown",
                "source": "unknown", 
                "duration": info.duration if hasattr(info, 'duration') else None,
                "model": "base",
                "language": info.language if hasattr(info, 'language') else "en"
            }
        }
        print(json.dumps(transcript_data, indent=2, ensure_ascii=False))


# Register the format
register_format("json", JsonFormatWriter()) 
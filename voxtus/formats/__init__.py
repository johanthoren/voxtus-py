"""
Format implementations for transcription output.

This package contains individual format implementations that can be used
to output transcriptions in various formats.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List


class FormatWriter:
    """Base class for format writers."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
        """Write segments to the specified format."""
        raise NotImplementedError("Format writers must implement write()")
    
    def write_to_stdout(self, segments: List[Any], info: Any) -> None:
        """Write segments to stdout in the specified format."""
        raise NotImplementedError("Format writers must implement write_to_stdout()")


# Format registry - will be populated by individual format modules
_format_registry: Dict[str, FormatWriter] = {}


def register_format(name: str, writer: FormatWriter) -> None:
    """Register a format writer."""
    _format_registry[name] = writer


def get_format_writer(name: str) -> FormatWriter:
    """Get a format writer by name."""
    if name not in _format_registry:
        raise ValueError(f"Unknown format: {name}")
    return _format_registry[name]


def get_supported_formats() -> List[str]:
    """Get list of supported format names."""
    return list(_format_registry.keys())


def write_format(format_name: str, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None]) -> None:
    """Write segments using the specified format."""
    writer = get_format_writer(format_name)
    writer.write(segments, output_file, title, source, info, verbose, vprint_func)


def write_format_to_stdout(format_name: str, segments: List[Any], info: Any) -> None:
    """Write segments to stdout using the specified format."""
    writer = get_format_writer(format_name)
    writer.write_to_stdout(segments, info)


# Auto-import format modules to register them
from . import json, txt

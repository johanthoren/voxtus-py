"""
Format implementations for transcription output.

This package contains individual format implementations that can be used
to output transcriptions in various formats. The package uses a registry
pattern to allow dynamic format discovery and extensible architecture.

Architecture:
    - FormatWriter: Base class that all format writers must inherit from
    - Registry system: Automatic discovery of available formats
    - Individual modules: Each format (txt, json, etc.) in its own file
    - Auto-registration: Formats register themselves on import

Adding New Formats:
    1. Create a new file in this package (e.g., foo.py)
    2. Inherit from FormatWriter and implement required methods
    3. Call register_format() at module level
    4. Import the module in this __init__.py file

Example:
    # In voxtus/formats/foo.py
    class FooFormatWriter(FormatWriter):
        def write(self, segments, output_file, title, source, info, verbose, vprint_func):
            # Implementation here
            pass
        
        def write_to_stdout(self, segments, info):
            # Implementation here  
            pass
    
    register_format("foo", FooFormatWriter())

The format will then be automatically available via:
    - get_supported_formats()
    - write_format("foo", ...)
    - CLI: voxtus video.mp4 -f foo
"""

from pathlib import Path
from typing import Any, Callable, Dict, List


class FormatWriter:
    """Base class for format writers."""
    
    def write(self, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None], model: str = "base") -> None:
        """Write segments to the specified format."""
        raise NotImplementedError("Format writers must implement write()")
    
    def write_to_stdout(self, segments: List[Any], title: str, source: str, info: Any, model: str = "base") -> None:
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


def write_format(format_name: str, segments: List[Any], output_file: Path, title: str, source: str, info: Any, verbose: bool, vprint_func: Callable[[str, int], None], model: str = "base") -> None:
    """Write segments using the specified format."""
    writer = get_format_writer(format_name)
    writer.write(segments, output_file, title, source, info, verbose, vprint_func, model)


def write_format_to_stdout(format_name: str, segments: List[Any], title: str, source: str, info: Any, model: str = "base") -> None:
    """Write segments to stdout using the specified format."""
    writer = get_format_writer(format_name)
    writer.write_to_stdout(segments, title, source, info, model)


# Auto-import format modules to register them
from . import json, srt, txt, vtt

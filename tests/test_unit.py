"""
Unit tests for pure functions in voxtus.

These tests focus on functions that don't have side effects and can be tested
in isolation without requiring external dependencies or file system operations.
"""
import argparse
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from returns.pipeline import is_successful
from returns.result import Failure, Success

from voxtus.__main__ import (Config, ProcessingContext, create_config,
                             create_output_template, create_print_wrapper,
                             create_processing_context, create_ydl_options,
                             get_final_name, parse_arguments)
from voxtus.formats.txt import format_transcript_line


class TestFormatTranscriptLine:
    """Test the format_transcript_line function."""
    
    def test_format_basic_segment(self):
        """Test formatting a basic transcript segment."""
        segment = Mock()
        segment.start = 0.0
        segment.end = 5.5
        segment.text = "Hello world"
        
        result = format_transcript_line(segment)
        assert result == "[0.00 - 5.50]: Hello world"
    
    def test_format_with_decimal_precision(self):
        """Test formatting preserves 2 decimal places."""
        segment = Mock()
        segment.start = 1.234
        segment.end = 7.89
        segment.text = "Test message"
        
        result = format_transcript_line(segment)
        assert result == "[1.23 - 7.89]: Test message"
    
    def test_format_with_special_characters(self):
        """Test formatting with special characters in text."""
        segment = Mock()
        segment.start = 10.0
        segment.end = 15.0
        segment.text = "Hello, world! How are you? 🎉"
        
        result = format_transcript_line(segment)
        assert result == "[10.00 - 15.00]: Hello, world! How are you? 🎉"


class TestGetFinalName:
    """Test the get_final_name function."""
    
    def test_uses_custom_name_when_provided(self):
        """Test that custom name takes precedence."""
        result = get_final_name("original_title", "custom_name")
        assert result == "custom_name"
    
    def test_uses_title_when_no_custom_name(self):
        """Test that title is used when no custom name provided."""
        result = get_final_name("original_title", None)
        assert result == "original_title"
    
    def test_empty_custom_name_uses_title(self):
        """Test that empty custom name falls back to title."""
        result = get_final_name("original_title", "")
        assert result == "original_title"


class TestCreateOutputTemplate:
    """Test the create_output_template function."""
    
    def test_creates_correct_template_path(self):
        """Test that output template is created correctly."""
        workdir = Path("/tmp/test")
        token = "abc123"
        
        result = create_output_template(workdir, token)
        expected = workdir / "abc123.%(ext)s"
        assert result == expected
    
    def test_with_different_workdir(self):
        """Test with different working directory."""
        workdir = Path("/home/user/downloads")
        token = "xyz789"
        
        result = create_output_template(workdir, token)
        expected = workdir / "xyz789.%(ext)s"
        assert result == expected


class TestCreateYdlOptions:
    """Test the create_ydl_options function."""
    
    def test_basic_options_structure(self):
        """Test that basic options are always present."""
        result = create_ydl_options(False, False, Path("/tmp/output"))
        
        assert result['format'] == 'bestaudio/best'
        assert result['outtmpl'] == '/tmp/output'
        assert result['enable_file_urls'] is True
        assert len(result['postprocessors']) == 1
        assert result['postprocessors'][0]['key'] == 'FFmpegExtractAudio'
        assert result['postprocessors'][0]['preferredcodec'] == 'mp3'
        assert result['postprocessors'][0]['preferredquality'] == '192'
    
    def test_stdout_mode_options(self):
        """Test options when stdout mode is enabled."""
        result = create_ydl_options(False, True, Path("/tmp/output"))
        
        assert result['quiet'] is True
        assert result['no_warnings'] is True
        assert result['verbose'] is False
        assert result['noprogress'] is True
    
    def test_debug_mode_options(self):
        """Test options when debug mode is enabled."""
        result = create_ydl_options(True, False, Path("/tmp/output"))
        
        assert result['quiet'] is False
        assert result['no_warnings'] is False
        assert result['verbose'] is True
    
    def test_normal_mode_options(self):
        """Test options in normal mode (no debug, no stdout)."""
        result = create_ydl_options(False, False, Path("/tmp/output"))
        
        assert result['quiet'] is True
        assert result['no_warnings'] is True
        assert result['verbose'] is False
    
    def test_stdout_overrides_debug(self):
        """Test that stdout mode overrides debug settings."""
        result = create_ydl_options(True, True, Path("/tmp/output"))
        
        # Stdout mode should override debug settings
        assert result['quiet'] is True
        assert result['no_warnings'] is True
        assert result['verbose'] is False
        assert result['noprogress'] is True


class TestCreatePrintWrapper:
    """Test the create_print_wrapper function."""
    
    def test_verbose_level_0_always_prints(self, capsys):
        """Test that level 0 messages always print when not in stdout mode."""
        vprint = create_print_wrapper(verbose_level=0, stdout_mode=False)
        vprint("Test message", 0)
        
        captured = capsys.readouterr()
        assert "Test message" in captured.err
    
    def test_verbose_level_1_requires_v_flag(self, capsys):
        """Test that level 1 messages require -v flag."""
        # Without -v flag (verbose_level=0)
        vprint = create_print_wrapper(verbose_level=0, stdout_mode=False)
        vprint("Level 1 message", 1)
        
        captured = capsys.readouterr()
        assert captured.err == ""
        
        # With -v flag (verbose_level=1)
        vprint = create_print_wrapper(verbose_level=1, stdout_mode=False)
        vprint("Level 1 message", 1)
        
        captured = capsys.readouterr()
        assert "Level 1 message" in captured.err
    
    def test_verbose_level_2_requires_vv_flag(self, capsys):
        """Test that level 2 messages require -vv flag."""
        # With -v flag (verbose_level=1)
        vprint = create_print_wrapper(verbose_level=1, stdout_mode=False)
        vprint("Level 2 message", 2)
        
        captured = capsys.readouterr()
        assert captured.err == ""
        
        # With -vv flag (verbose_level=2)
        vprint = create_print_wrapper(verbose_level=2, stdout_mode=False)
        vprint("Level 2 message", 2)
        
        captured = capsys.readouterr()
        assert "Level 2 message" in captured.err
    
    def test_stdout_mode_suppresses_all_output(self, capsys):
        """Test that stdout mode suppresses all output regardless of verbosity."""
        vprint = create_print_wrapper(verbose_level=2, stdout_mode=True)
        vprint("Should not print", 0)
        vprint("Should not print", 1)
        vprint("Should not print", 2)
        
        captured = capsys.readouterr()
        assert captured.err == ""
    
    def test_default_level_is_zero(self, capsys):
        """Test that default message level is 0."""
        vprint = create_print_wrapper(verbose_level=0, stdout_mode=False)
        vprint("Default level message")  # No level specified
        
        captured = capsys.readouterr()
        assert "Default level message" in captured.err


class TestCreateConfig:
    """Test the create_config function."""
    
    def test_basic_config_creation(self, tmp_path):
        """Test creating config with basic arguments."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=1,
            keep=False,
            overwrite=False,
            format="txt",
            name=None,
            output=str(tmp_path),
            stdout=False
        )
        
        config = create_config(args)
        
        assert config.input_path == "test.mp3"
        assert config.verbose_level == 1
        assert config.keep_audio is False
        assert config.overwrite_files is False
        assert config.custom_name is None
        assert config.output_dir == tmp_path
        assert config.stdout_mode is False
        assert config.formats == ["txt"]
    
    def test_config_with_custom_name(self, tmp_path):
        """Test config creation with custom name."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=True,
            overwrite=True,
            format="json",
            name="my_custom_name",
            output=str(tmp_path),
            stdout=True
        )
        
        config = create_config(args)
        
        assert config.custom_name == "my_custom_name"
        assert config.keep_audio is True
        assert config.overwrite_files is True
        assert config.stdout_mode is True
        assert config.formats == ["json"]
    
    def test_config_strips_txt_extension_from_name(self, tmp_path):
        """Test that .txt extension is stripped from custom name."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=False,
            overwrite=False,
            format="txt",
            name="my_file.txt",
            output=str(tmp_path),
            stdout=False
        )
        
        config = create_config(args)
        assert config.custom_name == "my_file"
    
    def test_config_uses_current_dir_when_no_output(self):
        """Test that current directory is used when no output specified."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=False,
            overwrite=False,
            format="txt",
            name=None,
            output=None,
            stdout=False
        )
        
        config = create_config(args)
        assert config.output_dir == Path.cwd()
    
    def test_config_expands_user_path(self, tmp_path):
        """Test that user path (~) is expanded."""
        # Create a mock path that looks like a user path
        user_path = "~/test_output"
        
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=False,
            overwrite=False,
            format="txt",
            name=None,
            output=user_path,
            stdout=False
        )
        
        config = create_config(args)
        # The path should be expanded and resolved
        assert str(config.output_dir) != user_path
        assert config.output_dir.is_absolute()


class TestCreateProcessingContext:
    """Test the create_processing_context function."""
    
    def test_context_creation_with_url(self, tmp_path):
        """Test creating context for URL input."""
        config = Config(
            input_path="https://example.com/video.mp4",
            verbose_level=1,
            keep_audio=False,
            overwrite_files=False,
            custom_name=None,
            output_dir=tmp_path,
            stdout_mode=False,
            formats=["txt"]
        )
        
        ctx = create_processing_context(config)
        
        assert ctx.config == config
        assert ctx.is_url is True
        assert ctx.workdir.exists()
        assert ctx.workdir.is_dir()
        assert isinstance(ctx.token, str)
        assert len(ctx.token) > 0
        assert callable(ctx.vprint)
    
    def test_context_creation_with_file(self, tmp_path):
        """Test creating context for file input."""
        config = Config(
            input_path="/path/to/file.mp3",
            verbose_level=2,
            keep_audio=True,
            overwrite_files=True,
            custom_name="test",
            output_dir=tmp_path,
            stdout_mode=True,
            formats=["json"]
        )
        
        ctx = create_processing_context(config)
        
        assert ctx.config == config
        assert ctx.is_url is False
        assert ctx.workdir.exists()
        assert ctx.workdir.is_dir()
        assert isinstance(ctx.token, str)
        assert len(ctx.token) > 0
        assert callable(ctx.vprint)
    
    def test_context_creates_unique_tokens(self, tmp_path):
        """Test that each context gets a unique token."""
        config = Config(
            input_path="test.mp3",
            verbose_level=0,
            keep_audio=False,
            overwrite_files=False,
            custom_name=None,
            output_dir=tmp_path,
            stdout_mode=False,
            formats=["txt"]
        )
        
        ctx1 = create_processing_context(config)
        ctx2 = create_processing_context(config)
        
        assert ctx1.token != ctx2.token
    
    def test_context_creates_unique_workdirs(self, tmp_path):
        """Test that each context gets a unique working directory."""
        config = Config(
            input_path="test.mp3",
            verbose_level=0,
            keep_audio=False,
            overwrite_files=False,
            custom_name=None,
            output_dir=tmp_path,
            stdout_mode=False,
            formats=["txt"]
        )
        
        ctx1 = create_processing_context(config)
        ctx2 = create_processing_context(config)
        
        assert ctx1.workdir != ctx2.workdir
        assert ctx1.workdir.exists()
        assert ctx2.workdir.exists()


class TestParseArguments:
    """Test the parse_arguments function."""
    
    def test_parse_basic_arguments(self, monkeypatch):
        """Test parsing basic command line arguments."""
        test_args = ["voxtus", "test.mp3"]
        monkeypatch.setattr("sys.argv", test_args)
        
        args = parse_arguments()
        
        assert args.input == "test.mp3"
        assert args.verbose == 0
        assert args.keep is False
        assert args.overwrite is False
        assert args.format == "txt"  # default format
        assert args.name is None
        assert args.output is None
        assert args.stdout is False
    
    def test_parse_all_flags(self, monkeypatch):
        """Test parsing all available flags."""
        test_args = [
            "voxtus", "test.mp3",
            "-v", "-v",  # -vv for debug
            "--keep",
            "--overwrite", 
            "--format", "json",
            "--name", "custom_name",
            "--output", "/tmp/output",
            "--stdout"
        ]
        monkeypatch.setattr("sys.argv", test_args)
        
        args = parse_arguments()
        
        assert args.input == "test.mp3"
        assert args.verbose == 2  # -vv
        assert args.keep is True
        assert args.overwrite is True
        assert args.format == "json"
        assert args.name == "custom_name"
        assert args.output == "/tmp/output"
        assert args.stdout is True
    
    def test_parse_short_flags(self, monkeypatch):
        """Test parsing short flag versions."""
        test_args = [
            "voxtus", "test.mp3",
            "-v",
            "-k",
            "-f", "txt,json",
            "-n", "short_name",
            "-o", "/tmp/short"
        ]
        monkeypatch.setattr("sys.argv", test_args)
        
        args = parse_arguments()
        
        assert args.input == "test.mp3"
        assert args.verbose == 1
        assert args.keep is True
        assert args.format == "txt,json"
        assert args.name == "short_name"
        assert args.output == "/tmp/short"


class TestTranscriptionProgress:
    """Test transcription progress indicator behavior."""
    
    def test_progress_shown_in_normal_mode(self, tmp_path, capsys, monkeypatch):
        """Test that progress is shown in normal (non-verbose) mode."""
        from unittest.mock import Mock, patch

        from voxtus.__main__ import create_print_wrapper, transcribe_to_formats

        # Mock WhisperModel and segments
        mock_segment = Mock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = "Test transcription"
        
        mock_info = Mock()
        mock_info.duration = 10.0
        
        mock_model = Mock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        
        # Mock the WhisperModel constructor
        with patch('voxtus.__main__.WhisperModel', return_value=mock_model):
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()  # Create empty file
            base_output = tmp_path / "output"
            
            vprint = create_print_wrapper(verbose_level=0, stdout_mode=False)
            transcribe_to_formats(audio_file, base_output, ["txt"], "test", "test.mp3", verbose=False, vprint_func=vprint)
        
        captured = capsys.readouterr()
        # Progress should be shown to stderr
        assert "📝 Transcribing... 100.0%" in captured.err
        assert "(10.0s / 10.0s)" in captured.err
    
    def test_progress_suppressed_in_verbose_mode(self, tmp_path, capsys, monkeypatch):
        """Test that progress is suppressed in verbose mode to avoid interference."""
        from unittest.mock import Mock, patch

        from voxtus.__main__ import create_print_wrapper, transcribe_to_formats

        # Mock WhisperModel and segments
        mock_segment = Mock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = "Test transcription"
        
        mock_info = Mock()
        mock_info.duration = 10.0
        
        mock_model = Mock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        
        # Mock the WhisperModel constructor
        with patch('voxtus.__main__.WhisperModel', return_value=mock_model):
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()  # Create empty file
            base_output = tmp_path / "output"
            
            vprint = create_print_wrapper(verbose_level=1, stdout_mode=False)
            transcribe_to_formats(audio_file, base_output, ["txt"], "test", "test.mp3", verbose=True, vprint_func=vprint)
        
        captured = capsys.readouterr()
        # Progress should NOT be shown in verbose mode
        assert "📝 Transcribing..." not in captured.err or "%" not in captured.err
        # But transcript line should be shown
        assert "Test transcription" in captured.err
    
    def test_progress_with_multiple_segments(self, tmp_path, capsys):
        """Test progress updates with multiple segments."""
        from unittest.mock import Mock, patch

        from voxtus.__main__ import create_print_wrapper, transcribe_to_formats

        # Mock multiple segments
        segments = []
        for i, end_time in enumerate([2.0, 4.0, 6.0, 8.0, 10.0]):
            segment = Mock()
            segment.start = i * 2.0
            segment.end = end_time
            segment.text = f"Segment {i+1}"
            segments.append(segment)
        
        mock_info = Mock()
        mock_info.duration = 10.0
        
        mock_model = Mock()
        mock_model.transcribe.return_value = (segments, mock_info)
        
        # Mock the WhisperModel constructor
        with patch('voxtus.__main__.WhisperModel', return_value=mock_model):
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()
            base_output = tmp_path / "output"
            
            vprint = create_print_wrapper(verbose_level=0, stdout_mode=False)
            transcribe_to_formats(audio_file, base_output, ["txt"], "test", "test.mp3", verbose=False, vprint_func=vprint)
        
        captured = capsys.readouterr()
        # Should show final 100% completion
        assert "📝 Transcribing... 100.0% (10.0s / 10.0s)" in captured.err
    
    def test_stdout_mode_remains_quiet(self, tmp_path, capsys):
        """Test that stdout mode produces no progress messages."""
        from unittest.mock import Mock, patch

        from voxtus.__main__ import transcribe_to_stdout

        # Mock WhisperModel and segments
        mock_segment = Mock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = "Test transcription"
        
        mock_info = Mock()
        mock_info.duration = 10.0
        
        mock_model = Mock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        
        # Mock the WhisperModel constructor
        with patch('voxtus.__main__.WhisperModel', return_value=mock_model):
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()
            
            transcribe_to_stdout(audio_file, "txt")
        
        captured = capsys.readouterr()
        # Stdout should only contain transcript
        assert captured.out.strip() == "[0.00 - 5.00]: Test transcription"
        # Stderr should be empty (no progress messages)
        assert captured.err == ""


class TestFormatSelection:
    """Test format selection and validation functionality."""
    
    def test_parse_single_format(self):
        """Test parsing a single format."""
        from voxtus.__main__ import parse_and_validate_formats
        
        formats = parse_and_validate_formats("txt", stdout_mode=False)
        assert formats == ["txt"]
    
    def test_parse_multiple_formats(self):
        """Test parsing multiple comma-separated formats."""
        from voxtus.__main__ import parse_and_validate_formats
        
        formats = parse_and_validate_formats("txt,json", stdout_mode=False)
        assert formats == ["txt", "json"]
    
    def test_parse_formats_with_spaces(self):
        """Test parsing formats with spaces around commas."""
        from voxtus.__main__ import parse_and_validate_formats
        
        formats = parse_and_validate_formats("txt, json", stdout_mode=False)
        assert formats == ["txt", "json"]
    
    def test_parse_formats_case_insensitive(self):
        """Test that format parsing is case insensitive."""
        from voxtus.__main__ import parse_and_validate_formats
        
        formats = parse_and_validate_formats("TXT,JSON", stdout_mode=False)
        assert formats == ["txt", "json"]
    
    def test_invalid_format_raises_exit(self, capsys):
        """Test that invalid formats cause system exit."""
        import pytest

        from voxtus.__main__ import parse_and_validate_formats
        
        with pytest.raises(SystemExit):
            parse_and_validate_formats("invalid", stdout_mode=False)
        
        captured = capsys.readouterr()
        assert "Invalid format(s): invalid" in captured.err
        assert "Supported formats:" in captured.err
    
    def test_multiple_formats_with_stdout_raises_exit(self, capsys):
        """Test that multiple formats with stdout mode cause system exit."""
        import pytest

        from voxtus.__main__ import parse_and_validate_formats
        
        with pytest.raises(SystemExit):
            parse_and_validate_formats("txt,json", stdout_mode=True)
        
        captured = capsys.readouterr()
        assert "Only one format allowed when using --stdout" in captured.err
    
    def test_single_format_with_stdout_allowed(self):
        """Test that single format with stdout mode is allowed."""
        from voxtus.__main__ import parse_and_validate_formats
        
        formats = parse_and_validate_formats("json", stdout_mode=True)
        assert formats == ["json"]


class TestJSONFormat:
    """Test JSON format functionality."""
    
    def test_json_format_structure(self, tmp_path):
        """Test JSON format output structure."""
        import json
        from unittest.mock import Mock

        from voxtus.formats import write_format

        # Mock segments
        segments = []
        for i in range(3):
            segment = Mock()
            segment.start = i * 2.0
            segment.end = (i + 1) * 2.0
            segment.text = f"Segment {i + 1} text"
            segments.append(segment)
        
        # Mock info
        mock_info = Mock()
        mock_info.duration = 6.0
        mock_info.language = "en"
        
        output_file = tmp_path / "test.json"
        vprint = lambda msg, level=0: None
        
        write_format("json", segments, output_file, "Test Title", "test.mp3", mock_info, False, vprint)
        
        # Read and parse the JSON
        with open(output_file) as f:
            data = json.load(f)
        
        # Verify structure
        assert "transcript" in data
        assert "metadata" in data
        
        # Verify transcript
        assert len(data["transcript"]) == 3
        for i, segment in enumerate(data["transcript"]):
            assert segment["id"] == i + 1
            assert segment["start"] == i * 2.0
            assert segment["end"] == (i + 1) * 2.0
            assert segment["text"] == f"Segment {i + 1} text"
        
        # Verify metadata
        metadata = data["metadata"]
        assert metadata["title"] == "Test Title"
        assert metadata["source"] == "test.mp3"
        assert metadata["duration"] == 6.0
        assert metadata["model"] == "base"
        assert metadata["language"] == "en"
    
    def test_txt_format_structure(self, tmp_path):
        """Test TXT format output structure."""
        from unittest.mock import Mock

        from voxtus.formats import write_format

        # Mock segments
        segments = []
        for i in range(2):
            segment = Mock()
            segment.start = i * 3.0
            segment.end = (i + 1) * 3.0
            segment.text = f"Text segment {i + 1}"
            segments.append(segment)
        
        output_file = tmp_path / "test.txt"
        vprint = lambda msg, level=0: None
        
        write_format("txt", segments, output_file, "Test Title", "test.mp3", None, False, vprint)
        
        # Read the file
        with open(output_file) as f:
            content = f.read()
        
        # Verify content
        lines = content.strip().split('\n')
        assert len(lines) == 2
        assert lines[0] == "[0.00 - 3.00]: Text segment 1"
        assert lines[1] == "[3.00 - 6.00]: Text segment 2"


class TestFormatArguments:
    """Test format argument integration."""
    
    def test_format_argument_in_config(self, tmp_path):
        """Test that format argument is properly parsed into config."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=False,
            overwrite=False,
            format="txt,json",
            name=None,
            output=str(tmp_path),
            stdout=False
        )
        
        from voxtus.__main__ import create_config
        config = create_config(args)
        
        assert config.formats == ["txt", "json"]
    
    def test_default_format_is_txt(self, tmp_path):
        """Test that default format is txt."""
        args = argparse.Namespace(
            input="test.mp3",
            verbose=0,
            keep=False,
            overwrite=False,
            format="txt",  # This is the default from argparse
            name=None,
            output=str(tmp_path),
            stdout=False
        )
        
        from voxtus.__main__ import create_config
        config = create_config(args)
        
        assert config.formats == ["txt"] 
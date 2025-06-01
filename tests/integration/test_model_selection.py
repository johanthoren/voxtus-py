"""
Tests for model selection functionality.

This module tests:
- Model listing with --list-models
- Model validation and error handling  
- Transcription with different models
- Default model behavior
"""
import subprocess
from pathlib import Path

# CI environments may be slower, so use generous timeout
CI_TIMEOUT = 120  # 2 minutes for model loading and transcription


def test_list_models_command():
    """Test that --list-models command works and shows expected content."""
    result = subprocess.run(
        ["voxtus", "--list-models"],
        capture_output=True,
        text=True,
        timeout=30  # This should be fast
    )
    
    assert result.returncode == 0
    output = result.stdout
    
    # Check for key sections
    assert "🎤 Available Whisper Models:" in output
    assert "📂 Tiny Models:" in output
    assert "📂 Base Models:" in output 
    assert "📂 Small Models:" in output
    assert "📂 Medium Models:" in output
    assert "📂 Large Models:" in output
    
    # Check for specific models
    assert "tiny" in output
    assert "base" in output
    assert "small" in output
    assert "medium" in output
    assert "large-v3" in output
    assert "turbo" in output
    
    # Check for usage examples
    assert "💡 Usage examples:" in output
    assert "# Good balance (default)" in output
    
    # Verify stderr is empty (no errors)
    assert result.stderr == ""


def test_invalid_model_error():
    """Test that invalid model names produce helpful error messages."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "--model", "invalid-model", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 1
    assert "❌ Error: Unknown model 'invalid-model'" in result.stderr
    assert "📋 Available models:" in result.stderr
    assert "Use 'voxtus --list-models'" in result.stderr


def test_tiny_model_transcription():
    """Test transcription with tiny model (our standard test model)."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "--model", "tiny", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    # Tiny model produces "VoxDus" transcription
    assert "VoxDus" in result.stdout
    assert "command line tool" in result.stdout


def test_base_model_transcription():
    """Test transcription with base model."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "--model", "base", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    # Base model may produce "Voxdust" instead of "Voxtus"
    assert ("Voxtus" in result.stdout or "Voxdust" in result.stdout)
    assert "command line tool" in result.stdout


def test_model_parameter_file_output(tmp_path):
    """Test that model parameter works with file output mode."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "model_test"
    
    result = subprocess.run(
        ["voxtus", "--model", "tiny", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    
    # Check that file was created
    transcript_file = output_dir / f"{name}.txt"
    assert transcript_file.exists()
    
    # Check content accuracy with tiny model
    with transcript_file.open() as f:
        content = f.read()
        assert "VoxDus" in content
        assert "command line tool" in content


def test_model_with_multiple_formats(tmp_path):
    """Test model parameter with multiple output formats."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "multi_format_test"
    
    result = subprocess.run(
        ["voxtus", "--model", "tiny", "-f", "txt,json", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    
    # Check that both files were created
    txt_file = output_dir / f"{name}.txt"
    json_file = output_dir / f"{name}.json"
    
    assert txt_file.exists()
    assert json_file.exists()
    
    # Both should contain accurate content from tiny model
    with txt_file.open() as f:
        txt_content = f.read()
        assert "VoxDus" in txt_content
    
    # JSON should be valid and contain metadata
    import json
    with json_file.open() as f:
        json_data = json.load(f)
        assert "transcript" in json_data
        assert "metadata" in json_data
        assert json_data["metadata"]["model"] == "tiny"


def test_base_model_golden_file_match():
    """Test that base model produces output matching its golden files."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    # Test base model TXT output
    result = subprocess.run(
        ["voxtus", "--model", "base", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    
    # Load expected base model output
    base_txt_file = Path(__file__).parent.parent / "data" / "expected_output_base.txt"
    with base_txt_file.open() as f:
        expected_txt = f.read().strip()
    
    assert result.stdout.strip() == expected_txt
    assert "Voxdust" in result.stdout  # Base model should produce "Voxdust"


def test_base_model_json_metadata():
    """Test that base model JSON output has correct metadata."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "--model", "base", "-f", "json", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    
    # Parse JSON output
    import json
    data = json.loads(result.stdout)
    
    # Check model metadata is correct
    assert data["metadata"]["model"] == "base"
    assert "Voxdust" in data["transcript"][0]["text"]


def test_tiny_model_golden_files():
    """Test that tiny model produces output matching golden files."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    # Test tiny model (our standard test model)
    result = subprocess.run(
        ["voxtus", "--model", "tiny", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        timeout=CI_TIMEOUT
    )
    
    assert result.returncode == 0
    
    # Load expected tiny model output (our standard golden files)
    expected_txt_file = Path(__file__).parent.parent / "data" / "expected_output.txt"
    with expected_txt_file.open() as f:
        expected_txt = f.read().strip()
    
    assert result.stdout.strip() == expected_txt
    assert "VoxDus" in result.stdout  # Tiny model should produce "VoxDus" 
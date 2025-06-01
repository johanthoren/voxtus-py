import json
import subprocess
from pathlib import Path

from . import EXPECTED_OUTPUT, validate_no_runtime_warnings


def test_json_format_output(tmp_path):
    """Test JSON format output structure and content."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "json_test"

    result = subprocess.run(
        ["voxtus", "-f", "json", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    
    # Check JSON file was created
    json_file = output_dir / f"{name}.json"
    assert json_file.exists()
    
    # Validate that no RuntimeWarnings appear in normal mode
    validate_no_runtime_warnings(result.stderr)
    
    # Validate JSON structure
    with json_file.open() as f:
        data = json.load(f)
    
    # Check required structure
    assert "transcript" in data
    assert "metadata" in data
    
    # Check transcript format
    transcript = data["transcript"]
    assert len(transcript) > 0
    for segment in transcript:
        assert "id" in segment
        assert "start" in segment
        assert "end" in segment
        assert "text" in segment
        assert isinstance(segment["id"], int)
        assert isinstance(segment["start"], (int, float))
        assert isinstance(segment["end"], (int, float))
        assert isinstance(segment["text"], str)
    
    # Check metadata format
    metadata = data["metadata"]
    assert "title" in metadata
    assert "source" in metadata
    assert "duration" in metadata
    assert "model" in metadata
    assert "language" in metadata
    
    # Check expected content is present
    full_text = " ".join([seg["text"] for seg in transcript])
    assert "Voxdust" in full_text or "command line tool" in full_text

def test_srt_format_output(tmp_path):
    """Test SRT format output structure and content."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "srt_test"

    result = subprocess.run(
        ["voxtus", "-f", "srt", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    
    # Check SRT file was created
    srt_file = output_dir / f"{name}.srt"
    assert srt_file.exists()
    
    # Validate that no RuntimeWarnings appear in normal mode
    validate_no_runtime_warnings(result.stderr)
    
    # Validate SRT format
    with srt_file.open(encoding="utf-8") as f:
        content = f.read()
    
    # Check SRT structure
    assert content.strip()  # Not empty
    
    # SRT should have numbered segments
    lines = content.strip().split('\n')
    
    # First line should be segment number "1"
    assert lines[0].strip() == "1"
    
    # Should have timestamp lines with format HH:MM:SS,mmm --> HH:MM:SS,mmm
    timestamp_found = False
    for line in lines:
        if "-->" in line:
            timestamp_found = True
            # Validate timestamp format
            assert "," in line  # SRT uses comma for milliseconds
            parts = line.split(" --> ")
            assert len(parts) == 2
            # Basic format check (should be HH:MM:SS,mmm)
            for part in parts:
                assert ":" in part and "," in part
            break
    
    assert timestamp_found, "No timestamp line found in SRT output"
    
    # Check expected content is present
    assert "Voxdust" in content or "command line tool" in content

def test_vtt_format_output(tmp_path):
    """Test VTT format output structure and content."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "vtt_test"

    result = subprocess.run(
        ["voxtus", "-f", "vtt", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    
    # Check VTT file was created
    vtt_file = output_dir / f"{name}.vtt"
    assert vtt_file.exists()
    
    # Validate VTT format
    with vtt_file.open(encoding="utf-8") as f:
        content = f.read()
    
    # Check VTT structure
    assert content.strip()  # Not empty
    assert content.startswith("WEBVTT\n")  # Must start with WEBVTT header
    
    # Check for metadata NOTE blocks
    assert "NOTE Title" in content
    assert "NOTE Source" in content
    assert "NOTE Duration" in content
    assert "NOTE Language" in content
    assert "NOTE Model" in content
    
    # Should have timestamp lines with format HH:MM:SS.mmm --> HH:MM:SS.mmm
    timestamp_found = False
    lines = content.split('\n')
    for line in lines:
        if "-->" in line and "NOTE" not in line:
            timestamp_found = True
            # Validate timestamp format
            assert "." in line  # VTT uses dot for milliseconds
            parts = line.split(" --> ")
            assert len(parts) == 2
            # Basic format check (should be HH:MM:SS.mmm)
            for part in parts:
                assert ":" in part and "." in part
            break
    
    assert timestamp_found, "No timestamp line found in VTT output"
    
    # Check expected content is present
    assert "Voxdust" in content or "command line tool" in content

def test_multiple_formats_output(tmp_path):
    """Test generating multiple formats in a single run."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "multi_format_test"

    result = subprocess.run(
        ["voxtus", "-f", "txt,json,srt,vtt", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    
    # Check all format files were created
    txt_file = output_dir / f"{name}.txt"
    json_file = output_dir / f"{name}.json"
    srt_file = output_dir / f"{name}.srt"
    vtt_file = output_dir / f"{name}.vtt"
    
    assert txt_file.exists()
    assert json_file.exists()
    assert srt_file.exists()
    assert vtt_file.exists()
    
    # Validate that no RuntimeWarnings appear in normal mode
    validate_no_runtime_warnings(result.stderr)
    
    # Verify each format has content
    assert txt_file.stat().st_size > 0
    assert json_file.stat().st_size > 0
    assert srt_file.stat().st_size > 0
    assert vtt_file.stat().st_size > 0
    
    # Quick content validation for each format
    with txt_file.open() as f:
        txt_content = f.read()
        assert "[" in txt_content and "]:" in txt_content
    
    with json_file.open() as f:
        json_data = json.load(f)
        assert "transcript" in json_data and "metadata" in json_data
    
    with srt_file.open(encoding="utf-8") as f:
        srt_content = f.read()
        assert "-->" in srt_content and "," in srt_content
    
    with vtt_file.open(encoding="utf-8") as f:
        vtt_content = f.read()
        assert vtt_content.startswith("WEBVTT") and "NOTE" in vtt_content

def test_json_stdout_mode(tmp_path):
    """Test JSON format stdout mode."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "-f", "json", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path)
    )
    
    assert result.returncode == 0
    
    # Should not create any files
    files_created = list(tmp_path.glob("*"))
    assert len(files_created) == 0
    
    # Validate JSON output
    json_data = json.loads(result.stdout)
    assert "transcript" in json_data
    assert "metadata" in json_data
    
    # Check transcript content
    transcript = json_data["transcript"]
    assert len(transcript) > 0
    full_text = " ".join([seg["text"] for seg in transcript])
    assert "Voxdust" in full_text or "command line tool" in full_text

def test_srt_stdout_mode(tmp_path):
    """Test SRT format stdout mode."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "-f", "srt", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path)
    )
    
    assert result.returncode == 0
    
    # Should not create any files
    files_created = list(tmp_path.glob("*"))
    assert len(files_created) == 0
    
    # Validate SRT output format
    srt_content = result.stdout
    assert srt_content.strip()
    
    # Check SRT structure in stdout
    lines = srt_content.strip().split('\n')
    assert lines[0].strip() == "1"  # First segment number
    
    # Find timestamp line
    timestamp_found = False
    for line in lines:
        if "-->" in line:
            timestamp_found = True
            assert "," in line  # SRT comma format
            break
    
    assert timestamp_found
    assert "Voxdust" in srt_content or "command line tool" in srt_content 
import json
import subprocess
from pathlib import Path

from . import EXPECTED_OUTPUT_MP3


def test_vtt_stdout_mode(tmp_path):
    """Test VTT format stdout mode."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "-f", "vtt", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path)
    )
    
    assert result.returncode == 0
    
    # Should not create any files
    files_created = list(tmp_path.glob("*"))
    assert len(files_created) == 0
    
    # Validate VTT output format
    vtt_content = result.stdout
    assert vtt_content.strip()
    assert vtt_content.startswith("WEBVTT\n")
    
    # Check metadata blocks
    assert "NOTE Title" in vtt_content
    assert "NOTE Duration" in vtt_content
    assert "NOTE Language" in vtt_content
    
    # Find timestamp line
    timestamp_found = False
    lines = vtt_content.split('\n')
    for line in lines:
        if "-->" in line and "NOTE" not in line:
            timestamp_found = True
            assert "." in line  # VTT dot format
            break
    
    assert timestamp_found
    assert "Voxdust" in vtt_content or "command line tool" in vtt_content

def test_format_consistency_across_modes(tmp_path):
    """Test that file and stdout modes produce consistent transcript content for each format."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
    formats = ["json", "srt", "vtt"]
    
    # Create stdout test directory
    stdout_test_dir = tmp_path / "stdout_test"
    stdout_test_dir.mkdir(exist_ok=True)
    
    for fmt in formats:
        # Test file mode
        file_result = subprocess.run(
            ["voxtus", "-f", fmt, "-n", f"test_{fmt}", "-o", str(tmp_path), str(test_data)],
            capture_output=True,
            text=True
        )
        
        # Test stdout mode
        stdout_result = subprocess.run(
            ["voxtus", "-f", fmt, "--stdout", str(test_data)],
            capture_output=True,
            text=True,
            cwd=str(stdout_test_dir)  # Use different directory
        )
        
        assert file_result.returncode == 0, f"File mode failed for {fmt}"
        assert stdout_result.returncode == 0, f"Stdout mode failed for {fmt}"
        
        # Read file content
        file_path = tmp_path / f"test_{fmt}.{fmt}"
        assert file_path.exists(), f"Output file not created for {fmt}"
        
        with file_path.open(encoding="utf-8") as f:
            file_content = f.read()
        
        stdout_content = stdout_result.stdout
        
        # Content should match (allowing for slight differences in metadata)
        if fmt == "json":
            file_data = json.loads(file_content)
            stdout_data = json.loads(stdout_content)
            
            # Transcript data should be identical
            assert file_data["transcript"] == stdout_data["transcript"]
            
        elif fmt in ["srt", "vtt"]:
            # For subtitle formats, the subtitle blocks should be identical
            # Extract just the subtitle content (ignore metadata differences)
            
            def extract_subtitle_blocks(content):
                lines = content.split('\n')
                blocks = []
                current_block = []
                
                for line in lines:
                    if fmt == "vtt" and line.startswith("NOTE"):
                        # Skip VTT metadata blocks for comparison
                        continue
                    if line.strip() == "" and current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    elif line.strip():
                        current_block.append(line)
                
                if current_block:
                    blocks.append('\n'.join(current_block))
                
                # Filter out metadata blocks and keep only subtitle blocks
                subtitle_blocks = []
                for block in blocks:
                    if "-->" in block:  # Contains timestamp
                        subtitle_blocks.append(block)
                
                return subtitle_blocks
            
            file_blocks = extract_subtitle_blocks(file_content)
            stdout_blocks = extract_subtitle_blocks(stdout_content)
            
            # Should have same number of subtitle blocks
            assert len(file_blocks) == len(stdout_blocks), f"Different number of subtitle blocks in {fmt}"
            
            # Each subtitle block should be identical
            for i, (file_block, stdout_block) in enumerate(zip(file_blocks, stdout_blocks)):
                assert file_block == stdout_block, f"Subtitle block {i} differs in {fmt} format"

def test_file_vs_stdout_exact_match(tmp_path):
    """Test that file output and stdout output produce consistent transcript content."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    formats = ["txt", "json", "srt", "vtt"]
    
    # Create stdout subdirectory
    stdout_subdir = tmp_path / "stdout_subdir"
    stdout_subdir.mkdir(exist_ok=True)
    
    for fmt in formats:
        # Generate file output
        file_result = subprocess.run(
            ["voxtus", "-f", fmt, "-n", f"exact_test_{fmt}", "-o", str(tmp_path), str(test_data)],
            capture_output=True,
            text=True
        )
        
        # Generate stdout output
        stdout_result = subprocess.run(
            ["voxtus", "-f", fmt, "--stdout", str(test_data)],
            capture_output=True,
            text=True,
            cwd=str(stdout_subdir)  # Different directory to ensure no file creation
        )
        
        assert file_result.returncode == 0, f"File mode failed for {fmt}"
        assert stdout_result.returncode == 0, f"Stdout mode failed for {fmt}"
        
        # Read file content
        output_file = tmp_path / f"exact_test_{fmt}.{fmt}"
        assert output_file.exists(), f"Output file not created for {fmt}"
        
        with output_file.open(encoding="utf-8") as f:
            file_content = f.read()
        
        stdout_content = stdout_result.stdout
        
        # For formats that include metadata (JSON, VTT), the metadata will differ
        # between file and stdout modes (file mode includes actual filename/path,
        # stdout mode uses "unknown"). This is expected behavior.
        # We verify that the transcript content is consistent.
        
        if fmt == "txt":
            # TXT format should be exactly identical
            assert file_content == stdout_content, (
                f"TXT file and stdout output should be identical:\n"
                f"File content:   {repr(file_content)}\n"
                f"Stdout content: {repr(stdout_content)}"
            )
        elif fmt == "json":
            # JSON format: verify transcript data is identical, allow metadata differences
            file_data = json.loads(file_content)
            stdout_data = json.loads(stdout_content)
            
            assert file_data["transcript"] == stdout_data["transcript"], (
                f"JSON transcript data should be identical between file and stdout modes:\n"
                f"File transcript:   {file_data['transcript']}\n"
                f"Stdout transcript: {stdout_data['transcript']}"
            )
            
            # Verify the metadata structure is consistent (but values may differ)
            assert set(file_data["metadata"].keys()) == set(stdout_data["metadata"].keys()), (
                f"JSON metadata keys should be identical:\n"
                f"File keys:   {set(file_data['metadata'].keys())}\n"
                f"Stdout keys: {set(stdout_data['metadata'].keys())}"
            )
            
        elif fmt in ["srt", "vtt"]:
            # For subtitle formats, extract the subtitle blocks (ignore metadata differences for VTT)
            def extract_subtitle_content(content, format_type):
                lines = content.split('\n')
                subtitle_lines = []
                
                for line in lines:
                    # Skip VTT metadata blocks
                    if format_type == "vtt" and line.startswith("NOTE"):
                        continue
                    # Skip VTT header
                    if format_type == "vtt" and line.strip() == "WEBVTT":
                        continue
                    # Include lines with timestamps or subtitle text
                    if "-->" in line or (line.strip() and not line.strip().isdigit()):
                        subtitle_lines.append(line)
                
                return '\n'.join(subtitle_lines).strip()
            
            file_subtitles = extract_subtitle_content(file_content, fmt)
            stdout_subtitles = extract_subtitle_content(stdout_content, fmt)
            
            assert file_subtitles == stdout_subtitles, (
                f"{fmt.upper()} subtitle content should be identical:\n"
                f"File subtitles:   {repr(file_subtitles)}\n"
                f"Stdout subtitles: {repr(stdout_subtitles)}"
            ) 
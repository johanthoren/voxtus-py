import contextlib
import http.server
import os
import socketserver
import subprocess
import threading
import time
from pathlib import Path

EXPECTED_OUTPUT = r"[0.00 - 7.00]:  Voxdust is a command line tool for transcribing internet videos or local audio files into readable text."

@contextlib.contextmanager
def change_directory(path):
    """Context manager for changing directory safely in parallel tests."""
    old_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_cwd)

def get_free_port():
    """Get a free port for HTTP server to avoid conflicts in parallel tests."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def validate_result(result, output_dir, name):
    assert result.returncode == 0
    transcript = output_dir / f"{name}.txt"
    assert transcript.exists()
    with transcript.open() as f:
        contents = f.read()
        assert len(contents.strip()) > 0
        assert EXPECTED_OUTPUT in contents

def validate_stdout_result(result):
    """Validate that stdout mode produces ONLY transcript output with no other messages."""
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0
    
    # Check that the expected transcript content is in stdout
    assert EXPECTED_OUTPUT in result.stdout
    assert "[0.00 -" in result.stdout
    assert "]:" in result.stdout
    
    # In stdout mode, stdout should contain ONLY transcript lines
    # Every line should be a transcript line with the format [start - end]: text
    stdout_lines = result.stdout.strip().split('\n')
    for line in stdout_lines:
        line = line.strip()
        if line:  # Skip empty lines
            assert line.startswith('[') and ']:' in line, f"Non-transcript line found in stdout: '{line}'"

def test_transcribe_local_file(tmp_path):
    """Test local file processing (covers both MP3 and MP4 since they use same code path)."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "sample"

    result = subprocess.run(
        ["voxtus", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    validate_result(result, output_dir, name)

def test_stdout_mode(tmp_path):
    """Test stdout mode functionality."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
    result = subprocess.run(
        ["voxtus", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path)  # Run in temp directory to verify no files are created
    )
    
    validate_stdout_result(result)
    
    # Should not create any files in the working directory
    files_created = list(tmp_path.glob("*"))
    assert len(files_created) == 0, f"Files were created in stdout mode: {files_created}"

def test_http_url_processing(tmp_path):
    """Test HTTP URL processing (parallel-safe version)."""
    data_dir = Path(__file__).parent / "data"
    
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    handler = http.server.SimpleHTTPRequestHandler
    
    # Get a free port to avoid conflicts in parallel execution
    port = get_free_port()
    
    output_dir = tmp_path
    name = "http_test"

    # Use context manager to safely change directory
    with change_directory(data_dir):
        httpd = ReusableTCPServer(("", port), handler)
        
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        time.sleep(1)

        try:
            url = f"http://localhost:{port}/sample_video.mp4"
            result = subprocess.run(
                ["voxtus", "-n", name, "-o", str(output_dir), url],
                capture_output=True,
                text=True,
            )

            validate_result(result, output_dir, name)

        finally:
            httpd.shutdown()
            server_thread.join()
            assert not server_thread.is_alive(), "HTTP server thread is still alive after shutdown"

def test_output_consistency(tmp_path):
    """Test that stdout and file modes produce consistent content."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
    # Run in normal mode
    normal_result = subprocess.run(
        ["voxtus", "-n", "test", "-o", str(tmp_path), str(test_data)],
        capture_output=True,
        text=True
    )
    
    # Create stdout test directory
    stdout_test_dir = tmp_path / "stdout_test"
    stdout_test_dir.mkdir(exist_ok=True)
    
    # Run in stdout mode  
    stdout_result = subprocess.run(
        ["voxtus", "--stdout", str(test_data)],
        capture_output=True,
        text=True,
        cwd=str(stdout_test_dir)  # Different directory
    )
    
    # Both should succeed
    assert normal_result.returncode == 0
    assert stdout_result.returncode == 0
    
    # Read the file created by normal mode
    transcript_file = tmp_path / "test.txt"
    assert transcript_file.exists()
    
    with transcript_file.open() as f:
        file_content = f.read().strip()
    
    # Extract just the transcript lines from stdout (ignore any yt-dlp output)
    stdout_lines = []
    for line in stdout_result.stdout.strip().split('\n'):
        if line.strip() and '[' in line and ']:' in line:
            stdout_lines.append(line.strip())
    
    stdout_content = '\n'.join(stdout_lines)
    
    # The transcript content should match
    assert file_content == stdout_content, f"File content:\n{file_content}\n\nStdout content:\n{stdout_content}"
    
    # Normal mode should have status messages, stdout mode should be mostly silent
    assert len(normal_result.stderr) > 0  # Should have status messages

def test_json_format_output(tmp_path):
    """Test JSON format output structure and content."""
    import json
    
    test_data = Path(__file__).parent / "data" / "sample.mp3"
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
    test_data = Path(__file__).parent / "data" / "sample.mp3"
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
    test_data = Path(__file__).parent / "data" / "sample.mp3"
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
    test_data = Path(__file__).parent / "data" / "sample.mp3"
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
    
    # Verify each format has content
    assert txt_file.stat().st_size > 0
    assert json_file.stat().st_size > 0
    assert srt_file.stat().st_size > 0
    assert vtt_file.stat().st_size > 0
    
    # Quick content validation for each format
    with txt_file.open() as f:
        txt_content = f.read()
        assert "[" in txt_content and "]:" in txt_content
    
    import json
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
    import json
    
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
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
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
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

def test_vtt_stdout_mode(tmp_path):
    """Test VTT format stdout mode."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
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
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    
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
            import json
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

def test_txt_exact_output_match(tmp_path):
    """Test TXT format produces exactly expected output (golden file test)."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    expected_file = Path(__file__).parent / "data" / "expected_output.txt"
    
    # Read expected output
    with expected_file.open(encoding="utf-8") as f:
        expected_output = f.read().strip()
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = subprocess.run(
        ["voxtus", "-f", "txt", "--stdout", "tests/data/sample.mp3"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)  # Run from project root
    )
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert actual_output == expected_output, (
        f"TXT output doesn't match expected:\n"
        f"Expected: {repr(expected_output)}\n"
        f"Actual:   {repr(actual_output)}\n"
        f"Diff:\n"
        f"Expected lines: {expected_output.split()}\n"
        f"Actual lines:   {actual_output.split()}"
    )

def test_json_exact_output_match(tmp_path):
    """Test JSON format produces exactly expected output (golden file test)."""
    import json
    
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    expected_file = Path(__file__).parent / "data" / "expected_output.json"
    
    # Read expected output
    with expected_file.open(encoding="utf-8") as f:
        expected_data = json.load(f)
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = subprocess.run(
        ["voxtus", "-f", "json", "--stdout", "tests/data/sample.mp3"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)  # Run from project root
    )
    
    assert result.returncode == 0
    actual_data = json.loads(result.stdout)
    
    # Compare JSON data structure
    assert actual_data == expected_data, (
        f"JSON output doesn't match expected:\n"
        f"Expected: {json.dumps(expected_data, indent=2)}\n"
        f"Actual:   {json.dumps(actual_data, indent=2)}"
    )

def test_srt_exact_output_match(tmp_path):
    """Test SRT format produces exactly expected output (golden file test)."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    expected_file = Path(__file__).parent / "data" / "expected_output.srt"
    
    # Read expected output
    with expected_file.open(encoding="utf-8") as f:
        expected_output = f.read().strip()
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = subprocess.run(
        ["voxtus", "-f", "srt", "--stdout", "tests/data/sample.mp3"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)  # Run from project root
    )
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert actual_output == expected_output, (
        f"SRT output doesn't match expected:\n"
        f"Expected: {repr(expected_output)}\n"
        f"Actual:   {repr(actual_output)}\n"
        f"Expected lines: {expected_output.splitlines()}\n"
        f"Actual lines:   {actual_output.splitlines()}"
    )

def test_vtt_exact_output_match(tmp_path):
    """Test VTT format produces exactly expected output (golden file test)."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    expected_file = Path(__file__).parent / "data" / "expected_output.vtt"
    
    # Read expected output
    with expected_file.open(encoding="utf-8") as f:
        expected_output = f.read().strip()
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = subprocess.run(
        ["voxtus", "-f", "vtt", "--stdout", "tests/data/sample.mp3"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)  # Run from project root
    )
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert actual_output == expected_output, (
        f"VTT output doesn't match expected:\n"
        f"Expected: {repr(expected_output)}\n"
        f"Actual:   {repr(actual_output)}\n"
        f"Expected lines: {expected_output.splitlines()}\n"
        f"Actual lines:   {actual_output.splitlines()}"
    )

def test_file_vs_stdout_exact_match(tmp_path):
    """Test that file output and stdout output produce consistent transcript content."""
    test_data = Path(__file__).parent / "data" / "sample.mp3"
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
            import json
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

import subprocess
from pathlib import Path

from . import (EXPECTED_OUTPUT_MP3, EXPECTED_OUTPUT_MP4, change_directory,
               get_free_port, validate_no_runtime_warnings, validate_result,
               validate_stdout_result)


def test_transcribe_local_file(tmp_path):
    """Test local file processing (covers both MP3 and MP4 since they use same code path)."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "sample"

    result = subprocess.run(
        ["voxtus", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    validate_result(result, output_dir, name)
    # Validate that no RuntimeWarnings appear in normal mode (our warning suppression works)
    validate_no_runtime_warnings(result.stderr)

def test_stdout_mode(tmp_path):
    """Test stdout mode functionality."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
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

def validate_result_mp4(result, output_dir, name):
    """Validate result for MP4 files with appropriate expected output."""
    assert result.returncode == 0
    transcript = output_dir / f"{name}.txt"
    assert transcript.exists()
    with transcript.open() as f:
        contents = f.read()
        assert len(contents.strip()) > 0
        assert EXPECTED_OUTPUT_MP4 in contents

def test_http_url_processing(tmp_path):
    """Test HTTP URL processing (parallel-safe version)."""
    import http.server
    import socketserver
    import threading
    import time
    
    data_dir = Path(__file__).parent.parent / "data"
    
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

            validate_result_mp4(result, output_dir, name)

        finally:
            httpd.shutdown()
            server_thread.join()
            assert not server_thread.is_alive(), "HTTP server thread is still alive after shutdown"

def test_output_consistency(tmp_path):
    """Test that stdout and file modes produce consistent content."""
    test_data = Path(__file__).parent.parent / "data" / "sample.mp3"
    
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
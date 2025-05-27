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

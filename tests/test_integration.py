import subprocess
import threading
import time
import http.server
import socketserver
import os
from pathlib import Path

EXPECTED_OUTPUT = r"[0.00 - 7.00]:  Voxdust is a command line tool for transcribing internet videos or local audio files into readable text."

def validate_result(result, output_dir, name):
    assert result.returncode == 0
    transcript = output_dir / f"{name}.txt"
    assert transcript.exists()
    with transcript.open() as f:
        contents = f.read()
        assert len(contents.strip()) > 0
        assert EXPECTED_OUTPUT in contents


def test_transcribe_local_mp3(tmp_path):
    test_data = Path(__file__).parent / "data" / "sample.mp3"
    output_dir = tmp_path
    name = "sample"

    result = subprocess.run(
        ["voxtus", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    validate_result(result, output_dir, name)

def test_transcribe_local_mp4(tmp_path):
    test_data = Path(__file__).parent / "data" / "sample_video.mp4"
    output_dir = tmp_path
    name = "sample"

    result = subprocess.run(
        ["voxtus", "-n", name, "-o", str(output_dir), str(test_data)],
        capture_output=True,
        text=True,
    )

    validate_result(result, output_dir, name)

def test_transcribe_http_mp4_via_ytdlp(tmp_path):
    data_dir = Path(__file__).parent / "data"
    os.chdir(data_dir)

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    handler = http.server.SimpleHTTPRequestHandler
    httpd = ReusableTCPServer(("", 0), handler)
    port = httpd.server_address[1]
    output_dir = tmp_path
    name = "http_test"

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

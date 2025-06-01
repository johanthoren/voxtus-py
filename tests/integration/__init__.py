import contextlib
import http.server
import os
import platform
import re
import signal
import socketserver
import subprocess
import threading
import time
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

EXPECTED_OUTPUT_MP3 = r"[0.00 - 7.00]:  VoxDus is a command line tool for transcribing internet videos or local audio files into readable text."
EXPECTED_OUTPUT_MP4 = r"[0.00 - 7.00]:  VoxDus is a command line tool for transcribing internet videos or local audio files into readable text."

# Test model - use tiny for consistency across environments
TEST_MODEL = "tiny"

def normalize_timing_for_integration(text):
    """Normalize timing values for integration test comparison.
    
    This handles differences in model timing between environments by rounding
    end times to the nearest 0.1 second.
    """
    # Handle TXT timing format ([0.00 - 6.96])
    def normalize_txt_timing(match):
        start = float(match.group(1))
        end = float(match.group(2))
        # Round end time to nearest 0.1 second for tolerance
        end_rounded = round(end, 1)
        return f'[{start:.2f} - {end_rounded:.2f}]'
    
    return re.sub(r'\[([0-9.]+) - ([0-9.]+)\]', normalize_txt_timing, text)

def timing_matches_expected(actual_text, expected_patterns):
    """Check if actual text matches any of the expected patterns with timing tolerance."""
    actual_normalized = normalize_timing_for_integration(actual_text)
    
    for pattern in expected_patterns:
        pattern_normalized = normalize_timing_for_integration(pattern)
        if pattern_normalized in actual_normalized:
            return True
    
    return False

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
        assert timing_matches_expected(contents, [EXPECTED_OUTPUT_MP3, EXPECTED_OUTPUT_MP4])

def validate_stdout_result(result):
    """Validate that stdout mode produces ONLY transcript output with no other messages."""
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0
    
    # Check that the expected transcript content is in stdout (with timing tolerance)
    assert timing_matches_expected(result.stdout, [EXPECTED_OUTPUT_MP3, EXPECTED_OUTPUT_MP4])
    assert "[0.00 -" in result.stdout
    assert "]:" in result.stdout
    
    # In stdout mode, stdout should contain ONLY transcript lines
    # Every line should be a transcript line with the format [start - end]: text
    stdout_lines = result.stdout.strip().split('\n')
    for line in stdout_lines:
        line = line.strip()
        if line:  # Skip empty lines
            assert line.startswith('[') and ']:' in line, f"Non-transcript line found in stdout: '{line}'"

def validate_no_runtime_warnings(stderr_content):
    """Validate that stderr doesn't contain RuntimeWarnings from faster-whisper.
    
    This validates our warning suppression is working in normal mode.
    """
    # Check for common RuntimeWarning patterns from faster-whisper
    warning_patterns = [
        "RuntimeWarning",
        "divide by zero",
        "overflow encountered",
        "invalid value encountered in matmul",
        "invalid value encountered in multiply",
    ]
    
    for pattern in warning_patterns:
        assert pattern not in stderr_content, f"Found RuntimeWarning pattern '{pattern}' in stderr: {stderr_content}"

def is_process_terminated_by_signal(returncode, expected_signal):
    """
    Check if a process was terminated by the expected signal across platforms.
    
    Args:
        returncode: Process return code from subprocess
        expected_signal: Expected signal number (e.g., signal.SIGINT, signal.SIGTERM)
    
    Returns:
        bool: True if process was terminated by the expected signal
    """
    if returncode is None:
        return False
    
    # Unix/Linux standard: 128 + signal_number (macOS local testing)
    if returncode == 128 + expected_signal:
        return True
    
    # Linux CI: negative signal number
    if returncode == -expected_signal:
        return True
    
    # Windows signal handling is different and less standardized
    if platform.system() == "Windows":
        # Windows doesn't have POSIX signals, but subprocess.send_signal() 
        # translates them to Windows equivalents
        if expected_signal == signal.SIGINT:
            # Ctrl+C on Windows can return various codes
            return returncode in [-1073741510, 1, 130, -2]  # 0xC000013A and others
        elif expected_signal == signal.SIGTERM:
            # TerminateProcess() on Windows can return various codes  
            return returncode in [1, 143, -15, -1]
    
    return False


def is_process_interrupted(returncode):
    """Check if process was interrupted by any signal (SIGINT or SIGTERM)."""
    return (is_process_terminated_by_signal(returncode, signal.SIGINT) or 
            is_process_terminated_by_signal(returncode, signal.SIGTERM))

def run_voxtus_transcription(command, signal_to_send=None, timeout=10.0):
    """
    Run voxtus command and optionally send a signal to test interruption handling.
    
    Args:
        command: List of command arguments
        signal_to_send: Signal to send to the process (e.g., signal.SIGINT)
        timeout: How long to wait before timing out
    
    Returns:
        subprocess.CompletedProcess with result
    """
    # Start the process
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent)  # Run from project root
    )
    
    if signal_to_send:
        # Give the process a brief moment to start
        time.sleep(0.1)
        
        try:
            # Send the signal
            process.send_signal(signal_to_send)
        except ProcessLookupError:
            # Process may have already finished
            pass
    
    try:
        # Wait for completion with timeout
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            command, process.returncode, stdout, stderr
        )
    except subprocess.TimeoutExpired:
        # If timeout, terminate the process
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        return subprocess.CompletedProcess(
            command, process.returncode, stdout, stderr
        )

# CI environments may be slower, so use generous timeout
CI_TIMEOUT = 120  # 2 minutes for model loading and transcription

def run_voxtus_with_timeout(args, **kwargs):
    """Run voxtus command with consistent timeout handling for CI environments."""
    import subprocess

    # Add test model if no model specified
    if '--model' not in args:
        args = ['voxtus', '--model', TEST_MODEL] + args[1:]
    
    # Set default timeout if not provided
    if 'timeout' not in kwargs:
        kwargs['timeout'] = CI_TIMEOUT
    
    # Set default capture settings if not provided
    if 'capture_output' not in kwargs:
        kwargs['capture_output'] = True
    if 'text' not in kwargs:
        kwargs['text'] = True
    
    return subprocess.run(args, **kwargs) 
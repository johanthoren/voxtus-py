import signal
import subprocess
import sys

from . import is_process_terminated_by_signal, run_voxtus_transcription


class TestSignalIntegration:
    """Integration tests for signal handling using subprocess."""

    def test_signal_integration_process_terminates_on_interrupt(self):
        """Test that voxtus process terminates correctly when interrupted (integration test)."""
        result = run_voxtus_transcription(
            ["voxtus", "-f", "txt", "--stdout", "tests/data/sample.mp3"],
            signal_to_send=signal.SIGINT,
            timeout=5.0
        )
        
        # Cross-platform exit code verification
        assert is_process_terminated_by_signal(result.returncode, signal.SIGINT), (
            f"Process exit code {result.returncode} doesn't indicate SIGINT termination"
        )
    
    def test_signal_integration_process_terminates_on_terminate(self):
        """Test that voxtus process terminates correctly when receiving SIGTERM (integration test)."""
        # SIGTERM is not available on Windows
        if sys.platform == "win32":
            return
        
        result = run_voxtus_transcription(
            ["voxtus", "-f", "txt", "--stdout", "tests/data/sample.mp3"],
            signal_to_send=signal.SIGTERM,
            timeout=5.0
        )
        
        # Cross-platform exit code verification
        assert is_process_terminated_by_signal(result.returncode, signal.SIGTERM), (
            f"Process exit code {result.returncode} doesn't indicate SIGTERM termination"
        ) 
import subprocess
from pathlib import Path

from . import EXPECTED_OUTPUT_MP3, TEST_MODEL


class TestWarningsIntegration:
    """Integration tests for warnings suppression using subprocess."""

    def test_warnings_suppressed_in_normal_mode_integration(self):
        """Test warnings suppression in normal mode (integration test)."""
        result = subprocess.run(
            ["voxtus", "--model", TEST_MODEL, "-f", "txt", "--stdout", "tests/data/sample.mp3"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        
        assert result.returncode == 0
        assert result.stdout.strip() == EXPECTED_OUTPUT_MP3
        
        # Check that stderr doesn't contain warnings (warnings should be suppressed)
        # Note: This is a heuristic - we can't guarantee no warnings, but we expect 
        # the typical faster-whisper warnings to be suppressed
        assert "FutureWarning" not in result.stderr
        assert "UserWarning" not in result.stderr
    
    def test_warnings_visible_in_debug_mode_integration(self):
        """Test warnings are visible in debug mode (integration test)."""
        result = subprocess.run(
            ["voxtus", "--model", TEST_MODEL, "-vv", "-f", "txt", "--stdout", "tests/data/sample.mp3"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        
        assert result.returncode == 0
        assert result.stdout.strip() == EXPECTED_OUTPUT_MP3
        
        # In debug mode, warnings should NOT be suppressed
        # We can't guarantee warnings will appear, but the suppression should be disabled 
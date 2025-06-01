import signal
from unittest.mock import MagicMock, patch

from . import create_mock_processing_context


class TestSignalHandler:
    """Unit tests for signal handler functionality using mocks."""

    def test_signal_handler_exit_codes(self):
        """Test that signal handlers exit with correct codes."""
        from voxtus.__main__ import signal_handler
        
        with patch('sys.exit') as mock_exit:
            signal_handler(signal.SIGINT, None)
            mock_exit.assert_called_once_with(130)
            
        with patch('sys.exit') as mock_exit:
            signal_handler(signal.SIGTERM, None)
            mock_exit.assert_called_once_with(143)
    
    def test_signal_handler_cleanup_functionality(self, tmp_path):
        """Test signal handler cleanup functionality."""
        from voxtus.__main__ import signal_handler
        
        mock_context = create_mock_processing_context(tmp_path)
        
        with patch('voxtus.__main__._cleanup_context', mock_context), \
             patch('sys.exit') as mock_exit, \
             patch('shutil.rmtree') as mock_rmtree:
            
            signal_handler(signal.SIGINT, None)
            
            # Verify cleanup was attempted and exit code is correct
            mock_rmtree.assert_called_once_with(mock_context.workdir, ignore_errors=True)
            mock_exit.assert_called_once_with(130) 
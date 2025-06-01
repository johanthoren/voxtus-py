from unittest.mock import Mock, patch

from . import create_mock_whisper_model


class TestWarningsSuppression:
    """Unit tests for warnings suppression mechanism using mocks."""
    
    def test_warnings_suppressed_in_normal_mode(self, tmp_path):
        """Test that warnings are suppressed when verbose_level < 2."""
        from voxtus.__main__ import transcribe_to_stdout

        mock_model, mock_segment, mock_info = create_mock_whisper_model()
        
        with patch('faster_whisper.WhisperModel', return_value=mock_model), \
             patch('warnings.catch_warnings') as mock_catch_warnings:
            
            mock_context = Mock()
            mock_catch_warnings.return_value.__enter__ = Mock(return_value=mock_context)
            mock_catch_warnings.return_value.__exit__ = Mock(return_value=None)
            
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()
            
            transcribe_to_stdout(audio_file, "txt", "Test Title", "test.mp3", 0)
        
        mock_catch_warnings.assert_called_once()
    
    def test_warnings_visible_in_debug_mode(self, tmp_path):
        """Test that warnings are NOT suppressed when verbose_level >= 2."""
        from voxtus.__main__ import transcribe_to_stdout

        mock_model, mock_segment, mock_info = create_mock_whisper_model()
        
        with patch('faster_whisper.WhisperModel', return_value=mock_model), \
             patch('warnings.catch_warnings') as mock_catch_warnings:
            
            audio_file = tmp_path / "test.mp3"
            audio_file.touch()
            
            transcribe_to_stdout(audio_file, "txt", "Test Title", "test.mp3", 2)
        
        mock_catch_warnings.assert_not_called() 
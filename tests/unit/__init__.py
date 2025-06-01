from unittest.mock import MagicMock, Mock, patch


# Common mock objects for unit tests
def create_mock_whisper_model():
    """Create a mock WhisperModel for unit tests."""
    mock_segment = Mock()
    mock_segment.start = 0.0
    mock_segment.end = 5.0
    mock_segment.text = "Test transcription"
    
    mock_info = Mock()
    mock_info.duration = 10.0
    
    mock_model = Mock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    
    return mock_model, mock_segment, mock_info

def create_mock_processing_context(tmp_path=None):
    """Create a mock ProcessingContext for unit tests."""
    from voxtus.__main__ import ProcessingContext
    
    mock_context = MagicMock(spec=ProcessingContext)
    
    if tmp_path:
        mock_workdir = MagicMock()
        mock_workdir.exists.return_value = True
        mock_context.workdir = mock_workdir
    
    return mock_context 
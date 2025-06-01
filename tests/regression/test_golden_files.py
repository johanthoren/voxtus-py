import json

from . import (EXPECTED_OUTPUT, assert_exact_match, load_golden_file,
               run_voxtus_stdout)


def test_txt_exact_output_match(tmp_path):
    """Test TXT format produces exactly expected output (golden file test)."""
    expected_output = load_golden_file("txt")
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = run_voxtus_stdout("txt", "tests/data/sample.mp3")
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert_exact_match(actual_output, expected_output, "txt")

def test_json_exact_output_match(tmp_path):
    """Test JSON format produces exactly expected output (golden file test)."""
    expected_data = load_golden_file("json")
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = run_voxtus_stdout("json", "tests/data/sample.mp3")
    
    assert result.returncode == 0
    actual_data = json.loads(result.stdout)
    
    assert_exact_match(actual_data, expected_data, "json")

def test_srt_exact_output_match(tmp_path):
    """Test SRT format produces exactly expected output (golden file test)."""
    expected_output = load_golden_file("srt")
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = run_voxtus_stdout("srt", "tests/data/sample.mp3")
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert_exact_match(actual_output, expected_output, "srt")

def test_vtt_exact_output_match(tmp_path):
    """Test VTT format produces exactly expected output (golden file test)."""
    expected_output = load_golden_file("vtt")
    
    # Test stdout mode - use relative path to ensure consistent source metadata
    result = run_voxtus_stdout("vtt", "tests/data/sample.mp3")
    
    assert result.returncode == 0
    actual_output = result.stdout.strip()
    
    assert_exact_match(actual_output, expected_output, "vtt") 
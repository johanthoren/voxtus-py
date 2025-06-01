import json
import re
import subprocess
from pathlib import Path

# Expected output constant for regression tests
EXPECTED_OUTPUT = r"[0.00 - 7.00]:  VoxDus is a command line tool for transcribing internet videos or local audio files into readable text."

def run_voxtus_stdout(format_type, input_file, cwd=None):
    """Run voxtus in stdout mode and return the result."""
    if cwd is None:
        cwd = Path(__file__).parent.parent.parent  # Project root
    
    result = subprocess.run(
        ["voxtus", "--model", "tiny", "-f", format_type, "--stdout", input_file],
        capture_output=True,
        text=True,
        cwd=str(cwd)
    )
    return result

def load_golden_file(format_type):
    """Load the expected golden file for the given format."""
    golden_file = Path(__file__).parent.parent / "data" / f"expected_output.{format_type}"
    
    if format_type == "json":
        with golden_file.open(encoding="utf-8") as f:
            return json.load(f)
    else:
        with golden_file.open(encoding="utf-8") as f:
            return f.read().strip()

def normalize_timing_for_comparison(text, tolerance=0.2):
    """Normalize timing values in text for comparison with tolerance.
    
    This handles differences in model timing between environments.
    """
    def replace_timing(match):
        start = float(match.group(1))
        end = float(match.group(2))
        # Round to nearest 0.1 to handle small timing differences
        start_rounded = round(start, 1)
        end_rounded = round(end, 1)
        return f"{start_rounded:05.2f} --> {end_rounded:05.2f}"
    
    # Handle SRT/VTT timing format (00:00:00,000 --> 00:00:06,960)
    text = re.sub(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})', 
                  lambda m: normalize_srt_timing(m, tolerance), text)
    
    # Handle JSON timing format ("start": 0.0, "end": 6.96)
    text = re.sub(r'"end":\s*([0-9.]+)', 
                  lambda m: f'"end": {round(float(m.group(1)), 1)}', text)
    
    # Handle TXT timing format ([0.00 - 6.96])
    text = re.sub(r'\[([0-9.]+) - ([0-9.]+)\]', 
                  lambda m: f'[{float(m.group(1)):.2f} - {round(float(m.group(2)), 1):.2f}]', text)
    
    return text

def normalize_srt_timing(match, tolerance):
    """Normalize SRT timing format with tolerance."""
    start_h, start_m, start_s, start_ms = map(int, match.groups()[:4])
    end_h, end_m, end_s, end_ms = map(int, match.groups()[4:])
    
    # Convert to total seconds
    start_total = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
    end_total = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000
    
    # Round to nearest 0.1 second
    end_total = round(end_total, 1)
    
    # Convert back to SRT format
    end_h = int(end_total // 3600)
    end_m = int((end_total % 3600) // 60)
    end_s = int(end_total % 60)
    end_ms = int((end_total % 1) * 1000)
    
    return f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"

def assert_exact_match(actual, expected, format_type):
    """Assert that actual output matches expected output with timing tolerance."""
    if format_type == "json":
        # For JSON, normalize timing in both actual and expected
        actual_str = json.dumps(actual, sort_keys=True)
        expected_str = json.dumps(expected, sort_keys=True)
        
        actual_normalized = normalize_timing_for_comparison(actual_str)
        expected_normalized = normalize_timing_for_comparison(expected_str)
        
        assert actual_normalized == expected_normalized, (
            f"JSON output doesn't match expected (with timing tolerance):\n"
            f"Expected: {json.dumps(expected, indent=2)}\n"
            f"Actual:   {json.dumps(actual, indent=2)}"
        )
    else:
        # For text formats, normalize timing
        actual_normalized = normalize_timing_for_comparison(actual)
        expected_normalized = normalize_timing_for_comparison(expected)
        
        assert actual_normalized == expected_normalized, (
            f"{format_type.upper()} output doesn't match expected (with timing tolerance):\n"
            f"Expected: {repr(expected)}\n"
            f"Actual:   {repr(actual)}\n"
            f"Expected lines: {expected.splitlines()}\n"
            f"Actual lines:   {actual.splitlines()}"
        ) 
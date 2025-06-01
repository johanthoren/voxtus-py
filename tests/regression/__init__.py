import json
import subprocess
from pathlib import Path

# Expected output constant for regression tests
EXPECTED_OUTPUT = r"[0.00 - 7.00]:  Voxdust is a command line tool for transcribing internet videos or local audio files into readable text."

def run_voxtus_stdout(format_type, input_file, cwd=None):
    """Run voxtus in stdout mode and return the result."""
    if cwd is None:
        cwd = Path(__file__).parent.parent.parent  # Project root
    
    result = subprocess.run(
        ["voxtus", "-f", format_type, "--stdout", input_file],
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

def assert_exact_match(actual, expected, format_type):
    """Assert that actual output exactly matches expected output."""
    if format_type == "json":
        assert actual == expected, (
            f"JSON output doesn't match expected:\n"
            f"Expected: {json.dumps(expected, indent=2)}\n"
            f"Actual:   {json.dumps(actual, indent=2)}"
        )
    else:
        assert actual == expected, (
            f"{format_type.upper()} output doesn't match expected:\n"
            f"Expected: {repr(expected)}\n"
            f"Actual:   {repr(actual)}\n"
            f"Expected lines: {expected.splitlines()}\n"
            f"Actual lines:   {actual.splitlines()}"
        ) 
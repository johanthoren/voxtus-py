import subprocess


def test_help_output():
    result = subprocess.run(["voxtus", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()

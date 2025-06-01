import importlib.metadata
import subprocess

EXPECTED_HELP_OUTPUT = "usage: voxtus"

def test_help_output():
    result = subprocess.run(["voxtus", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert EXPECTED_HELP_OUTPUT in result.stdout

def test_version_output():
    # Get version dynamically
    try:
        expected_version = importlib.metadata.version("voxtus")
    except importlib.metadata.PackageNotFoundError:
        # This can happen if the package is not installed (e.g. in a CI environment before install)
        # In this case, try to read from pyproject.toml as a fallback
        # This is a simplified parser, assumes version is on a line like: version = "x.y.z"
        try:
            with open("pyproject.toml", "r") as f:
                for line in f:
                    if line.strip().startswith("version"):                        
                        expected_version = line.split("=")[1].strip().replace("\"", "")
                        break
                else:
                    assert False, "Version not found in pyproject.toml and package not installed"
        except FileNotFoundError:
            assert False, "pyproject.toml not found and package not installed"

    expected_version_output = f"voxtus {expected_version}"
    result = subprocess.run(["voxtus", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert expected_version_output in result.stdout

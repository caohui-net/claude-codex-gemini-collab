"""Event CLI entry point."""
import sys
import subprocess
from pathlib import Path


def main():
    """Wrapper for scripts/collab_event.py."""
    script = Path(__file__).parent.parent.parent / "scripts" / "collab_event.py"
    if not script.exists():
        print(f"Error: {script} not found", file=sys.stderr)
        return 1

    result = subprocess.run([sys.executable, str(script)] + sys.argv[1:])
    return result.returncode

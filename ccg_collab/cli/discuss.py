"""Discussion CLI entry point."""
import sys
import subprocess
from pathlib import Path


def main():
    """Wrapper for ccg_collab/scripts/collab_discuss.py."""
    script = Path(__file__).parent.parent / "scripts" / "collab_discuss.py"
    if not script.exists():
        print(f"Error: {script} not found", file=sys.stderr)
        return 1

    result = subprocess.run([sys.executable, str(script)] + sys.argv[1:])
    return result.returncode

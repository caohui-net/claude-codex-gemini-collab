#!/usr/bin/env python3
"""Path resolution for collaboration workspace root."""

import subprocess
from pathlib import Path


def find_upward_collaboration(start_dir=None):
    """Search upward for .omc/collaboration/ directory."""
    current = Path(start_dir or ".").resolve()

    while True:
        collab_dir = current / ".omc" / "collaboration"
        if collab_dir.exists() and collab_dir.is_dir():
            return current

        if current.parent == current:
            return None
        current = current.parent


def find_git_root(start_dir=None):
    """Find git repository root, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start_dir or ".",
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def resolve_existing_base_dir(base_dir=None, start_dir=None):
    """
    Resolve base directory for non-init commands.

    Resolution order:
    1. --base-dir (if specified)
    2. Upward search for .omc/collaboration/
    3. Fail with diagnostic

    Returns: Path object
    Raises: ValueError if not found
    """
    if base_dir:
        resolved = Path(base_dir).resolve()
        collab_dir = resolved / ".omc" / "collaboration"
        if not collab_dir.exists() or not collab_dir.is_dir():
            raise ValueError(
                f"No .omc/collaboration directory found at {resolved}. "
                "Run init or use a valid --base-dir."
            )
        return resolved

    found = find_upward_collaboration(start_dir)
    if found:
        return found

    cwd = Path(start_dir or ".").resolve()
    raise ValueError(
        f"No .omc/collaboration directory found from {cwd} upward. "
        "Run init or pass --base-dir."
    )


def resolve_init_base_dir(base_dir=None, start_dir=None):
    """
    Resolve base directory for init command.

    Resolution order:
    1. --base-dir (if specified)
    2. Existing upward .omc/collaboration/ (reuse, avoid nested state)
    3. Git root (if inside git repo)
    4. Current working directory

    Returns: (Path, source_name) tuple
    """
    if base_dir:
        return Path(base_dir).resolve(), "--base-dir"

    # Check for existing state (avoid nested)
    existing = find_upward_collaboration(start_dir)
    if existing:
        return existing, "existing"

    # Try git root
    git_root = find_git_root(start_dir)
    if git_root:
        return git_root, "git"

    # Fall back to cwd
    return Path(start_dir or ".").resolve(), "cwd"


def add_base_dir_arg(parser):
    """Add --base-dir argument to argparse parser."""
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Explicit collaboration workspace root directory"
    )

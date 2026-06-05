"""Path validation for execution security."""

from pathlib import Path
from typing import Tuple


EXECUTION_POLICY = {
    "allowed_paths": ["src/", "scripts/", "tests/", "docs/"],
    "forbidden_paths": [".git/", ".omc/collaboration/state.json", ".omc/collaboration/events.jsonl"],
    "allow_symlinks": False,
    "allow_absolute_paths": False,
}


def validate_path(path: str, base_dir: Path, policy: dict = None) -> Tuple[bool, str]:
    """Validate target path meets security policy.

    Returns: (is_valid, error_message)
    """
    if policy is None:
        policy = EXECUTION_POLICY

    try:
        p = Path(path)

        # Check absolute path
        if p.is_absolute() and not policy["allow_absolute_paths"]:
            return False, f"Absolute paths not allowed: {path}"

        # Normalize to absolute
        if not p.is_absolute():
            p = base_dir / p
        resolved = p.resolve()

        # Check within base_dir
        try:
            resolved.relative_to(base_dir)
        except ValueError:
            return False, f"Path outside workspace: {path}"

        # Check symlink
        if p.is_symlink() and not policy["allow_symlinks"]:
            return False, f"Symlinks not allowed: {path}"

        # Check forbidden paths
        for forbidden in policy["forbidden_paths"]:
            forbidden_resolved = (base_dir / forbidden).resolve()
            try:
                if resolved.is_relative_to(forbidden_resolved):
                    return False, f"Forbidden path: {path}"
            except (ValueError, AttributeError):
                pass

        # Check allowed paths
        for allowed in policy["allowed_paths"]:
            allowed_resolved = (base_dir / allowed).resolve()
            try:
                if resolved.is_relative_to(allowed_resolved):
                    return True, ""
            except (ValueError, AttributeError):
                pass

        return False, f"Path not in allowed list: {path}"

    except Exception as e:
        return False, f"Path validation error: {e}"

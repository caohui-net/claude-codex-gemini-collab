"""Discussion artifact management."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict


def save_artifact(base_dir: Path, task_id: str, round_num: int, agent: str, content: str) -> str:
    """Save discussion artifact to file, return relative path."""
    artifacts_dir = base_dir / ".omc" / "collaboration" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{task_id}-discuss-r{round_num}-{agent}-{timestamp}.md"
    artifact_path = artifacts_dir / filename

    artifact_path.write_text(content)
    return str(artifact_path.relative_to(base_dir))

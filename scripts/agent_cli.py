#!/usr/bin/env python3
"""CLI wrappers for Codex and Gemini agents."""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentReply:
    """Agent response data."""
    agent: str
    raw_text: str
    parsed: dict
    artifact_path: str
    elapsed_sec: float
    exit_code: int


def run_codex(prompt: str, base_dir: Path, timeout_sec: int = 180) -> AgentReply:
    """Run Codex CLI in read-only mode."""
    start = time.time()

    cmd = [
        "codex", "exec",
        "--cd", str(base_dir),
        "--sandbox", "read-only",
        "-"
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.time() - start

        # Extract last message (Codex output after "codex\n")
        raw_text = result.stdout
        lines = raw_text.split('\n')

        # Find "codex" marker and extract response
        response_lines = []
        found_marker = False
        for line in lines:
            if line.strip() == "codex":
                found_marker = True
                continue
            if found_marker and line.strip() and not line.startswith("tokens used"):
                response_lines.append(line)

        response = '\n'.join(response_lines).strip()

        # Try to parse as JSON
        parsed = {}
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {"raw": response}

        return AgentReply(
            agent="codex",
            raw_text=response,
            parsed=parsed,
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return AgentReply(
            agent="codex",
            raw_text="",
            parsed={"error": "timeout"},
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=124,
        )
    except Exception as e:
        elapsed = time.time() - start
        return AgentReply(
            agent="codex",
            raw_text="",
            parsed={"error": str(e)},
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=1,
        )


def run_gemini(prompt: str, base_dir: Path, timeout_sec: int = 180) -> AgentReply:
    """Run Gemini CLI in plan mode with JSON output."""
    start = time.time()

    cmd = [
        "gemini",
        "--prompt", prompt,
        "--output-format", "json",
        "--approval-mode", "plan",
        "--skip-trust",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(base_dir),
        )
        elapsed = time.time() - start

        # Parse JSON output
        parsed = {}
        response = ""
        try:
            output = json.loads(result.stdout)
            response = output.get("response", "")
            parsed = {"response": response, "stats": output.get("stats", {})}
        except json.JSONDecodeError:
            response = result.stdout
            parsed = {"raw": response}

        return AgentReply(
            agent="gemini",
            raw_text=response,
            parsed=parsed,
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return AgentReply(
            agent="gemini",
            raw_text="",
            parsed={"error": "timeout"},
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=124,
        )
    except Exception as e:
        elapsed = time.time() - start
        return AgentReply(
            agent="gemini",
            raw_text="",
            parsed={"error": str(e)},
            artifact_path="",
            elapsed_sec=elapsed,
            exit_code=1,
        )

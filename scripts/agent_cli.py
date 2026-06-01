#!/usr/bin/env python3
"""CLI wrappers for Codex and Gemini agents."""

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Import Daemon client
sys.path.insert(0, str(Path(__file__).parent))
from ccg_client import submit_task, get_task_status


@dataclass
class AgentReply:
    """Agent response data."""
    agent: str
    raw_text: str
    parsed: dict
    artifact_path: str
    elapsed_sec: float
    exit_code: int


def strip_markdown_json(text: str) -> str:
    """Strip markdown JSON code blocks."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def run_codex(prompt: str, base_dir: Path, timeout_sec: int = 180) -> AgentReply:
    """Run Codex CLI for discussion analysis."""
    start = time.time()

    # Try Daemon first
    task_id = submit_task({
        "cmd": ["codex", "exec", "--cd", str(base_dir), "-"],
        "cwd": str(base_dir),
        "timeout": timeout_sec,
        "stdin": prompt
    })

    if task_id:
        # Poll for completion
        poll_interval = 0.1  # 100ms
        max_wait = timeout_sec
        waited = 0.0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            status = get_task_status(task_id)
            if not status:
                break  # Daemon lost, fallback

            if status["status"] == "completed":
                elapsed = time.time() - start
                full_stdout = status.get("stdout", "")

                # Extract content between markers
                if "[RESPONSE_START]" in full_stdout and "[RESPONSE_END]" in full_stdout:
                    start_idx = full_stdout.index("[RESPONSE_START]") + len("[RESPONSE_START]")
                    end_idx = full_stdout.index("[RESPONSE_END]")
                    response = full_stdout[start_idx:end_idx].strip()
                else:
                    response = full_stdout.strip()

                response = strip_markdown_json(response)

                if not response or response.lower() in ("ready", "ready."):
                    return AgentReply(
                        agent="codex",
                        raw_text=full_stdout,
                        parsed={"error": "codex_no_response", "raw": response},
                        artifact_path="",
                        elapsed_sec=elapsed,
                        exit_code=status.get("exit_code", 0),
                    )

                parsed = {}
                try:
                    parsed = json.loads(response)
                except json.JSONDecodeError:
                    parsed = {"error": "json_parse_failed", "raw": response}

                return AgentReply(
                    agent="codex",
                    raw_text=full_stdout,
                    parsed=parsed,
                    artifact_path="",
                    elapsed_sec=elapsed,
                    exit_code=status.get("exit_code", 0),
                )

            elif status["status"] in ("failed", "timeout", "cancelled"):
                # Daemon task failed, break to fallback to direct CLI
                break

            # Increase poll interval gradually
            poll_interval = min(poll_interval * 1.5, 0.5)

        # Timeout waiting for Daemon
        if waited >= max_wait:
            elapsed = time.time() - start
            return AgentReply(
                agent="codex",
                raw_text="",
                parsed={"error": "daemon_timeout"},
                artifact_path="",
                elapsed_sec=elapsed,
                exit_code=124,
            )

    # Fallback: Direct CLI execution
    cmd = [
        "codex", "exec",
        "--cd", str(base_dir),
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

        # Keep full stdout for protocol enforcement and artifact saving
        full_stdout = result.stdout

        # Try to extract content between [RESPONSE_START] and [RESPONSE_END]
        if "[RESPONSE_START]" in full_stdout and "[RESPONSE_END]" in full_stdout:
            start_idx = full_stdout.index("[RESPONSE_START]") + len("[RESPONSE_START]")
            end_idx = full_stdout.index("[RESPONSE_END]")
            response = full_stdout[start_idx:end_idx].strip()
        else:
            # Fallback: use full stdout (for backward compatibility)
            response = full_stdout.strip()

        # Strip markdown blocks and parse JSON
        response = strip_markdown_json(response)

        # Handle non-JSON responses (e.g., "Ready.")
        if not response or response.lower() in ("ready", "ready."):
            return AgentReply(
                agent="codex",
                raw_text=full_stdout,
                parsed={"error": "codex_no_response", "raw": response},
                artifact_path="",
                elapsed_sec=elapsed,
                exit_code=result.returncode,
            )

        parsed = {}
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {"error": "json_parse_failed", "raw": response}

        return AgentReply(
            agent="codex",
            raw_text=full_stdout,
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

    # Try Daemon first
    task_id = submit_task({
        "cmd": ["gemini", "--prompt", prompt, "--output-format", "json",
                "--approval-mode", "plan", "--skip-trust"],
        "cwd": str(base_dir),
        "timeout": timeout_sec
    })

    if task_id:
        # Poll for completion
        poll_interval = 0.1  # 100ms
        max_wait = timeout_sec
        waited = 0.0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            status = get_task_status(task_id)
            if not status:
                break  # Daemon lost, fallback

            if status["status"] == "completed":
                elapsed = time.time() - start
                stdout = status.get("stdout", "")

                # Parse JSON output
                parsed = {}
                full_response = ""
                try:
                    output = json.loads(stdout)
                    full_response = output.get("response", "")

                    # Extract content between markers if present
                    if "[RESPONSE_START]" in full_response and "[RESPONSE_END]" in full_response:
                        start_idx = full_response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
                        end_idx = full_response.index("[RESPONSE_END]")
                        response = full_response[start_idx:end_idx].strip()
                    else:
                        response = full_response

                    response = strip_markdown_json(response)
                    try:
                        parsed = json.loads(response)
                    except json.JSONDecodeError:
                        parsed = {"raw": response}

                except json.JSONDecodeError:
                    full_response = stdout
                    parsed = {"raw": full_response}

                return AgentReply(
                    agent="gemini",
                    raw_text=full_response,
                    parsed=parsed,
                    artifact_path="",
                    elapsed_sec=elapsed,
                    exit_code=status.get("exit_code", 0),
                )

            elif status["status"] in ("failed", "timeout", "cancelled"):
                # Daemon task failed, break to fallback to direct CLI
                break

            # Increase poll interval gradually
            poll_interval = min(poll_interval * 1.5, 0.5)

        # Timeout waiting for Daemon
        if waited >= max_wait:
            elapsed = time.time() - start
            return AgentReply(
                agent="gemini",
                raw_text="",
                parsed={"error": "daemon_timeout"},
                artifact_path="",
                elapsed_sec=elapsed,
                exit_code=124,
            )

    # Fallback: Direct CLI execution
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
        full_response = ""
        try:
            output = json.loads(result.stdout)
            full_response = output.get("response", "")

            # Extract content between markers if present
            if "[RESPONSE_START]" in full_response and "[RESPONSE_END]" in full_response:
                start_idx = full_response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
                end_idx = full_response.index("[RESPONSE_END]")
                response = full_response[start_idx:end_idx].strip()
            else:
                response = full_response

            # Strip markdown and parse inner JSON
            response = strip_markdown_json(response)
            try:
                parsed = json.loads(response)
            except json.JSONDecodeError:
                parsed = {"raw": response}

        except json.JSONDecodeError:
            full_response = result.stdout
            parsed = {"raw": full_response}

        return AgentReply(
            agent="gemini",
            raw_text=full_response,
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

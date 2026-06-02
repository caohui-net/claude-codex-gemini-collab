#!/usr/bin/env python3
"""CLI wrappers for Codex and Gemini agents."""

import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

# Import Daemon client
sys.path.insert(0, str(Path(__file__).parent))
from ccg_client import submit_task, get_task_status
from rmux_utils import check_rmux_available


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


def run_in_tmux(cmd: list, cwd: str, stdin_data: str, timeout_sec: int, keep_session: bool = False) -> tuple[str, int]:
    """Execute command in isolated tmux session and return output.

    Args:
        cmd: Command to execute
        cwd: Working directory
        stdin_data: Data to send to stdin (optional)
        timeout_sec: Timeout in seconds
        keep_session: If True, preserve session for debugging (default: False)

    Returns:
        tuple: (stdout, exit_code)
        If keep_session=True, session name is printed to stdout for manual attachment
    """
    import shlex

    session_name = f"ccg-{uuid.uuid4().hex[:8]}"
    marker_file = f"/tmp/ccg-exit-{session_name}"
    eof_marker = f"CCG_EOF_{uuid.uuid4().hex}"

    try:
        # Build wrapper script that captures exit code and keeps session alive
        quoted_cmd = " ".join(shlex.quote(arg) for arg in cmd)

        if keep_session:
            # Keep session alive indefinitely for debugging
            if stdin_data:
                wrapper = f"cd {shlex.quote(cwd)} && ({quoted_cmd} << '{eof_marker}'\n{stdin_data}\n{eof_marker}\n); echo $? > {marker_file}; exec bash"
            else:
                wrapper = f"cd {shlex.quote(cwd)} && {quoted_cmd}; echo $? > {marker_file}; exec bash"
        else:
            # Normal: session exits after sleep
            if stdin_data:
                wrapper = f"cd {shlex.quote(cwd)} && ({quoted_cmd} << '{eof_marker}'\n{stdin_data}\n{eof_marker}\n); echo $? > {marker_file}; sleep 2"
            else:
                wrapper = f"cd {shlex.quote(cwd)} && {quoted_cmd}; echo $? > {marker_file}; sleep 2"

        # Run in tmux session that auto-exits
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", wrapper],
            timeout=5,
            check=True
        )

        # Wait for marker file (command completed) or timeout
        start = time.time()
        exit_code = None
        while time.time() - start < timeout_sec:
            # Check if marker file exists (command completed)
            try:
                with open(marker_file, 'r') as f:
                    exit_code = int(f.read().strip())
                break
            except (FileNotFoundError, ValueError):
                pass
            time.sleep(0.2)

        if exit_code is None:
            # Timeout - kill session unless keep_session is True
            if not keep_session:
                subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
            subprocess.run(["rm", "-f", marker_file], capture_output=True)

            if keep_session:
                return f"[timeout - session preserved: {session_name}]", 124
            return "", 124

        # Capture output while session is still alive
        output_result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-"],
            capture_output=True,
            text=True,
            timeout=5
        )
        stdout = output_result.stdout if output_result.returncode == 0 else ""

        # Cleanup (conditional on keep_session)
        if keep_session:
            # Preserve session for debugging
            attach_msg = f"\n[tmux session preserved: {session_name}]\n[attach: tmux attach -t {session_name}]\n"
            stdout = stdout + attach_msg
        else:
            # Normal cleanup
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

        subprocess.run(["rm", "-f", marker_file], capture_output=True)

        return stdout, exit_code

    except subprocess.TimeoutExpired:
        if not keep_session:
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        subprocess.run(["rm", "-f", marker_file], capture_output=True)

        if keep_session:
            return f"[TimeoutExpired - session preserved: {session_name}]", 124
        return "", 124
    except Exception as e:
        if not keep_session:
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        subprocess.run(["rm", "-f", marker_file], capture_output=True)

        if keep_session:
            return f"Error: {e} [session preserved: {session_name}]", 1
        return f"Error: {e}", 1


def run_codex(prompt: str, base_dir: Path, timeout_sec: int = 180, use_tmux: bool = False, keep_session: bool = False) -> AgentReply:
    """Run Codex CLI for discussion analysis.

    Args:
        prompt: Input prompt for codex
        base_dir: Working directory
        timeout_sec: Timeout in seconds
        use_tmux: If True and rmux available, run in isolated tmux session
    """
    start = time.time()

    # Check if tmux should be used
    should_use_tmux = use_tmux and check_rmux_available()

    # Try Daemon first (only if not using tmux)
    task_id = None
    if not should_use_tmux:
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

    # Tmux execution path
    if should_use_tmux:
        cmd = ["codex", "exec", "--cd", str(base_dir), "-"]
        stdout, exit_code = run_in_tmux(cmd, str(base_dir), prompt, timeout_sec, keep_session)
        elapsed = time.time() - start

        if exit_code == 124:
            return AgentReply(
                agent="codex",
                raw_text="",
                parsed={"error": "timeout"},
                artifact_path="",
                elapsed_sec=elapsed,
                exit_code=124,
            )

        # Parse output same as regular path
        full_stdout = stdout
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
                exit_code=exit_code,
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
            exit_code=exit_code,
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


def run_gemini(prompt: str, base_dir: Path, timeout_sec: int = 180, use_tmux: bool = False, keep_session: bool = False) -> AgentReply:
    """Run Gemini CLI in plan mode with JSON output.

    Args:
        prompt: Input prompt for gemini
        base_dir: Working directory
        timeout_sec: Timeout in seconds
        use_tmux: If True and rmux available, run in isolated tmux session
    """
    start = time.time()

    # Check if tmux should be used
    should_use_tmux = use_tmux and check_rmux_available()

    # Try Daemon first (only if not using tmux)
    task_id = None
    if not should_use_tmux:
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

    # Tmux execution path
    if should_use_tmux:
        cmd = ["gemini", "--prompt", prompt, "--output-format", "json",
               "--approval-mode", "plan", "--skip-trust"]
        stdout, exit_code = run_in_tmux(cmd, str(base_dir), "", timeout_sec, keep_session)
        elapsed = time.time() - start

        if exit_code == 124:
            return AgentReply(
                agent="gemini",
                raw_text="",
                parsed={"error": "timeout"},
                artifact_path="",
                elapsed_sec=elapsed,
                exit_code=124,
            )

        # Parse output
        parsed = {}
        full_response = ""
        try:
            output = json.loads(stdout)
            full_response = output.get("response", "")

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
            exit_code=exit_code,
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

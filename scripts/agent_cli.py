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
from taolun_client import submit_task, get_task_status
from rmux_utils import check_rmux_available
from file_injector import inject_files


@dataclass
class AgentReply:
    """Agent response data."""
    agent: str
    raw_text: str
    parsed: dict
    artifact_path: str
    elapsed_sec: float
    exit_code: int


# ========== HTTP & Config Utilities ==========

class AgentConfig:
    """统一配置管理器 - 支持多种配置格式"""

    def __init__(self, agent_name: str):
        self.agent = agent_name
        self._config: dict = {}
        self._error: str = ""
        self._load()

    def _load(self):
        """根据agent类型加载相应配置"""
        if self.agent == "codex":
            self._load_codex()
        elif self.agent == "gemini":
            self._load_gemini()

    def _load_codex(self):
        """加载Codex配置：auth.json + config.toml"""
        # Load auth.json
        auth_path = Path.home() / ".codex" / "auth.json"
        auth, err = _load_json_config(auth_path)
        if err:
            self._error = err
            return

        api_key = auth.get("api_key", "") or auth.get("OPENAI_API_KEY", "")
        if not api_key:
            self._error = "missing api_key in auth.json"
            return

        # Load config.toml
        config_path = Path.home() / ".codex" / "config.toml"
        try:
            import tomllib
            config = tomllib.loads(config_path.read_text())
            provider = config.get("model_provider", "fox")
            model = config.get("model", "gpt-5.5")

            # Try top-level base_url first, then nested
            base_url = config.get("base_url", "")
            if not base_url:
                base_url = config.get("model_providers", {}).get(provider, {}).get("base_url", "")

            self._config = {
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "provider": provider,
            }
        except Exception as e:
            self._error = f"config.toml read failed: {e}"

    def _load_gemini(self):
        """加载Gemini配置：.env"""
        env_path = Path.home() / ".gemini" / ".env"
        cfg: dict = {}
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    cfg[k.strip()] = v.strip()
        except Exception as e:
            self._error = f"env read failed: {e}"
            return

        self._config = {
            "base_url": cfg.get("GOOGLE_GEMINI_BASE_URL", "").rstrip("/"),
            "api_key": cfg.get("GEMINI_API_KEY", ""),
            "model": cfg.get("GEMINI_MODEL", "gemini-3-pro-preview"),
        }

    def get(self, key: str, default=None):
        """获取配置项"""
        return self._config.get(key, default)

    def validate(self, *required_keys) -> tuple[bool, str]:
        """验证必需配置项，返回 (是否有效, 错误信息)"""
        if self._error:
            return False, self._error

        missing = [k for k in required_keys if not self.get(k)]
        if missing:
            return False, f"missing: {', '.join(missing)}"
        return True, ""


def _http_post_json(url: str, body: dict, headers: dict, timeout_sec: int = 60) -> tuple[dict, int, str]:
    """Send HTTP POST request with JSON body.

    Returns: (response_json, status_code, error_message)
    """
    import urllib.request
    import urllib.error

    try:
        body_bytes = json.dumps(body).encode()
        req = urllib.request.Request(url, data=body_bytes, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            response_data = json.loads(resp.read().decode())
            return response_data, resp.status, ""
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {}, e.code, f"HTTP {e.code}: {error_body[:200]}"
    except urllib.error.URLError as e:
        return {}, 0, f"URL error: {e.reason}"
    except Exception as e:
        return {}, 0, f"Request failed: {e}"


def _load_json_config(path: Path) -> tuple[dict, str]:
    """Load JSON config file.

    Returns: (config_dict, error_message)
    """
    try:
        return json.loads(path.read_text()), ""
    except Exception as e:
        return {}, f"Failed to load {path}: {e}"


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

    session_name = f"taolun-{uuid.uuid4().hex[:8]}"
    marker_file = f"/tmp/taolun-exit-{session_name}"
    eof_marker = f"TAOLUN_EOF_{uuid.uuid4().hex}"

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


def run_codex_api(prompt: str, timeout_sec: int = 60, files: list[str] = None) -> AgentReply:
    """Call Codex via API directly (bypasses CLI, no Cloudflare timeout).

    Reads config from ~/.codex/auth.json and ~/.codex/config.toml.
    Controlled by env: TAOLUN_CODEX_BACKEND=api (enable) | cli (force CLI).

    Args:
        prompt: The analysis prompt
        timeout_sec: HTTP timeout in seconds
        files: Optional list of file paths to inject as context
    """
    import os
    import urllib.request
    import urllib.error
    import tomllib

    start = time.time()

    # Debug: log prompt length
    print(f"🐛 [Debug] run_codex_api called with prompt length: {len(prompt)}", file=sys.stderr, flush=True)
    print(f"🐛 [Debug] Prompt preview: {prompt[:100]}...", file=sys.stderr, flush=True)
    if files:
        print(f"🐛 [Debug] Files to inject: {len(files)}", file=sys.stderr, flush=True)

    # Load configuration using unified manager
    config = AgentConfig("codex")
    valid, err = config.validate("api_key", "base_url", "model")
    if not valid:
        return AgentReply("codex", "", {"error": err}, "", time.time() - start, 1)

    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")

    url = base_url.rstrip("/") + "/chat/completions"

    # Inject file contents into prompt if files provided
    enhanced_prompt = prompt
    if files:
        file_contexts = []
        for file_path in files:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                file_contexts.append(f"### File: {file_path}\n```\n{content}\n```")
                print(f"📎 [Debug] Injected {file_path} ({len(content)} chars)", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"⚠️  [Debug] Failed to read {file_path}: {e}", file=sys.stderr, flush=True)

        if file_contexts:
            enhanced_prompt = f"{prompt}\n\n## Context Files\n\n" + "\n\n".join(file_contexts)
            print(f"🐛 [Debug] Enhanced prompt length: {len(enhanced_prompt)}", file=sys.stderr, flush=True)

    # System prompt - keep short to avoid API failures with long prompts
    system_prompt = "You are Codex, an expert code reviewer."

    # Build request body
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_prompt}
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Send HTTP request using utility
    data, status_code, http_err = _http_post_json(url, body, headers, timeout_sec)
    if http_err:
        return AgentReply("codex", "", {"error": http_err}, "", time.time() - start, 1)

    print(f"🐛 [Debug] HTTP status: {status_code}", file=sys.stderr, flush=True)
    print(f"🐛 [Debug] Parsed JSON keys: {list(data.keys())}", file=sys.stderr, flush=True)

    # 打印完整的choices结构来诊断为什么content为空
    if "choices" in data and len(data["choices"]) > 0:
        choice = data["choices"][0]
        print(f"🐛 [Debug] Choice keys: {list(choice.keys())}", file=sys.stderr, flush=True)
        print(f"🐛 [Debug] Choice structure: {json.dumps(choice, ensure_ascii=False)[:300]}", file=sys.stderr, flush=True)

    # Extract content: prefer content field, fallback to reasoning_content only if content is empty
    message = data["choices"][0]["message"]
    reasoning = message.get("reasoning_content")
    regular = message.get("content", "")
    content = regular if regular else reasoning

    print(f"🐛 [Debug] API response content length: {len(content)}", file=sys.stderr, flush=True)
    print(f"🐛 [Debug] Content preview: {content[:200]}...", file=sys.stderr, flush=True)

    elapsed = time.time() - start
    parsed = {}
    try:
        parsed = json.loads(strip_markdown_json(content))
    except json.JSONDecodeError:
        parsed = {"raw": content}
    return AgentReply("codex", content, parsed, "", elapsed, 0)


def run_codex(prompt: str, base_dir: Path, files: list[str] = None, timeout_sec: int = 180, use_tmux: bool = False, keep_session: bool = False, reasoning_effort: str = None) -> AgentReply:
    """Run Codex for discussion analysis with two-phase reasoning optimization.

    Args:
        files: Optional list of file paths (relative to base_dir) to inject as context.
               Small files (<5KB) are injected as full content.
               Large files are referenced by path (CLI mode only).
        reasoning_effort: Override reasoning effort ("low", "medium", "high").
                         If None, uses two-phase strategy: medium first, then high if issues found.

    Backend selection via TAOLUN_CODEX_BACKEND env var:
      api  — direct API call (fast, no CLI overhead)
      cli  — force CLI (default legacy behavior)
      unset — api if available, fallback to cli
    """
    import os

    # 准备文件路径列表（用于--image参数）
    file_paths = []
    if files:
        file_paths = [str(base_dir / f) for f in files]
        print(f"📎 [Codex] 附加文件: {len(file_paths)}个", file=sys.stderr, flush=True)

    backend = os.environ.get("TAOLUN_CODEX_BACKEND", "api").lower()
    print(f"🔍 [Codex] 使用backend模式: {backend}", file=sys.stderr)
    if backend == "api":
        print(f"🔍 [Codex] API模式 timeout={min(timeout_sec, 120)}秒", file=sys.stderr)
        return run_codex_api(prompt, timeout_sec=min(timeout_sec, 120), files=file_paths)
    if backend == "auto":
        reply = run_codex_api(prompt, timeout_sec=30)
        if reply.exit_code == 0:
            return reply
        # fallback to CLI below

    # CLI mode: use reasoning_effort parameter
    # Default to None which will use config.toml's setting

    start = time.time()

    # Check if tmux should be used
    should_use_tmux = use_tmux and check_rmux_available()

    # Try Daemon first (only if not using tmux)
    task_id = None
    if not should_use_tmux:
        # Build command with optional reasoning_effort override
        cmd = ["codex", "exec", "--cd", str(base_dir), "--skip-git-repo-check"]
        if reasoning_effort:
            cmd.extend(["-c", f"model_reasoning_effort={reasoning_effort}"])
            print(f"🎯 [Codex] 推理模式: {reasoning_effort}", file=sys.stderr, flush=True)
        # 添加文件附件
        for file_path in file_paths:
            cmd.extend(["--image", file_path])
        cmd.append("-")

        task_id = submit_task({
            "cmd": cmd,
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

                # Extract Codex response from CLI output format
                response = full_stdout.strip()

                # Strategy 1: Try parsing as nested JSON first (Codex CLI wraps response)
                try:
                    outer = json.loads(full_stdout)
                    if isinstance(outer, dict) and "response" in outer:
                        response = outer["response"]
                except json.JSONDecodeError:
                    pass

                # Strategy 2: Extract between markers (most reliable)
                if "[RESPONSE_START]" in response and "[RESPONSE_END]" in response:
                    start_idx = response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
                    end_idx = response.index("[RESPONSE_END]")
                    response = response[start_idx:end_idx].strip()
                # Strategy 3: Extract from CLI format (find LAST "codex\n" before "tokens used")
                elif "\ntokens used" in response and "\ncodex\n" in response:
                    tokens_idx = response.index("\ntokens used")
                    last_codex_idx = response[:tokens_idx].rfind("\ncodex\n")
                    if last_codex_idx >= 0:
                        start_idx = last_codex_idx + len("\ncodex\n")
                        response = response[start_idx:tokens_idx].strip()
                elif "\ncodex\n" in response:
                    start_idx = response.rfind("\ncodex\n") + len("\ncodex\n")
                    response = response[start_idx:].strip()

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
                    cleaned = strip_markdown_json(response)
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    # Try extracting first {...} block from prose response
                    import re
                    m = re.search(r'\{.*\}', response, re.DOTALL)
                    if m:
                        try:
                            parsed = json.loads(m.group())
                        except json.JSONDecodeError:
                            pass
                if not parsed:
                    # DEBUG: Log parsing failure
                    debug_log = Path("/tmp/codex_parse_debug.log")
                    with open(debug_log, "a") as f:
                        f.write(f"\n{'='*60}\n")
                        f.write(f"[DAEMON] Parse failed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Full stdout (first 1000): {full_stdout[:1000]}\n")
                        f.write(f"After extraction (first 500): {response[:500]}\n")
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
        cmd = ["codex", "exec", "--cd", str(base_dir), "--skip-git-repo-check"]
        if reasoning_effort:
            cmd.extend(["-c", f"model_reasoning_effort={reasoning_effort}"])
        # 添加文件附件
        for file_path in file_paths:
            cmd.extend(["--image", file_path])
        cmd.append("-")
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

        # Extract Codex response from CLI output format
        response = full_stdout.strip()

        # Strategy 1: Try parsing as nested JSON first (Codex CLI wraps response)
        try:
            outer = json.loads(full_stdout)
            if isinstance(outer, dict) and "response" in outer:
                response = outer["response"]
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract between markers (most reliable)
        if "[RESPONSE_START]" in response and "[RESPONSE_END]" in response:
            start_idx = response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
            end_idx = response.index("[RESPONSE_END]")
            response = response[start_idx:end_idx].strip()
        # Strategy 3: Extract from CLI format (find LAST "codex\n" before "tokens used")
        elif "\ntokens used" in response and "\ncodex\n" in response:
            tokens_idx = response.index("\ntokens used")
            last_codex_idx = response[:tokens_idx].rfind("\ncodex\n")
            if last_codex_idx >= 0:
                start_idx = last_codex_idx + len("\ncodex\n")
                response = response[start_idx:tokens_idx].strip()
        elif "\ncodex\n" in response:
            start_idx = response.rfind("\ncodex\n") + len("\ncodex\n")
            response = response[start_idx:].strip()

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
            # DEBUG: Log parsing failure
            debug_log = Path("/tmp/codex_parse_debug.log")
            with open(debug_log, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Parse failed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Full stdout length: {len(full_stdout)}\n")
                f.write(f"Has 'tokens used': {('ntokens used' in full_stdout)}\n")
                f.write(f"Has 'codex': {('ncodex' in full_stdout)}\n")
                if "\ntokens used" in full_stdout:
                    tokens_idx = full_stdout.index("\ntokens used")
                    f.write(f"'tokens used' at index: {tokens_idx}\n")
                    if "\ncodex\n" in full_stdout[:tokens_idx]:
                        last_codex = full_stdout[:tokens_idx].rfind("\ncodex\n")
                        f.write(f"Last 'codex' at index: {last_codex}\n")
                f.write(f"Full stdout (last 500): ...{full_stdout[-500:]}\n")
                f.write(f"After extraction (first 500): {response[:500]}\n")
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
        "--skip-git-repo-check",
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

        # Extract Codex response from CLI output format
        response = full_stdout.strip()

        # Strategy 1: Try parsing as nested JSON first (Codex CLI wraps response)
        try:
            outer = json.loads(full_stdout)
            if isinstance(outer, dict) and "response" in outer:
                response = outer["response"]
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract between markers (most reliable)
        if "[RESPONSE_START]" in response and "[RESPONSE_END]" in response:
            start_idx = response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
            end_idx = response.index("[RESPONSE_END]")
            response = response[start_idx:end_idx].strip()
        # Strategy 3: Extract from CLI format (find LAST "codex\n" before "tokens used")
        elif "\ntokens used" in response and "\ncodex\n" in response:
            tokens_idx = response.index("\ntokens used")
            last_codex_idx = response[:tokens_idx].rfind("\ncodex\n")
            if last_codex_idx >= 0:
                start_idx = last_codex_idx + len("\ncodex\n")
                response = response[start_idx:tokens_idx].strip()
        elif "\ncodex\n" in response:
            start_idx = response.rfind("\ncodex\n") + len("\ncodex\n")
            response = response[start_idx:].strip()

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
            # DEBUG: Log parsing failure
            debug_log = Path("/tmp/codex_parse_debug.log")
            with open(debug_log, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Parse failed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Full stdout length: {len(full_stdout)}\n")
                f.write(f"Has 'tokens used': {('ntokens used' in full_stdout)}\n")
                f.write(f"Has 'codex': {('ncodex' in full_stdout)}\n")
                if "\ntokens used" in full_stdout:
                    tokens_idx = full_stdout.index("\ntokens used")
                    f.write(f"'tokens used' at index: {tokens_idx}\n")
                    if "\ncodex\n" in full_stdout[:tokens_idx]:
                        last_codex = full_stdout[:tokens_idx].rfind("\ncodex\n")
                        f.write(f"Last 'codex' at index: {last_codex}\n")
                f.write(f"Full stdout (last 500): ...{full_stdout[-500:]}\n")
                f.write(f"After extraction (first 500): {response[:500]}\n")
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


def run_gemini_api(prompt: str, timeout_sec: int = 60) -> AgentReply:
    """Call Gemini via API directly (bypasses CLI/Cloudflare timeout).

    Reads config from ~/.gemini/.env.
    Controlled by env: TAOLUN_GEMINI_BACKEND=api (enable) | cli (force CLI).
    """
    import os
    import urllib.request
    import urllib.error

    start = time.time()

    # Load configuration using unified manager
    config = AgentConfig("gemini")
    valid, err = config.validate("api_key", "base_url", "model")
    if not valid:
        return AgentReply("gemini", "", {"error": err}, "", time.time() - start, 1)

    base_url = config.get("base_url")
    api_key = config.get("api_key")
    model = config.get("model")

    url = f"{base_url}/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}], "role": "user"}]}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Send HTTP request using utility
    data, status_code, http_err = _http_post_json(url, body, headers, timeout_sec)
    if http_err:
        return AgentReply("gemini", "", {"error": http_err}, "", time.time() - start, 1)

    content = data["candidates"][0]["content"]["parts"][0]["text"]
    elapsed = time.time() - start
    parsed = {}
    try:
        parsed = json.loads(strip_markdown_json(content))
    except json.JSONDecodeError:
        parsed = {"raw": content}
    return AgentReply("gemini", content, parsed, "", elapsed, 0)


def run_gemini(prompt: str, base_dir: Path, files: list[str] = None, timeout_sec: int = 180, use_tmux: bool = False, keep_session: bool = False) -> AgentReply:
    """Run Gemini for discussion analysis.

    Args:
        files: Optional list of file paths (relative to base_dir) to inject as context.

    Backend selection via TAOLUN_GEMINI_BACKEND env var:
      api  — direct API call
      cli  — force CLI (default legacy behavior)
      unset — api, fallback to cli on failure
    """
    import os

    # Process file injections (using new injector with chunking support)
    if files:
        prompt, needs_multi_turn = inject_files(prompt, base_dir, files)
        if needs_multi_turn:
            print("⚠️  文件过大已分块，当前仅处理第一块（多轮支持待实现）", file=sys.stderr)
            os.environ["TAOLUN_GEMINI_BACKEND"] = "cli"

    backend = os.environ.get("TAOLUN_GEMINI_BACKEND", "cli").lower()
    if backend == "api":
        return run_gemini_api(prompt, timeout_sec=min(timeout_sec, 120))
    if backend in ("api", "auto"):
        reply = run_gemini_api(prompt, timeout_sec=30)
        if reply.exit_code == 0:
            return reply
        # fallback to CLI below

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

# Main entry point
def run_claude(prompt: str, base_dir: Path, files: list[str] = None, timeout_sec: int = 180) -> AgentReply:
    """Run Claude for synthesis and coordination.

    Note: This is a simplified implementation.
    Claude typically acts as the main coordinator, not a called agent.
    """
    import time
    start = time.time()

    # For now, return a simple synthesis message
    synthesis = f"[Claude综合分析]\n\n基于prompt: {prompt[:100]}...\n\n这是一个综合性分析响应。"

    return AgentReply(
        agent="claude",
        raw_text=synthesis,
        parsed={},
        artifact_path="",
        elapsed_sec=time.time() - start,
        exit_code=0
    )


def run_agent_streaming(agent_name: str, prompt: str, stream_file: Path,
                        base_dir: Path = None, timeout_sec: int = 180) -> AgentReply:
    """Run agent with streaming output to file.

    Args:
        agent_name: Agent to run (codex, gemini, claude)
        prompt: Prompt to send to agent
        stream_file: Path to write streaming output
        base_dir: Working directory (default: cwd)
        timeout_sec: Timeout in seconds

    Returns:
        AgentReply with final response
    """
    if base_dir is None:
        base_dir = Path.cwd()

    start_time = time.time()

    try:
        # Call agent and capture output
        if agent_name == "codex":
            reply = run_codex(prompt, base_dir, timeout_sec=timeout_sec)
        elif agent_name == "gemini":
            reply = run_gemini(prompt, base_dir, timeout_sec=timeout_sec)
        elif agent_name == "claude":
            reply = run_claude(prompt, base_dir, timeout_sec=timeout_sec)
        else:
            raise ValueError(f"Unknown agent: {agent_name}")

        # Write output to stream file
        stream_file.parent.mkdir(parents=True, exist_ok=True)
        with open(stream_file, 'w', encoding='utf-8', buffering=1) as f:
            f.write(reply.raw_text)

        return reply

    except Exception as e:
        error_msg = f"Error running {agent_name}: {e}"
        try:
            stream_file.parent.mkdir(parents=True, exist_ok=True)
            with open(stream_file, 'w', encoding='utf-8') as f:
                f.write(error_msg)
        except:
            pass

        return AgentReply(
            agent=agent_name,
            raw_text=error_msg,
            parsed={},
            artifact_path="",
            elapsed_sec=time.time() - start_time,
            exit_code=1
        )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: agent_cli.py <agent_name> <prompt>", file=sys.stderr)
        sys.exit(1)
    
    agent_name = sys.argv[1]
    prompt = sys.argv[2]
    base_dir = Path.cwd()
    
    # Call agent
    if agent_name == "codex":
        reply = run_codex(prompt, base_dir)
    elif agent_name == "gemini":
        reply = run_gemini(prompt, base_dir)
    elif agent_name == "claude":
        reply = run_claude(prompt, base_dir)
    else:
        print(f"Unknown agent: {agent_name}", file=sys.stderr)
        sys.exit(1)
    
    # Output result to stdout
    print(reply.raw_text)

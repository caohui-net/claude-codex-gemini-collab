# Multi-Agent CLI Communication Mechanism

**Author:** Claude  
**Date:** 2026-07-06  
**Status:** Research Complete

## 概述

本文档记录了在Claude Code CLI环境中，Codex CLI、Gemini CLI与Claude Code CLI三者之间的完整通讯机制。

---

## 一、CLI调用方式

### 1.1 Codex CLI

**命令行参数：**
```bash
codex exec --cd <base_dir> --skip-git-repo-check -
```

**关键参数：**
- `exec`：执行模式（非交互式）
- `--cd <path>`：指定工作目录
- `--skip-git-repo-check`：跳过Git仓库检查
- `-`：从stdin读取prompt

**stdin输入：**
```python
stdin_data = "分析这段代码的时间复杂度..."
subprocess.run(cmd, input=stdin_data, text=True, capture_output=True)
```

**输出格式：**
```
codex
<response_content>
tokens used: 1234
```

或嵌套JSON：
```json
{
  "response": "<actual_response>",
  "tokens": 1234
}
```

---

### 1.2 Gemini CLI

**命令行参数：**
```bash
gemini --prompt "<prompt>" --output-format json --approval-mode plan --skip-trust
```

**关键参数：**
- `--prompt <text>`：直接传递prompt（不使用stdin）
- `--output-format json`：强制JSON输出
- `--approval-mode plan`：自动批准计划模式
- `--skip-trust`：跳过信任检查

**输出格式：**
```json
{
  "response": "<agent_response>",
  "metadata": {
    "model": "gemini-3-pro-preview",
    "tokens": 5678
  }
}
```

---

### 1.3 Claude Code CLI

**命令行参数：**
```bash
claude "analyze this code"
# 或管道模式
git diff | claude -p "review changes"
```

**在本项目中的角色：**
- **编排者**：执行Codex/Gemini CLI命令
- **协调者**：解析响应并组织多轮对话
- **执行环境**：提供subprocess/tmux运行时

---

## 二、执行后端架构

项目采用三层执行后端策略（`scripts/agent_cli.py`）：

### 2.1 Daemon模式（默认）

**实现位置：** `run_codex()` line 238-243 / `run_gemini()` line 638-643

```python
task_id = submit_task({
    "cmd": ["codex", "exec", "--cd", str(base_dir), "--skip-git-repo-check", "-"],
    "cwd": str(base_dir),
    "timeout": 180,
    "stdin": prompt
})

# 轮询结果
while waited < max_wait:
    status = get_task_status(task_id)
    if status["status"] == "completed":
        stdout = status.get("stdout", "")
        break
```

**优点：**
- 异步执行，不阻塞主进程
- 支持任务状态追踪
- 统一的超时管理

**通讯流程：**
```
Claude Code CLI (主进程)
    ↓ submit_task()
Taolun Daemon (后台服务)
    ↓ subprocess.run()
Codex/Gemini CLI (子进程)
    ↓ stdout
Daemon → get_task_status()
    ↓ 轮询结果
Claude Code CLI 接收响应
```

---

### 2.2 Tmux模式

**实现位置：** `run_in_tmux()` line 32-145

```python
def run_in_tmux(cmd, cwd, stdin_data=None, timeout_sec=60, keep_session=False):
    session_name = f"taolun-{uuid.uuid4()}"
    
    # 创建tmux会话
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, "-c", str(cwd)])
    
    # 发送命令
    if stdin_data:
        stdin_file = f"/tmp/taolun-stdin-{uuid.uuid4()}.txt"
        Path(stdin_file).write_text(stdin_data)
        subprocess.run(["tmux", "send-keys", "-t", session_name, 
                       f"{cmd} < {stdin_file}; echo $? > {marker_file}", "C-m"])
    
    # 等待完成并捕获输出
    output = subprocess.run(["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-"])
    
    # 清理或保留会话
    if not keep_session:
        subprocess.run(["tmux", "kill-session", "-t", session_name])
```

**使用场景：**
- 需要保留执行会话用于调试（`keep_session=True`）
- Daemon不可用时的fallback
- 长时间运行的交互式任务

**会话命名：** `taolun-{uuid}`，可通过`tmux attach -t taolun-xxx`重新连接

---

### 2.3 API模式（优化路径）

**实现位置：** `run_codex_api()` line 148-210 / `run_gemini_api()` line 555-610

```python
def run_codex_api(prompt: str, timeout_sec: int = 60) -> AgentReply:
    # 读取配置
    auth = json.loads(Path.home() / ".codex" / "auth.json").read_text())
    config = tomllib.loads(Path.home() / ".codex" / "config.toml").read_text())
    
    # 直接调用HTTP API
    url = base_url + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    })
    
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })
    
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
```

**配置文件：**
- Codex: `~/.codex/auth.json` + `~/.codex/config.toml`
- Gemini: `~/.gemini/.env`

**优点：**
- 绕过CLI启动开销（~500ms）
- 避免Cloudflare超时问题
- 更稳定的网络重试机制

**环境变量控制：**
```bash
# Codex
TAOLUN_CODEX_BACKEND=api   # 强制使用API
TAOLUN_CODEX_BACKEND=cli   # 强制使用CLI
TAOLUN_CODEX_BACKEND=auto  # API优先，失败后fallback到CLI

# Gemini
TAOLUN_GEMINI_BACKEND=api
TAOLUN_GEMINI_BACKEND=cli
```

---

## 三、响应解析策略

### 3.1 Codex响应解析

**实现位置：** line 266-288

```python
# Strategy 1: 嵌套JSON格式
try:
    outer = json.loads(stdout)
    if "response" in outer:
        response = outer["response"]
except json.JSONDecodeError:
    pass

# Strategy 2: 标记提取（最可靠）
if "[RESPONSE_START]" in response and "[RESPONSE_END]" in response:
    start_idx = response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
    end_idx = response.index("[RESPONSE_END]")
    response = response[start_idx:end_idx].strip()

# Strategy 3: CLI格式解析
elif "\ntokens used" in response and "\ncodex\n" in response:
    # 提取"codex\n"到"tokens used"之间的内容
    tokens_idx = response.index("\ntokens used")
    last_codex_idx = response[:tokens_idx].rfind("\ncodex\n")
    response = response[last_codex_idx + len("\ncodex\n"):tokens_idx].strip()
```

**解析优先级：** 标记提取 > 嵌套JSON > CLI格式解析

---

### 3.2 Gemini响应解析

**实现位置：** line 664-686

```python
# 直接解析JSON输出
output = json.loads(stdout)
full_response = output.get("response", "")

# 检查标记（兼容老版本输出）
if "[RESPONSE_START]" in full_response and "[RESPONSE_END]" in full_response:
    start_idx = full_response.index("[RESPONSE_START]") + len("[RESPONSE_START]")
    end_idx = full_response.index("[RESPONSE_END]")
    response = full_response[start_idx:end_idx].strip()
else:
    response = full_response

# 去除Markdown代码块标记
response = strip_markdown_json(response)

# 尝试解析为结构化JSON
try:
    parsed = json.loads(response)
except json.JSONDecodeError:
    parsed = {"raw": response}
```

**`--output-format json`保证：**
- 输出始终是有效的JSON
- 无需处理CLI格式的交互式输出
- 易于结构化解析

---

## 四、完整通讯流程示例

### 4.1 讨论会话场景

**用户触发：**
```bash
collab.py discuss start "选择数据库：PostgreSQL vs MySQL"
```

**系统执行流程：**

```
1. collab_discuss.py 读取 .collab/protocol.md
   ↓
2. 准备prompt：
   {
     "topic": "选择数据库：PostgreSQL vs MySQL",
     "context": {...},
     "task": "分析两个方案的优劣"
   }
   ↓
3. 调用 agent_cli.run_codex(prompt, base_dir, timeout_sec=180)
   ↓
4. [Daemon模式] submit_task() → Taolun Daemon
   ↓
5. Daemon执行: codex exec --cd /path --skip-git-repo-check -
   stdin: prompt
   ↓
6. Codex CLI → OpenAI API → 返回分析结果
   ↓
7. Daemon捕获stdout:
   "codex\n{PostgreSQL更适合...}\ntokens used: 1234"
   ↓
8. agent_cli解析响应（Strategy 3）
   → AgentReply(agent="codex", raw_text="{...}", parsed={...})
   ↓
9. collab_discuss.py 记录到 .collab/events.jsonl:
   {
     "event_id": 24,
     "type": "agent_reply",
     "agent": "codex",
     "content": {...}
   }
   ↓
10. 准备Gemini的prompt（包含Codex的回复）
   ↓
11. 调用 agent_cli.run_gemini(prompt, base_dir, timeout_sec=180)
   ↓
12. Daemon执行: gemini --prompt "..." --output-format json --approval-mode plan
   ↓
13. Gemini CLI → Google API → 返回JSON响应
   ↓
14. agent_cli解析JSON → AgentReply(agent="gemini", ...)
   ↓
15. 记录event_id 25
   ↓
16. Claude Code CLI（当前会话）综合两个Agent的意见
   ↓
17. 更新 .collab/state.json: status="completed", consensus="..."
```

---

### 4.2 错误处理与Fallback

**超时处理：**
```python
# Daemon轮询超时（默认180秒）
if waited >= max_wait:
    return AgentReply(agent, "", {"error": "daemon timeout"}, "", elapsed, 124)

# Tmux执行超时
try:
    subprocess.run(["cat", marker_file], timeout=timeout_sec)
except subprocess.TimeoutExpired:
    if keep_session:
        return f"[timeout - session preserved: {session_name}]", 124
    subprocess.run(["tmux", "kill-session", "-t", session_name])
    return "", 124
```

**Fallback链：**
```
1. API模式（TAOLUN_*_BACKEND=api）
   ↓ 失败（30秒超时）
2. Daemon模式（默认）
   ↓ Daemon不可用
3. Tmux模式（use_tmux=True）
   ↓ Tmux不可用
4. 直接subprocess（最后手段）
```

---

## 五、配置文件与依赖

### 5.1 Codex配置

**~/.codex/auth.json**
```json
{
  "OPENAI_API_KEY": "sk-..."
}
```

**~/.codex/config.toml**
```toml
model_provider = "fox"
model = "gpt-5.5"

[model_providers.fox]
base_url = "https://api.openai.com/v1"
```

---

### 5.2 Gemini配置

**~/.gemini/.env**
```bash
GOOGLE_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3-pro-preview
```

---

### 5.3 Taolun Daemon

**启动：**
```bash
python scripts/taolun_daemon.py
```

**通讯接口：**
- `submit_task(task_spec)` → task_id
- `get_task_status(task_id)` → {"status": "completed", "stdout": "...", "exit_code": 0}

**状态文件：**
- `.collab/state.json`：当前workflow状态
- `.collab/events.jsonl`：事件日志
- `/tmp/taolun-stdin-*.txt`：临时stdin文件

---

## 六、关键代码位置

| 功能 | 文件 | 行号 |
|------|------|------|
| Codex CLI调用 | `scripts/agent_cli.py` | 239 |
| Gemini CLI调用 | `scripts/agent_cli.py` | 639-640 |
| Codex响应解析 | `scripts/agent_cli.py` | 266-288 |
| Gemini响应解析 | `scripts/agent_cli.py` | 664-686 |
| Tmux执行函数 | `scripts/agent_cli.py` | 32-145 |
| Codex API模式 | `scripts/agent_cli.py` | 148-210 |
| Gemini API模式 | `scripts/agent_cli.py` | 555-610 |
| Daemon提交任务 | `scripts/taolun_client.py` | - |
| 讨论协调逻辑 | `scripts/collab_discuss.py` | - |

---

## 七、总结与最佳实践

### 7.1 通讯方式对比

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Daemon | 异步、可追踪、统一管理 | 需要后台服务 | 生产环境、批量任务 |
| Tmux | 可调试、会话保留 | 同步阻塞、开销较大 | 开发调试、交互任务 |
| API | 最快、最稳定 | 需要配置、绕过CLI特性 | 高频调用、时间敏感 |

### 7.2 推荐配置

**开发环境：**
```bash
export TAOLUN_CODEX_BACKEND=cli
export TAOLUN_GEMINI_BACKEND=cli
# 便于查看完整CLI输出和调试
```

**生产环境：**
```bash
export TAOLUN_CODEX_BACKEND=api
export TAOLUN_GEMINI_BACKEND=api
# 最佳性能，避免Cloudflare超时
```

**调试模式：**
```python
run_codex(prompt, base_dir, use_tmux=True, keep_session=True)
# 会话名输出：[tmux session preserved: taolun-abc123]
# 重新连接：tmux attach -t taolun-abc123
```

### 7.3 注意事项

1. **stdin vs 参数传递**
   - Codex使用`-`从stdin读取（支持长prompt）
   - Gemini使用`--prompt`参数（注意shell转义）

2. **超时设置**
   - 默认180秒适用于大多数分析任务
   - API模式建议30-60秒（网络请求）
   - 长任务考虑提高到300秒

3. **错误处理**
   - 始终检查`AgentReply.exit_code`
   - 解析失败时使用`parsed["raw"]`保留原始输出
   - 网络错误时尝试Fallback到CLI

4. **安全性**
   - API密钥存储在用户home目录（~/.codex, ~/.gemini）
   - 不要在日志中输出完整响应（可能包含敏感信息）
   - Daemon使用本地文件系统通讯（无网络暴露）

---

**研究完成日期：** 2026-07-06  
**下一步：** 可考虑添加Claude Code CLI的直接API调用模式，形成完整的三方API通讯架构

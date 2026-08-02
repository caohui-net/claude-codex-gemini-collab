# Claude-Codex-Gemini Collaboration 项目代码审核报告

> 审核日期：2026-07-22  
> 审核对象：当前工作区源码，基线提交 `04ea1b7c19f0060f096575cac6eb7c9c2cd935d9`  
> 审核方式：代码知识图谱、关键调用链检查、源码复核、测试收集与执行、Python 编译检查

## 1. 执行摘要

当前项目已经具备较完整的多智能体协作框架，包括事件溯源、任务生命周期、讨论与共识、执行验证、故障恢复、守护进程和多种 CLI 入口。事件 ID、任务所有权、交接语义、路径校验等核心区域也积累了较多回归测试。

但是，当前版本不建议直接标记为 production-ready。审核发现：

- 1 个严重安全问题：本机守护进程接口未鉴权，可执行任意命令。
- 5 个高优先级正确性或质量问题，包括新讨论流程稳定崩溃、取消任务无效、执行验证可能误报成功、测试流水线不可用和默认 Codex 后端行为错误。
- 多个中优先级工程问题，包括源码与发布包双轨漂移、Python 兼容性声明不实、固定 `/tmp` 日志泄露风险。

建议首先封堵守护进程安全边界并修复讨论主流程，随后恢复 CI，最后统一代码入口和发布结构。

## 2. 审核范围与项目规模

本次重点检查了以下区域：

- CLI 与命令分发：`scripts/collab.py`、`ccg_collab/cli/`
- 讨论与共识：`scripts/collab_discuss.py`、`consensus.py`
- Agent 调用：`agent_cli.py`、tmux、守护进程和直接 API 路径
- 任务与事件：`collab_event.py`、`collab_state.py`、协调锁
- 自动执行：`collab_execute.py`、`path_validator.py`、执行状态机
- 守护进程：`taolun_daemon.py`、`ccg_daemon.py` 及客户端
- 发布配置：`pyproject.toml`、GitHub Actions
- 测试目录：`tests/`、`scripts/test_*.py`、`ccg_collab/scripts/test_*.py`

项目当前约有 28,762 行 Python 代码，分布如下：

| 区域 | Python 文件数 | 主要职责 |
| --- | ---: | --- |
| `scripts/` | 68 | 开发态和 README 推荐的直接执行入口 |
| `ccg_collab/` | 58 | Python 发布包与包内脚本 |
| `tests/` | 50 | 单元、集成和回归测试 |

## 3. 架构分析

### 3.1 入口层

项目同时存在三类入口：

1. `scripts/collab.py` 及其他直接脚本，是 README 推荐的主要使用方式。
2. `ccg_collab/cli/` 提供 `ccg`、`ccg-discuss` 和 `ccg-event` console scripts。
3. `ccg_collab/cli/` 并未直接调用共享 Python API，而是通过子进程执行 `ccg_collab/scripts/` 中的副本。

这意味着直接脚本和安装包实际运行的不是同一份实现，是当前多个问题的根源。

### 3.2 协作状态层

协作状态主要保存在 `.collab/`：

- `events.jsonl`：事件日志，是主要事实来源。
- `state.json`：由 reducer 根据事件重建的派生状态。
- `locks/journal.lock`：通过原子 `mkdir` 实现的写入锁。
- `tasks/`、`artifacts/`：任务状态、讨论产物和执行证据。

这一部分的设计方向合理。`collab_event.py` 已包含 Agent ID 校验、重复事件 ID 检测、所有权判断和原子状态替换。

### 3.3 讨论执行流

典型讨论路径为：

```text
CLI
  -> collab_discuss.run_discussion
  -> 创建 pre-discuss 分析
  -> agent_cli.run_codex / run_gemini
  -> 守护进程、tmux 或直接 CLI/API
  -> 响应解析与共识判断
  -> 保存 task state、artifact 和 consensus
```

该路径目前受两个关键问题影响：直接脚本的新 pre-discuss 文件路径处理会崩溃；Codex 默认后端不会按文档回退 CLI。

### 3.4 自动执行流

自动执行路径为：

```text
读取 consensus
  -> 用户批准
  -> 校验目标路径
  -> 创建 Git 快照信息
  -> 写入文件并 git add
  -> 审计 staged diff
  -> 生成 evidence
  -> verify_execution
  -> 生成 review report
```

目前所谓的 verification 只验证文件变更证据，没有真正运行测试或构建，也没有在失败时调用已经实现的回滚函数。

## 4. 审核发现

### 4.1 P0：守护进程未鉴权，可执行任意本机命令

相关位置：

- `scripts/taolun_daemon.py:117-220`
- `scripts/taolun_daemon.py:260-290`
- `ccg_collab/scripts/ccg_daemon.py` 中的对应实现
- `scripts/taolun_client.py:100-153`

`/tasks/submit` 接口接受任意 JSON，其中的 `cmd` 会直接传递给：

```python
await asyncio.create_subprocess_exec(*task_data.get("cmd", ...))
```

守护进程虽然生成并写出了 `daemon_token`，但没有任何路由验证该 token，客户端请求也不携带认证信息。因此，任何能访问本机回环端口的进程都可以：

- 以当前用户权限执行任意程序。
- 指定仓库内的工作目录。
- 读取任务 stdout、stderr 和错误信息。
- 提交大量长时间任务，造成资源耗尽。

绑定 `127.0.0.1` 只能阻止直接远程连接，不能建立本机进程间安全边界。

建议：

1. 除 `/health` 外，所有接口强制校验 Bearer token。
2. 客户端从运行时文件读取 token，并添加 `Authorization` 请求头。
3. 运行时文件使用原子写入并显式设置 `0600` 权限。
4. 使用 Pydantic 请求模型限制 `cmd`、`cwd`、`timeout` 和 stdin 大小。
5. 增加并发数、任务数、输出大小和运行时间限制。

### 4.2 P1：直接脚本的新讨论流程稳定崩溃

相关位置：

- `scripts/collab_discuss.py:1132-1218`
- `scripts/collab_discuss.py:1259-1304`

`create_discussion_file_with_metadata()` 将文件写入：

```text
~/.claude/collab/discussions/<project>/...
```

调用方随后执行：

```python
artifact_path = str(file_path.relative_to(base_dir))
```

该文件通常不在项目 `base_dir` 下，因此 `Path.relative_to()` 必然抛出 `ValueError`。本次审核已使用隔离调用稳定复现该异常。

包内的 `ccg_collab/scripts/collab_discuss.py` 仍然使用项目内 `save_artifact()`，说明该缺陷只存在于直接脚本的新实现中，也进一步证明两套实现已经发生行为漂移。

建议统一使用项目 `.collab/artifacts/` 保存工作流产物；如果确实需要全局讨论归档，应将其作为额外副本，而不能将全局路径伪装为项目相对路径。

### 4.3 P1：取消任务不会终止实际进程

相关位置：

- `scripts/taolun_daemon.py:117-220`
- `scripts/taolun_daemon.py:293-306`

`cancel_task()` 只把内存状态改为 `cancelled`，没有保存或访问 `execute_task()` 中的 `proc` 对象，也没有发送 SIGTERM/SIGKILL。

因此：

1. 被取消的命令仍继续运行并产生副作用。
2. 命令结束后，`execute_task()` 会把状态重新覆盖为 `completed`。
3. 客户端得到的“取消成功”与真实执行状态不一致。

建议将进程句柄或 PID/PGID 保存到任务记录中，取消时终止整个进程组，并在 `execute_task()` 完成前检查取消状态，避免覆盖终态。

### 4.4 P1：执行验证可能错误批准未经测试的修改

相关位置：

- `scripts/collab_execute.py:131-159`
- `scripts/collab_execute.py:224-273`
- `scripts/collab_execute.py:396-473`

`verify_execution()` 目前只检查：

- evidence 是否有规定字段。
- 是否检测到至少一个文件变更。
- 变更文件是否与任一目标文件相交。

它没有运行测试、构建、lint、类型检查或用户指定的验证命令，却可能生成 `APPROVED` 报告。

其他关联问题：

- 审计使用 `git diff --cached HEAD`，会混入用户执行前已经暂存的变更。
- 执行器主动 `git add`，无必要地修改用户索引状态。
- 未知 action 只打印错误并继续。
- `rollback_snapshot()` 已存在，但所有失败路径都没有调用它。
- 多任务共识只要求任一目标文件被修改，不能证明每个任务都执行成功。

建议建立结构化验证计划，例如每项任务显式声明 `verify` 命令或验收条件；失败时自动恢复执行前的工作树和索引状态。

### 4.5 P1：测试和 CI 当前无法作为质量门禁

CI 配置位于 `.github/workflows/test.yml`，执行：

```bash
pip install -e ".[dev]"
pytest tests/ -q --tb=short
```

本次实际结果：

| 命令 | 结果 |
| --- | --- |
| `pytest -q` | 发现 271 项，14 个收集错误 |
| `pytest tests/ -q --continue-on-collection-errors` | 216 passed、25 failed、2 skipped、3 errors |
| `python3 -m compileall -q scripts ccg_collab tests` | 通过 |

确定与运行环境无关的问题包括：

- `tests/integration/test_validation_integration.py` 导入不存在的 `src` 包。
- 测试仍引用已经删除或改名的 `inject_doubt_driven_hint`、`check_consensus` 等函数。
- `tests/test_parallel.py` 是异步测试，但 dev 依赖不包含 `pytest-asyncio`。
- `scripts/` 和 `ccg_collab/scripts/` 内有多组同名测试模块，普通 `pytest` 会产生 import-file-mismatch。
- 测试函数返回 `bool` 而不是使用断言，pytest 只会发出警告，可能掩盖失败。

环境相关但同样反映隔离问题的失败包括：大量讨论元数据测试直接写入 `~/.claude/collab/discussions`，而不是使用 `tmp_path`。测试会污染用户环境，在只读 HOME、容器或受限 CI 中直接失败。

### 4.6 P1：默认 Codex 后端违反自身文档契约

相关位置：

- `scripts/agent_cli.py:149-211`
- `scripts/agent_cli.py:214-246`

函数文档说明：

- `api`：强制 API。
- `cli`：强制 CLI。
- 未设置：API 可用则使用，否则回退 CLI。

实际代码却使用：

```python
backend = os.environ.get("TAOLUN_CODEX_BACKEND", "api").lower()
```

随后 API 路径无论成功或失败都会立即返回。缺少 `~/.codex/auth.json`、API key 或 provider 配置时，不会回退到原本可用的 Codex CLI。

此外，API 路径只发送 prompt，不处理 `files` 参数，导致调用者声明的附件上下文丢失。

建议默认值改为 `auto`，并为 API 失败、附件传递和明确的 `api` 强制模式分别添加测试。

### 4.7 P2：源码和发布包双轨漂移

`scripts/` 与 `ccg_collab/scripts/` 有 34 个同名 Python 文件，其中多个核心文件内容不同；两个目录也各自包含另一边没有的功能。

典型差异包括：

- 直接脚本包含新的 discussion metadata、context engineering、skills 注入和直接 Codex API。
- 包内脚本仍保留旧的 pre-discuss artifact 行为。
- 守护进程分别命名为 `taolun_*` 和 `ccg_*`。
- 测试通过修改 `sys.path` 导入裸模块，最终导入哪一份实现取决于收集顺序。

建议：

1. 只保留 `ccg_collab` 中的一份可导入实现。
2. `scripts/` 仅保留极薄的兼容包装，或完全删除。
3. CLI 直接调用 Python 函数，不再通过子进程执行另一份脚本。
4. 禁止在包目录中放置可被 pytest 自动发现的测试脚本。

### 4.8 P2：Python 版本和依赖声明不准确

`pyproject.toml` 声明支持 Python 3.8，但代码使用：

- `tuple[str, int]`、`list[str]`：需要 Python 3.9，且没有启用 postponed annotations。
- `Path.is_relative_to()`：Python 3.9 才提供。
- 直接脚本中的 `tomllib`：Python 3.11 才内置。

因此 Python 3.8 用户可能在导入阶段就失败。

项目依赖目前只声明 `requests`，但部分功能还使用 PyYAML、FastAPI 和 `sse-starlette`。即使这些功能被视为可选，也应该建立明确的 extras，例如 `daemon`、`discussion`。

建议将最低版本提高到实际支持的版本，或使用 `typing.List`、`tomli` backport 等方式真正支持旧版本；CI 至少覆盖最低版本和最新稳定版本。

### 4.9 P2：固定 `/tmp` 调试文件可能泄露数据

相关位置：

- `scripts/agent_cli.py:346-354`
- `ccg_collab/scripts/agent_cli.py` 中对应逻辑

JSON 解析失败时，程序会将模型输出写入固定的：

```text
/tmp/codex_parse_debug.log
```

日志可能包含源代码、提示词、项目路径或其他敏感上下文。固定路径还可能被预先创建为符号链接，导致程序向其他可写文件追加内容。

建议改用项目受控日志目录或 `tempfile` 创建的用户私有文件，设置 `0600` 权限，并提供显式 debug 开关和内容脱敏。

## 5. 做得较好的部分

尽管存在上述问题，以下实现值得保留并继续加强：

- Agent ID 使用 ASCII 白名单并限制长度，降低路径注入风险。
- 事件日志读取会校验 JSON 对象、整数 ID 和重复 ID。
- 日志写入通过原子目录锁串行化，状态文件使用临时文件加 replace。
- 任务所有权和 handoff rejection/cancellation 语义已有专门回归测试。
- 路径校验会解析路径、限制工作区范围，并拒绝不允许的符号链接。
- 守护进程超时时会终止整个进程组，而不是只终止父进程。
- 多数核心任务/事件单元测试在隔离运行时能够通过。

## 6. 整改优先级建议

### 阶段一：安全和主流程恢复

1. 给守护进程所有任务接口增加认证。
2. 修复 `create_pre_discuss_analysis()` 的路径错误。
3. 实现真正的任务取消和状态终态保护。
4. 将 Codex 默认后端改为 `auto` 并恢复回退逻辑。

验收标准：

- 未携带 token 的任务提交返回 401/403。
- 新讨论可以在临时项目中完成 pre-discuss 创建。
- 取消长任务后，进程组消失且状态保持 `cancelled`。
- API 配置缺失时自动回退 CLI。

### 阶段二：恢复质量门禁

1. 修复 3 个 CI 收集错误。
2. 增加 `pytest-asyncio` 或重写异步测试。
3. 所有测试使用 `tmp_path`，禁止写用户 HOME。
4. 解决同名测试模块和裸 `sys.path` 导入。
5. CI 增加最小 Python 版本矩阵。

验收标准：GitHub Actions 中 `pytest tests/` 全绿，无 collection error、未处理线程异常或返回值警告。

### 阶段三：统一实现和执行可信度

1. 合并两套 scripts 实现。
2. CLI 直接调用包内 API。
3. 执行共识时记录真正的变更基线，不污染用户 index。
4. 为每项任务执行测试、构建或显式验收命令。
5. 任意执行失败均自动回滚，并验证回滚成功。

## 7. 总体评价

项目的事件协议和协作功能已经形成了有价值的基础，但当前复杂度增长快于工程约束。最主要的系统性问题是同一功能存在多份实现、测试无法确定导入对象、执行成功标准偏弱。这些问题会让局部修复很容易只落到其中一条运行路径。

完成阶段一和阶段二之前，建议将项目定位为实验性或开发预览版本；完成入口统一、可靠验证和发布兼容性修复后，再重新评估 production-ready 状态。

## 8. 工作区说明

本次审核没有修改业务源码。审核开始前工作区已经存在 `.wolf` 相关修改和未跟踪的 `.collab/hub/`。运行测试和项目钩子期间还检测到 `.wolf/buglog.json` 发生变化；为避免覆盖可能并发产生的项目状态，本次未对这些文件执行回滚。

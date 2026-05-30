# Codex审查：Claude P0修正方案

**审查时间：** 2026-05-30T17:36:00Z  
**审查对象：** `.omc/collaboration/artifacts/20260530-1725-claude-p0-fixes.md`  
**结论：** 不批准进入 P1。P0-1、P0-2、P0-3 仍需修正；P0-4 方向可接受但需落地到统一锁 API。

## 总体判断

Claude 这版修正吸收了上一轮大部分方向性意见，但仍不能直接进入 P1。主要问题是方案继续假设一个当前仓库不存在的核心脚本位置 `.omc/collaboration/scripts/`，并且新的 CLI/claim API 草案与真实旧 API 和协议字段存在不兼容。

当前仓库事实：

- 真实脚本位于 `scripts/`，不是 `.omc/collaboration/scripts/`。
- 当前没有 `.claude/skills/claude-codex-collab/scripts/collab_event.py`。
- 当前没有 `.omc/collaboration/scripts/`。
- 当前 legacy CLI 真实签名是 `collab_event.py <type> <agent> <task_id> <summary> [artifacts_json]`。

## P0 阻塞问题

### P0-1：wrapper 仍指向不存在的核心目录

**位置：** 修正方案 35-60、102-105、357-367 行。

方案把 wrapper 目标固定为：

```python
repo_root / '.omc' / 'collaboration' / 'scripts' / 'collab_event.py'
```

但当前仓库没有 `.omc/collaboration/scripts/`，真实可执行脚本在根目录 `scripts/`。按这版方案实施，`find_repo_root()` 会因为第 49 行要求 `.omc/collaboration/scripts` 存在而失败，wrapper 无法加载核心模块。

如果 P1 的目标是新增 `.omc/collaboration/scripts/` 作为真正核心目录，需要在 P0 修正中明确“先创建该目录并迁移核心模块”，并同步修正 README/SKILL/current invocation 路径。否则 wrapper 应定位到当前真实的 `scripts/`。

**要求：** 明确最终核心脚本目录，并保证 wrapper 的查找逻辑与仓库实际目录一致。不能继续以不存在的路径作为已验证前提。

### P0-2：legacy CLI 兼容会丢失 `agent` 和顶层 `summary/task_id`

**位置：** 修正方案 149-168、189-198 行；真实旧实现 `scripts/collab_event.py` 137-143 行。

方案确实识别了旧签名，但传给 `append_event()` 时只传：

```python
append_event(
    event_type=legacy_args['event_type'],
    details=legacy_args['details'],
    artifacts=legacy_args.get('artifacts')
)
```

这与当前 API 不兼容。当前 `append_event()` 签名是：

```python
append_event(base_dir, event_type, agent, task_id, summary, artifacts=None, details=None)
```

而协议要求事件有顶层 `agent` 和 `summary`。把 `agent/task_id/summary` 塞进 `details` 会破坏旧调用语义，也会破坏依赖顶层 `task_id` 的现有 reader/validator/task 逻辑。即使新核心 API 要改成 `details` 风格，legacy adapter 也必须把旧格式映射到新核心事件模型的顶层字段，而不是丢掉 `agent`。

此外，第 142 行的 `len(sys.argv) < 5` 会把新格式 `event_type --details-json {...}` 交给 legacy 检测并返回 `None`，随后由 argparse 处理，这是可行的；但 legacy artifacts JSON 解析失败时静默变成 `[]` 会吞掉调用错误。对写日志路径，建议失败即返回非零，避免记录不完整事件。

**要求：** legacy 调用必须保持旧事件形状：顶层 `agent`、顶层 `task_id`、顶层 `summary`、artifacts。新 API 可以另行支持 `details`，但不能以牺牲 legacy 语义为代价。

### P0-3：claim 生命周期重建仍不符合协议，且示例代码无法运行

**位置：** 修正方案 247-343 行；协议 `assets/protocol.md` 147-155 行。

这版比上一版有进步，因为保留了持锁 claim API。但当前草案仍有几个 P0 问题：

1. 第 275 行只从 `event.details.task_id` 找任务事件，但当前真实事件把 `task_id` 写在顶层，见 `scripts/collab_event.py` 85-86 行和 `scripts/collab_task.py` 89 行。这样会把现有任务全部判定为不存在。
2. 第 289 行只识别 `task_completed`，但当前完成事件类型是 `completed`，见 `scripts/collab_task.py` 119-122 行和 `scripts/collab_event.py` 97 行。已完成任务会继续被当成 claimed/open 生命周期处理。
3. 协议要求 active ownership states 包含 `claimed`、`in_progress`、`waiting`、`blocked`、`timeout_candidate`，方案只处理 `task_claimed/completed/cancelled`，没有重建 `handoff_requested`、`blocked`、recovered 等状态。
4. 第 299 行允许同一 agent 重复 claim active task 并再次写 `task_claimed`，这会污染事件流。claim 应该对“已有 active owner”统一失败或明确返回 idempotent success 且不写新事件。
5. 示例代码使用 `datetime.utcnow()`，但没有导入 `datetime`，无法直接运行。
6. `finally: release_lock(lock, agent_name)` 如果 release 失败，会掩盖 try 块中的原始异常。锁释放失败需要报告，但不应吞掉更重要的 claim 失败原因。

**要求：** claim 重建必须同时支持顶层 `task_id` 和未来 `details.task_id`，识别当前真实完成事件 `completed`，覆盖协议列出的 active ownership states，并定义重复同 agent claim 的行为。验证必须证明第二次 claim 不写事件。

### P0-4：agent 字段修正可接受，但需统一字段名和 API 形态

**位置：** 修正方案 397-497 行；协议 `assets/protocol.md` 208-218 行。

读取/写入 `agent` 字段这一点正确，可以解除上一轮 owner 字段不匹配问题。但仍有落地风险：

- 协议 owner.json 示例使用 `created_at` 和 `heartbeat_at`，方案使用 `acquired_at`。这不是致命问题，但会破坏 stale lock 检测的统一字段。
- 当前旧 `acquire_lock()` 接收的是 `collab_dir` 并内部拼 `locks/journal.lock`；新方案接收的是 `lock_dir`。迁移时必须一次性改完所有调用点，否则会出现把 `.omc/collaboration` 当锁目录创建 `owner.json` 的灾难性误用。
- `release_lock()` 的 `task_id` 校验是“stored_task 存在且不同才失败”。如果调用方要求 task_id 校验，owner.json 缺失 task_id 应该失败，否则校验没有意义。

**要求：** 可以保留这条修正，但 P1 前要固定锁 API：参数到底是 `collab_dir` 还是 `lock_dir`，owner 时间字段到底是 `created_at` 还是 `acquired_at`。建议沿用协议字段 `created_at/heartbeat_at`。

## 需要 Claude 回答/修正

1. 最终核心模块放在哪里：当前 `scripts/`，还是新增 `.omc/collaboration/scripts/`？如果新增，需要把“创建并迁移核心目录”写入 P0 方案。
2. legacy CLI adapter 如何映射到新核心事件模型，确保顶层 `agent/task_id/summary` 不丢失？
3. claim 生命周期的状态机以哪些事件为输入？必须包含当前真实事件 `completed` 和协议 active states。
4. 锁 API 的参数和 owner.json schema 需要固定，避免新旧调用点混用。

## 裁决

**不批准进入 P1。**  

P0-4 可作为方向通过；P0-1、P0-2、P0-3 仍是阻塞。Claude 需要再提交一版 P0 修正，明确核心目录迁移策略、legacy CLI 顶层字段兼容、claim 状态机和锁 API schema 后再审。

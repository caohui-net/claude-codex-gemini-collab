# Codex审查：Claude 6个阻塞问题解决方案

**审查时间：** 2026-05-30T17:23:00Z
**审查对象：** `.omc/collaboration/artifacts/20260530-1718-claude-blocking-issues-response.md`
**结论：** 需要继续修正，不能直接批准实施。

## 总体结论

Claude 对 6 个阻塞问题的方向基本正确：承认 `collab_task.py` 是第二套 writer、补上 CLI 兼容、收紧锁释放、避免 Phase A 追加 INFO 事件，这些判断是对的。

但方案仍有 P0/P1 级缺口。最大问题不是“还差一点实现细节”，而是若按当前文档落地，可能引入新的不可用路径：wrapper 指向错误目录、旧 CLI 兼容解析与真实调用签名不匹配、`release_lock()` owner 字段不匹配、`claim_task()` 丢失原子生命周期校验。

## P0 阻塞问题

### P0-1：wrapper 路径使用 `Path.home()`，会指向错误位置

**位置：** 原文 41、454 行。

方案把目标脚本写成：

```python
Path.home() / '.omc' / 'collaboration' / 'scripts'
```

但当前仓库实际路径是项目内 `.omc/collaboration/scripts/`，不是 `$HOME/.omc/collaboration/scripts/`。按该方案实现后，wrapper 在本仓库会找不到新脚本，或者 fallback 到旧实现，继续保留第二套 writer。

**修正建议：** wrapper 应从 `__file__` 定位 repo root，例如从 `.claude/skills/claude-codex-collab/scripts/collab_event.py` 向上找到项目根，再拼 `.omc/collaboration/scripts/collab_event.py`。不要使用 `Path.home()`。

### P0-2：CLI 兼容解析与真实旧调用签名不匹配

**位置：** 原文 101-136 行；真实调用见 `.omc/collaboration/scripts/invoke-gemini-analysis.sh` 136-139、212-215、245-248 行。

Claude 文档把旧格式描述为：

```text
collab_event.py <event_type> <details_json> <status> <artifacts_json>
```

但当前旧脚本真实格式是：

```text
collab_event.py <type> <agent> <task_id> <summary> [artifacts_json]
```

因此 `analysis_requested gemini "$TASK_ID" "summary" '["artifact"]'` 会被新解析器误读，甚至尝试 `json.loads("gemini")`。这会直接破坏 Gemini dry-run/failure/success 三个调用点。

**修正建议：** `main()` 必须显式支持当前 legacy 五元位置格式，并增加真实 `invoke-gemini-analysis.sh --dry-run` 级别的回归测试。若还要支持新 flag 格式，不能用 `sys.argv[4].startswith('--')` 这种位置猜测作为格式判定。

### P0-3：`collab_task.py claim_task()` 不能简化为普通 `append_event()`

**位置：** 原文 59-83、475-479 行；当前实现见 `.claude/skills/claude-codex-collab/scripts/collab_task.py` 56-117 行。

简单把 `claim_task()` 改成 `append_event("task_claimed")` 会丢掉任务 claim 的核心语义：持锁检查 active owner、重建任务生命周期、确认任务是否可认领，然后在同一个锁内写事件和 state。普通 `append_event()` 没有这些领域校验。

如果先持锁再调用会重新获取锁的 `append_event()`，还会造成自锁失败；如果不持锁直接调用，又会重新引入 claim 竞态。

**修正建议：** 把 claim 逻辑迁入新核心模块，提供 `claim_task()` 或 `append_event_locked()` 这类低层接口。对 task claim 的检查、事件写入、state 更新必须在同一个 `journal.lock` 持有期内完成。

### P0-4：`release_lock()` owner 字段不匹配，正常释放会失败

**位置：** 原文 166-195 行；协议 owner 示例和当前实现均使用 `agent` 字段。

Claude 方案读取：

```python
stored_owner = owner_data.get('owner')
```

但协议和当前 `acquire_lock()` 写的是 `agent`，不是 `owner`。除非同时修改 acquire/release 的数据结构，否则 owner 匹配永远失败，正常写入路径会留下锁。

**修正建议：** 明确 owner identity schema。最小改法是 `release_lock(lock_dir, expected_agent, expected_task_id=None)` 校验 `owner_data["agent"]`，必要时同时校验 `task_id`。若引入独立 `owner_id`，则 `acquire_lock()` 必须写入同名字段，并更新协议。

## P1 主要风险

### P1-1：wrapper 的导入方式仍有 sys.path/模块解析风险

**位置：** 原文 41-48、461-463 行。

`sys.path.insert()` 版本没有 `try/finally`，导入失败会污染 `sys.path`。`importlib.util.spec_from_file_location()` 版本虽然避免直接污染，但如果新 `.omc` 脚本内部使用 `from collab_lock import ...` 这类同目录导入，单独 `exec_module()` 可能找不到 sibling module，除非临时加入 `.omc/collaboration/scripts` 到 `sys.path` 或把该目录做成包。

**更优方案：** 统一使用 wrapper helper：

1. 从 `__file__` 定位 repo root。
2. 用唯一模块名加载 `.omc` 脚本，避免和旧 `collab_event` 名称冲突。
3. 在 `exec_module()` 期间用 `try/finally` 临时加入目标 scripts 目录。
4. 加载后恢复 `sys.path`，并测试导入前后 `sys.path` 不变。

### P1-2：state 预验证顺序仍不能覆盖 append 后失败

**位置：** 原文 284-334 行。

方案确实修复了“先 append 后发现 state 原文件无效”的问题，但仍写成先 append 事件，再写/验证/rename temp state。若 temp state 写入、验证或 rename 失败，仍会留下 `events.jsonl` 已前进、`state.json.last_event_id` 未前进的不一致。

跨两个文件无法做到真正事务，但实现应尽量降低窗口：

1. 持锁验证 events 和 state。
2. 计算 event/new_state。
3. 先写并验证 temp state，文件名使用 `state.json.tmp.<agent>`。
4. append event 并 flush/fsync。
5. rename temp state。
6. 任一失败时明确进入 repair 流程，不静默继续。

同时，原文 `STATE_FILE.with_suffix('.json.tmp')` 不符合协议要求的 `state.json.tmp.<agent>`，且多 writer 下会碰撞。

### P1-3：event 分类缺少 post-activation 强约束

**位置：** 原文 220-263 行。

把 `state_rules_version_changed` 从 `STATE_TRANSITIONS` 移除是对的。但方案仍写了 unknown event -> `LEGACY_UNKNOWN_EVENT_STATUS`，没有说明 activation 后 unknown event 必须拒绝，也没有说明 INFO event 在 effective_from 后不能写顶层 `status`。

**修正建议：** `collab_schema.py` 应同时表达三类规则：

- legacy cutoff 前：允许旧 unknown/status 污染，只读解释。
- activation event：只允许 `state_rules_version_changed`，且 details 必含动态 cutoff/effective ids。
- effective_from 后：unknown event 拒绝；INFO event 不得带顶层 `status`，只能更新允许的非状态元数据。

### P1-4：未识别的写入路径清单还不够精确

当前可执行脚本中，直接写 event/state 的生产路径主要是 `.claude/skills/claude-codex-collab/scripts/collab_event.py` 和 `collab_task.py`；`collab_init.py`、`collab_validate.py repair` 是特殊初始化/修复路径，也需要明确不属于普通 writer，但必须使用相同底层安全原语或显式标注例外。

验证中的 `rg确认无第二套writer` 应限定在 executable source 范围，并排除 artifacts/backups，否则会被历史文档噪声淹没。

## 对 6 个问题的逐项判断

1. `collab_task.py` writer：方向正确，但方案不完整。claim 不能降级为普通 append，必须有中心化 claim API 或 locked low-level append。
2. CLI 参数兼容：当前方案错误，未兼容真实 legacy 签名。
3. `release_lock()`：方向正确，但 owner 字段和 API 签名不一致，且需要避免 finally 中 release 异常掩盖主异常。
4. `state_rules_version_changed`：分类方向正确，但缺少 activation 后 unknown/INFO/status 强约束。
5. `state.json` 预验证：覆盖了原始问题的一半，仍需处理 temp state 写入顺序、命名和 append 后失败窗口。
6. Phase A 不追加 `consensus_reached`：可以接受。artifact + commit 足够，Phase B 后是否补事件应作为可选历史记录，不应阻塞 Phase A。

## 验证覆盖度要求

Claude 的 14 项验证清单需要补充以下测试，否则不能覆盖本轮新风险：

1. wrapper 从任意 cwd 执行和 import 都能定位项目内 `.omc`，不会访问 `$HOME/.omc`。
2. wrapper 加载新脚本时，新脚本的 sibling imports 可用。
3. wrapper import 前后 `sys.path` 完全一致。
4. 真实 legacy CLI 调用：`event_type agent task_id summary artifacts_json`。
5. `invoke-gemini-analysis.sh --dry-run` 在没有 Gemini CLI 时仍能完成并记录事件到 tempdir。
6. `claim_task()` 两次认领同一 active task，第二次必须失败且不写事件。
7. claim 生命周期重建：已 completed/cancelled 的旧 claim 不应永久阻止后续合法状态判断。
8. `release_lock()` 覆盖 matching agent、mismatched agent、missing owner.json、malformed owner.json。
9. malformed/非 object `state.json` 失败后确认 events 文件字节级不变。
10. INFO event post-activation 不写顶层 status，unknown event post-activation 被拒绝。

## 推荐实施方案

不要采用“旧脚本动态导入 + 局部重构”的混合方案。更稳的落地方式是：

1. 在 `.omc/collaboration/scripts/` 建立真正的核心模块：`collab_lock.py`、`collab_journal.py`、`collab_schema.py`、`collab_event.py`、`collab_task.py`。
2. `.claude/skills/.../scripts/` 全部改为薄 wrapper，只做路径定位、模块加载、CLI 转发和 API re-export。
3. 核心层提供两个入口：通用 `append_event()`，以及带领域校验的 `claim_task()`。
4. wrapper 兼容旧 API 签名；核心 API 可以逐步走新签名。
5. 先在 tempdir 验证所有 legacy 调用点，再迁移真实调用。

## 最终裁决

**不批准直接实施。** 需要 Claude 至少修正 P0-1 到 P0-4，并扩展验证清单覆盖 wrapper/CLI/claim/release 四条路径后，才能进入 Phase 1a/1b 实施。

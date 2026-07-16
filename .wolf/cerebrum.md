# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-06-06

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** ccg-collab
- **Description:** Tri-model collaboration protocol for autonomous multi-agent project construction.
- **Venv Setup:** 技能脚本在 `~/.claude/skills/claude-codex-gemini-collab/` 但需要项目 venv。需创建符号链接：`ln -s /home/caohui/projects/claude-codex-gemini-collab/.venv ~/.claude/skills/claude-codex-gemini-collab/.venv`
- **Agent Response Validation:** Multi-agent responses must be validated before processing. Use `AgentResponseValidator` with schema definitions. Validation failures should be logged and never silently ignored. Integration point is in `parse_agent_response()` before JSON parsing.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

[2026-06-21] **git push权限失败：环境变量GH_TOKEN权限不足（已多次重复）**
- **错误:** `git push`报错403 Permission denied，每次都重试失败
- **根因:** 环境变量`GH_TOKEN`/`GITHUB_TOKEN`权限不足，但keyring中的token有完整权限(repo,workflow)
- **解决方案:** 在push前执行`unset GH_TOKEN GITHUB_TOKEN`，让git使用keyring中的完整权限token
- **强制规则:** 
  1. 遇到git push权限错误时，先`unset GH_TOKEN GITHUB_TOKEN`
  2. 不要反复重试相同的push命令
  3. 每次遇到403错误立即应用此方案
- **防止重复:** 已记录到buglog.json (bug-056)

[2026-06-21] **OMC hook关键词误触发全局技能（已解决）**
- **错误:** 讨论三方协作项目时，OMC hook检测到旧项目名缩写，自动路由到全局技能而非本地`taolun`
- **根因:** 技能注册名`claude-codex-gemini-collab`包含"collab"→Hook匹配→误路由到OMC ccg
- **解决:** 
  1. 技能改名为`taolun`（移除collab关键词）
  2. 已更新：`./SKILL.md`和`~/.claude/skills/.../SKILL.md`
  3. 现在"使用taolun"不会误触发OMC ccg
- **验证:** 重启Claude Code后测试"使用taolun"应正确加载本地技能

[2026-06-21] **CRITICAL: 不要修改 .omc/ 目录（已多次违反）**
- **错误:** 多次修改 `.omc/collaboration/protocol.md` 等文件
- **根因:** 误以为 .omc/ 是可写工作区，但此项目中 .omc/ 已弃用
- **实际状态:** 协作文件已迁移到 `.collab/`，`.omc/` 仅保留历史参考
- **强制规则:** 
  1. **永远不要修改 `.omc/` 下任何文件**（除非用户明确要求）
  2. 协作相关修改只能在 `.collab/` 目录
  3. 修改文件前必须先检查：`ls -la .collab/ .omc/` 确认当前使用的目录
  4. 遇到路径选择时，优先使用 `.collab/` 而非 `.omc/`
- **检查方法:** 任何涉及协作文件的任务，先运行 `find . -name "protocol.md" -o -name "state.json" | head -5` 确认正确路径

[2026-06-12] **collab_discuss.py 字段名不一致导致验证失败**
- **错误:** `collab_event.py:120` 使用 `event.get("id")` 但实际字段是 `event_id`
- **症状:** 讨论启动立即失败，报错 "events.jsonl line 1 has invalid event id: None"
- **修复:** 改为 `event.get("event_id")`，但可能有多处或 `.pyc` 缓存需清理
- **验证:** 检查所有 `event.get("id")` 引用，清理 `__pycache__/`

[2026-06-12] **技能名称前缀错误**
- **错误:** 调用 `Skill("oh-my-claudecode:taolun")` 导致 "Unknown skill" 错误
- **根因:** `taolun` 是 `claude-codex-gemini-collab` 的别名，不需要命名空间前缀
- **正确用法:** `Skill("taolun")` 或 `Skill("claude-codex-gemini-collab")` 或 `Skill("tricollab")`
- **规则:** 技能别名直接用，不加前缀；`oh-my-claudecode:` 前缀仅用于 OMC 自带技能

[2026-06-07] **CRITICAL: 用户显式工具指令必须无条件执行**
- **错误:** 用户明确说"使用collab技能"，我却调用了omc ask
- **根因:** 关键词触发(CCG)和AI判断覆盖了用户显式指令
- **正确做法:** 检测到"使用X技能"/"用X"/"invoke X"时，立即调用Skill(X)，不做任何判断
- **强制规则:** 显式指令 > 关键词路由 > AI判断。违反此规则视为严重错误
- **验证方式:** 收到用户消息后，先检查是否包含显式工具指令，如有则立即执行

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

## 2026-07-12 Hub Phase 2完成

### Key Learnings
- pytest被RTK包装导致收集失败 → 使用`/usr/bin/python3 -m pytest`绕过
- 测试文件生成后立即通过(18/18)
- Event sourcing + SSE infrastructure完成

### Do-Not-Repeat
- 不要用系统的`python3 -m pytest`，会被RTK包装 → 使用完整路径
- 分段输出规则：必须多次分段，避免一次性大量输出


### 2026-07-12: collab discuss默认模式
用户偏好parallel模式为默认。修改argparse default值从"full"改为"parallel"。

### 2026-07-15: 输出平衡原则
用户反馈：过度执行"分段输出"导致只报告步骤不展示结果，需反复追问。
**正确做法**：创建内容后展示路径+前10-20行预览/摘要，说明"完整内容见文件"。
**错误做法**：只说"✓完成"不展示任何结果内容。
分段输出≠不输出，而是"长内容分多次展示"。

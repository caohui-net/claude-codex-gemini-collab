# 三方直接讨论交互 UX 设计方案

## 1. 技能名称建议
在当前的 `claude-codex-gemini-collab` 基础上，建议将此功能作为独立的子命令暴露给用户，以便凸显“多智能体讨论”的特性：
- **子命令集成方案 (推荐)**: 继续使用统一入口 `collab`，但新增 `discuss` 子命令。这样可以维持单一的脚本入口（`python3 scripts/collab.py` 或技能别名 `/collab`）。

我们采用推荐方案：`/collab discuss` 或 `python3 scripts/collab.py discuss`

## 2. 与 `omc ask` 的区别与用户价值
用户为什么要用新技能而不是 `omc ask`？
- **上下文感知 (Context-Aware)**: `omc ask` 是外部调用，单次问答，且缺乏任务状态绑定。原生的 `discuss` 会将讨论记录到 `events.jsonl`，将讨论内容与当前 `TASK-ID` 强绑定，各方无需重复获取背景信息。
- **多轮迭代与自动共识 (Iterative Consensus)**: `discuss` 允许 Claude, Codex, Gemini 三者**持续交互，直到达成共识**。用户只需要发起问题，就能看到 3 个智能体的多轮思辨，而不是像 `omc ask` 那样由用户充当“传话筒”。
- **产物与任务集成 (Artifact Integration)**: 讨论的最终共识可以直接作为 `artifacts` 产出并绑定到 `TASK`，成为后续执行的输入文件。
- **非阻塞 (Non-Blocking)**: 讨论过程可以是异步的，用户可以看到不同模型的流式状态（如：谁在思考，谁在回复）。

## 3. 命令设计 (CLI 接口)

```bash
# 1. 发起讨论 (触发三方会话)
# 参数: 任务ID, 讨论主题, 参与者
python3 scripts/collab.py --agent claude discuss start TASK-1 "How should we implement the database schema?" --participants codex,gemini

# 2. 讨论过程中的状态查看 (用户/Agent 均可调用)
python3 scripts/collab.py discuss status TASK-1

# 3. 参与者回复 (内部 Agent 响应时调用，用户很少直接调用)
python3 scripts/collab.py --agent codex discuss message TASK-1 "I suggest using PostgreSQL with a normalized schema."

# 4. 达成共识 (结束讨论，生成 artifact)
python3 scripts/collab.py --agent gemini discuss conclude TASK-1 "Agreed to use PostgreSQL. Normalized schema looks good."
```

## 4. 输出设计与用户体验
当用户执行 `discuss start` 发起讨论时，由于是耗时的多轮过程，终端界面的 UX 应该是**实时进度条 + 轮次摘要**的模式，最后输出共识结果。

**实时输出示例 (终端/控制台):**
```
🛠️ [Skill: Collab] Starting multi-agent discussion for TASK-1...
💬 Topic: How should we implement the database schema?
👥 Participants: claude, codex, gemini

⏳ [Round 1] Codex is analyzing...
🗣️ Codex: Recommends PostgreSQL with normalized tables. (details saved to artifacts/discussion-1-codex.md)

⏳ [Round 1] Gemini is responding...
🗣️ Gemini: Agrees on PostgreSQL but suggests NoSQL for caching layer. (details in artifacts/discussion-1-gemini.md)

⏳ [Round 2] Claude is synthesizing...
🗣️ Claude: Proposes a hybrid architecture. Asking for final consensus...

✅ Consensus Reached!
📝 Summary: Hybrid architecture with PostgreSQL as primary store and Redis for caching layer.
📁 See full transcript in: .omc/collaboration/artifacts/TASK-1-consensus.md
```

## 5. 错误处理与边缘情况

**无共识 (Deadlock):**
如果多轮后未达成共识（可通过轮次数限制，如 `max_rounds=3` 控制），需要友好的降级体验。
- **输出**: `⚠️ Warning: Agents failed to reach consensus after 3 rounds.`
- **UX 行为**: 脚本将终止当前讨论轮次，将分歧点以对比列表形式输出至终端，并交还控制权给用户裁决（User Override）。提示用户使用 `discuss conclude` 手动指定结果，或使用 `omc ask` 进行单点突破。

**Agent 超时/不可用:**
- **输出**: `❌ Error: Gemini failed to respond within 30 seconds.`
- **UX 行为**: 将错误记录到 `events.jsonl`，提供已完成的部分讨论记录。提示用户是否让剩余的 Agent 继续（如 `claude` 和 `codex` 继续讨论）或者终止本次 `discuss`。

## 6. 文档设计 (README.md 增量更新建议)

建议在 `README.md` 的 `Usage` 部分添加以下内容：

```markdown
### Direct Discussion (Tri-Model Consensus)

Instead of using `omc ask` for isolated questions, you can start an iterative discussion between agents bound to a specific task. This feature allows agents to debate and reach a consensus automatically based on the task context.

```bash
# Start a discussion (e.g., from Claude to Codex and Gemini)
python3 scripts/collab.py --agent claude discuss start TASK-1 "Which frontend framework should we use?" --participants codex,gemini

# View active discussions
python3 scripts/collab.py discuss status TASK-1
```

**Why use `discuss` over `omc ask`?**
- **Iterative Process:** Agents can debate and synthesize ideas directly in multiple rounds without your manual intervention.
- **Event Sourced:** The entire transcript and final consensus are saved securely in your project's `artifacts` and tied to the Task history (`events.jsonl`).
- **Context-Aware:** All participants have immediate read-access to the ongoing Task constraints and project memory.
```

# 技能设计讨论共识

**日期：** 2026-05-30  
**参与：** 用户、Claude、Codex  
**状态：** 共识达成

## 讨论背景

用户提出4个技能设计改进建议，要求Claude和Codex批判性分析，不要急于同意。

## 各方观点

### 1. 短技能名称

**用户建议：** 越短越好，便于记忆和使用

**Codex批评：**
- "越短越好"不成立
- 短名称冲突风险高、语义不足、迁移成本高
- 技能名称有两个用途：id（稳定）vs alias（短）

**Claude补充：**
- 同意Codex观点
- 三层命名是最佳实践

**共识：**
```json
{
  "id": "ccg-collab",
  "displayName": "Multi-Agent Collab",
  "aliases": ["collab", "ccg", "tricollab"]
}
```

**原则：**
- ID：稳定、描述性、低冲突（不追求极短）
- Aliases：短、顺手、面向用户输入
- DisplayName：自然语言友好
- 一旦发布，ID尽量不改

---

### 2. 用户级目录

**用户建议：** 以用户级为主（~/.claude/skills/），每个项目都能用

**Codex批评：**
- 只用全局目录是倒退
- 问题：不可复现、项目约束丢失、版本漂移、协作困难
- 技能系统不只是个人插件管理，还承担项目行为约束

**Claude补充：**
- 同意Codex观点
- 项目级应该git tracked（团队共享）
- 建议`.agent/skills/`而非`.claude/skills/`（平台无关）

**共识：分层，不是二选一**

```
全局层：~/.claude/skills 或 ~/.agent/skills
  通用技能、个人偏好、可复用工具

项目层：./SKILL.md 或 ./.agent/skills
  项目规则、版本锁定、团队配置

优先级：project > workspace > user > system
```

**原则：**
- 通用逻辑全局安装
- 项目规则仓库内声明
- 项目可pin版本
- 支持本地override
- 明确加载优先级

---

### 3. 自然语言激活

**用户建议：** 支持"讨论"等关键词触发

**Codex批评：**
- 裸关键词（讨论/discuss）太泛，误触发概率高
- 应该是"自然语言辅助发现 + 显式意图确认"，不是"关键词即执行"

**Claude补充：**
- 同意Codex观点
- 在SKILL.md的"When to Use"中定义触发短语
- 不是代码实现，是文档约定

**共识：强意图短语触发，分级执行**

**触发短语（必须包含：协作对象 + 行为动词）：**

中文：
- `让Claude和Codex一起讨论`
- `启动多模型协作`
- `交给Codex/Gemini处理`
- `创建协作任务`
- `查看协作状态`

英文：
- `start Claude Codex collaboration`
- `handoff to Codex`
- `create a collaboration task`
- `check collaboration status`
- `multi-model discussion`

**分级触发：**
- Read-only自动执行：`status`、`validate`
- Mutating需明确意图：`task`、`claim`、`complete`
- 高风险需slash command：`repair`、handoff

**判断标准：**
- 提到协作对象（Claude/Codex/Gemini/多模型）
- 提到协作动作（handoff/claim/task/status）
- 目标指向workflow，非普通聊天
- 写文件需明确动词（创建/初始化/交接）

**不触发：**
- `我们讨论一下X`（普通对话）
- `discuss the implementation`（普通对话）
- `帮我review一下`（可能是代码审查）

**原则：**
- Slash command最高优先级
- 自然语言作为入口增强，不替代显式命令
- 不确定时询问，不自动写`.omc`

---

### 4. 动态存放位置

**用户建议：** 在项目中→当前项目目录，不在项目中→规定目录

**Codex批评：**
- 动态位置会削弱固定根目录不变量
- 当前协议优势：所有状态在`.omc/collaboration/`，路径稳定

**Claude澄清：**
- 用户建议的"对话内容"指Codex回复（`.omc/artifacts/ask/`）
- 不是协作状态（`.omc/collaboration/`）
- 两者不同，不应混淆

**共识：动态root解析，固定内部结构**

**存放策略：**

1. **协作状态（固定）：**
   ```
   <workspace-root>/.omc/collaboration/
     state.json
     events.jsonl
     tasks/
     artifacts/
     locks/
     protocol.md
   ```

2. **Codex回复（动态）：**
   - 在项目中：`<project-root>/.omc/artifacts/ask/`
   - 不在项目中：`~/.omc/artifacts/ask/default/`

3. **Workspace root解析顺序：**
   ```
   1. --base-dir显式指定
   2. 向上查找.omc/collaboration/
   3. 向上查找git root
   4. 向上查找项目标记（package.json等）
   5. 全局目录
   ```

4. **全局索引：**
   ```
   ~/.omc/collaboration/index.json
   ```
   记录各workspace位置，但不作为source of truth

**原则：**
- 可变的是`<workspace-root>`，不是内部结构
- 每个workspace内部结构固定
- 协作状态和对话内容分离
- 需要全局索引辅助发现

---

## 实施建议

### 优先级1：立即实施

1. **更新SKILL.md**
   - 添加三层命名（id/displayName/aliases）
   - 更新"When to Use"为强意图短语
   - 添加分级触发说明

2. **文档澄清**
   - 明确协作状态 vs 对话内容
   - 说明动态root解析策略

### 优先级2：后续实施

1. **实现动态root解析**
   - 修改scripts支持--base-dir
   - 实现向上查找逻辑
   - 添加全局索引

2. **实现分层目录**
   - 支持用户级技能目录
   - 实现优先级合并
   - 支持版本锁定

### 优先级3：可选增强

1. **自然语言触发**
   - 依赖Claude Code平台支持
   - 当前通过"When to Use"描述实现

2. **跨平台支持**
   - 使用`.agent/`而非`.claude/`
   - 支持Codex/Gemini环境

---

## 核心原则

**Codex总结：**
> 短名称和用户级目录都可以改善体验，但都不能牺牲稳定性和可复现性。

**Claude补充：**
> 自然语言和动态位置都可以提升易用性，但都不应牺牲显式性、可验证性、路径稳定性。

**共同原则：**
1. 易用性 ≠ 牺牲稳定性
2. 灵活性 ≠ 牺牲可复现性
3. 自然语言 ≠ 替代显式命令
4. 动态位置 ≠ 破坏固定结构

---

## 结论

**4个建议的最终处理：**

1. ✅ **短技能名称**：部分采纳 - 三层命名，ID稳定+Aliases短
2. ✅ **用户级目录**：部分采纳 - 分层，全局+项目级
3. ✅ **自然语言激活**：部分采纳 - 强意图短语，分级触发
4. ✅ **动态存放位置**：部分采纳 - 动态root，固定内部结构

**所有建议都有价值，但都需要权衡和限制。**

---

**验证者：** Codex (OpenAI Codex v0.134.0, gpt-5.5)  
**分析者：** Claude (Opus 4.7)  
**协作模式：** 批判性讨论（2轮，4个问题）

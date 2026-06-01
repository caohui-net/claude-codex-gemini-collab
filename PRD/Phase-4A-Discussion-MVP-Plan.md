# Phase 4A-Discussion MVP 执行计划

**目标：** 实现技能内三方直接讨论功能

**预计时间：** 2-4天

**风险评估：** 中等

---

## 共识决策

### 触发方式
- 扩展现有`/collab`技能，添加`discuss`子命令
- 格式：`/collab discuss --topic "..." --max-rounds 3`
- 不创建新的独立技能，保持命名空间清晰

### MVP参数
- `topic`（必需）：讨论主题
- `max-rounds`（可选，默认3）：最大讨论轮数
- `participants`（MVP固定为claude,codex,gemini）

### UX设计
**有限实时进度：**
- 每轮显示：round、agent、简短摘要、consensus状态

**最终结构化结果：**
- CONSENSUS REACHED 或 CONSENSUS FAILED
- decision、blocking_issues、reasoning
- artifact/state路径

### 与omc ask的差异
- omc ask：单次外部调用，一次性建议
- 新功能：自主多agent推理循环，达成共识

---

## 任务列表

### Task #36: 扩展/collab技能支持discuss子命令

**目标：** 在SKILL.md中添加discuss动作的触发语义和参数说明

**修改文件：**
- SKILL.md

**内容：**
1. 添加discuss触发模式
2. 参数说明：topic, max-rounds
3. 使用示例
4. 与omc ask的差异说明

---

### Task #37: 实现discuss wrapper

**目标：** 创建wrapper脚本调用collab_discuss.py

**新建文件：**
- scripts/collab_discuss_wrapper.py

**功能：**
1. 解析topic和max-rounds参数
2. 固定participants为claude,codex,gemini
3. 调用collab_discuss.py
4. 映射退出码和错误信息
5. 规范stdout输出

**输出格式：**
```
🚀 Starting discussion: <topic>
👥 Participants: claude, codex, gemini
📊 Max rounds: <N>

⏳ [Round 1] Starting...
🗣️  Codex: <summary>
🗣️  Gemini: <summary>
   Consensus: ✗ (blocking: <issues>)

⏳ [Round 2] Starting...
...

✅ CONSENSUS REACHED
📋 Decision: <decision>
🚫 Blocking issues: <issues>
💡 Reasoning: <reasoning>
📁 Artifacts: <paths>
```

---

### Task #38: 集成到collab.py统一入口

**目标：** 在collab.py中添加discuss子命令

**修改文件：**
- scripts/collab.py

**功能：**
1. 添加discuss子命令解析
2. 调用collab_discuss_wrapper.py
3. 传递参数
4. 处理返回结果

---

### Task #39: 添加测试

**目标：** 验证discuss功能

**新建文件：**
- scripts/test_discuss_wrapper.py

**测试用例：**
1. 参数缺失（topic必需）
2. 共识成功场景
3. 无共识场景
4. 脚本失败处理
5. 状态恢复提示

---

### Task #40: 更新文档

**目标：** 更新README和SKILL.md

**修改文件：**
- README.md
- SKILL.md

**内容：**
1. 添加`/collab discuss`使用说明
2. 示例
3. 与omc ask的对比

---

## 验收标准

Phase 4A完成需满足：

1. **功能完整**
   - `/collab discuss`可以触发三方讨论
   - 参数解析正确
   - 输出格式规范

2. **UX良好**
   - 实时进度显示清晰
   - 最终结果结构化
   - 错误信息友好

3. **测试覆盖**
   - 至少5个测试用例
   - 所有测试通过

4. **文档完整**
   - README有使用说明
   - SKILL.md有触发语义

---

## 执行顺序

1. Task #36（扩展SKILL.md）- 定义接口
2. Task #37（实现wrapper）- 核心功能
3. Task #38（集成collab.py）- 统一入口
4. Task #39（测试）- 验证功能
5. Task #40（文档）- 知识固化

---

## Phase 4B推迟功能

- participants自定义
- `/collab-discuss` alias
- 实时TUI
- 人类中途介入
- 讨论模板
- 复杂共识评分

---

## 风险控制

**主要风险：**
1. 现有`/collab`技能结构是否容易扩展
2. 脚本输出是否可稳定解析
3. 长讨论是否噪音过大

**缓解措施：**
1. 固定参数面，降低复杂度
2. Wrapper错误映射，规范输出
3. 压缩进度输出，只显示关键信息

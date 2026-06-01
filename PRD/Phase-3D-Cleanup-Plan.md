# Phase 3D-Cleanup 执行计划

**目标：** 清理P2遗留问题，为Phase 4A-Discussion MVP打好基础

**预计时间：** 0.5-1天

**风险评估：** 低

---

## 任务列表

### Task #33: 修复all_responded字段语义

**问题：**
scripts/collab_state.py:273无条件设置all_responded=True，即使有participant失败或被跳过。

**修复方案：**
1. 修改complete_round()接口，传入actual_responded_count和expected_count
2. 计算all_responded = (actual_responded_count == expected_count)
3. 更新调用点collab_discuss.py传入正确的计数

**验收标准（5类场景）：**
1. 新任务全部响应：all_responded=true
2. 部分响应（有失败）：all_responded=false
3. 全部响应但无共识：all_responded=true, consensus=false
4. 恢复后继续等待：all_responded根据实际响应数判断
5. 超时或中断恢复：all_responded=false

**文件：**
- scripts/collab_state.py
- scripts/collab_discuss.py

---

### Task #34: 补齐E2E测试

**目标：** 覆盖恢复语义和Discussion基础状态

**测试用例：**
1. test_resume_with_partial_failure.py
   - 场景：Round 1 codex完成，gemini失败
   - 验证：resume不带--retry-failed跳过gemini
   - 验证：all_responded=false, consensus=false

2. test_resume_with_retry.py
   - 场景：Round 1 gemini失败
   - 验证：resume --retry-failed重新执行gemini
   - 验证：成功后all_responded=true

3. test_discussion_consensus.py
   - 场景：两个participant都返回consensus=true
   - 验证：judge_consensus返回true
   - 验证：task status=completed

4. test_discussion_no_consensus.py
   - 场景：一个consensus=true，一个consensus=false
   - 验证：judge_consensus返回false
   - 验证：task继续下一轮

**文件：**
- scripts/test_resume_partial_failure.py（新建）
- scripts/test_resume_retry.py（新建）
- scripts/test_discussion_consensus.py（新建）

---

### Task #35: 完善用户文档

**目标：** 明确当前Discussion能力边界和下一阶段入口

**文档更新：**
1. README.md
   - 添加"Discussion功能"章节
   - 说明当前能力：多轮讨论、共识判断、状态持久化
   - 说明限制：需要手动调用collab_discuss.py
   - 预告Phase 4A：技能内直接讨论

2. .omc/collaboration/protocol.md
   - 添加Discussion协议规范
   - 定义consensus判断规则
   - 定义blocking_issues语义

3. docs/ARCHITECTURE.md（新建）
   - 系统架构图
   - 模块职责说明
   - 数据流图

**文件：**
- README.md
- .omc/collaboration/protocol.md
- docs/ARCHITECTURE.md（新建）

---

## 验收标准

Phase 3D完成需满足：

1. **all_responded语义正确**
   - 5类场景测试通过
   - scan命令显示状态与持久化一致

2. **E2E测试覆盖**
   - 至少4个新测试用例
   - 覆盖恢复语义和Discussion基础状态
   - 所有测试通过

3. **文档完整**
   - README明确Discussion能力边界
   - protocol.md定义Discussion协议
   - ARCHITECTURE.md说明系统架构

4. **无回归**
   - 所有现有测试仍然通过
   - 无新引入的bug

---

## 执行顺序

1. Task #33（修复all_responded）- 核心修复
2. Task #34（E2E测试）- 验证修复
3. Task #35（文档）- 知识固化

---

## 下一步

Phase 3D完成后，启动Phase 4A-Discussion MVP规划讨论。

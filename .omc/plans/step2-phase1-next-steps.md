# Step 2 Phase 1 下一步计划

**创建时间：** 2026-05-30T17:04:00Z  
**状态：** 待执行

---

## 当前状态

**已完成：**
- Claude创建初始修正方案响应
- Codex完成批判性审查，识别6个阻塞问题

**阻塞问题：**
1. collab_task.py手写writer路径（line 8导入，lines 56-112手写事件/状态）
2. invoke-gemini-analysis.sh位置参数兼容性（lines 136, 212, 245使用位置参数5）
3. release_lock()危险的`except: pass`处理malformed owner.json
4. state_rules_version_changed双重分类（同时在STATE_TRANSITIONS和INFO_EVENTS）
5. state.json预验证缺失（需要在append前验证存在且为有效JSON对象）
6. Phase A共识事件冲突（consensus_reached是INFO事件，与"Phase A不追加INFO事件"冲突）

---

## 下一步行动

### Step 1: Claude响应阻塞问题（优先级：P0）

**创建文档：** `.omc/collaboration/artifacts/20260530-1705-claude-blocking-issues-response.md`

**必须解决的问题：**

1. **collab_task.py迁移策略**
   - 方案A: 改为wrapper，使用importlib导入新实现
   - 方案B: 直接修改导入路径指向新脚本
   - 推荐：方案A（保持文件位置不变，减少调用点修改）

2. **CLI参数兼容性**
   - 支持位置参数（向后兼容）
   - 支持标志参数（新推荐方式）
   - 实现：检测sys.argv格式，两种都支持

3. **release_lock()修正**
   - malformed owner.json → 失败，不删除锁
   - 只在owner匹配时删除锁
   - 添加明确的错误消息

4. **state_rules_version_changed分类**
   - 从STATE_TRANSITIONS移除
   - 仅保留在INFO_EVENTS
   - 文档说明：特殊激活事件，不更新state.status

5. **state.json预验证**
   - 持锁后立即验证state.json存在
   - 验证为有效JSON对象
   - 失败 → 报错并要求repair

6. **共识事件冲突解决**
   - 方案A: Phase 1完成后只写artifact和commit，不追加事件
   - 方案B: 等到Phase B激活后再追加consensus_reached事件
   - 推荐：方案A（避免状态污染）

---

### Step 2: Codex审查响应（优先级：P0）

**调用：** `/oh-my-claudecode:ask codex "审查Claude的阻塞问题响应"`

**期望输出：**
- 确认6个问题的解决方案是否完整
- 指出任何遗漏或新问题
- 批准或要求进一步修正

---

### Step 3: 达成共识（优先级：P0）

**创建文档：** `.omc/collaboration/artifacts/20260530-17XX-step2-phase1-final-consensus.md`

**内容：**
- 确认的解决方案
- 实施顺序
- 验证标准
- 批准实施

---

### Step 4: 实施Phase 1a（优先级：P0）

**创建4个新文件：**
1. `.omc/collaboration/scripts/collab_lock.py`
2. `.omc/collaboration/scripts/collab_schema.py`
3. `.omc/collaboration/scripts/collab_journal.py`
4. `.omc/collaboration/scripts/collab_event.py`

**包含所有修正：**
- strict=True默认
- LEGACY_UNKNOWN_EVENT_STATUS命名
- 持锁后日志完整性验证
- owner校验
- stale lock报告
- 完整schema注册
- CLI参数兼容性
- state.json预验证
- temp state验证
- sys.path处理

**验证：**
```bash
python3 -m py_compile .omc/collaboration/scripts/*.py
```

---

### Step 5: 实施Phase 1b（优先级：P0）

**修改3个文件：**

1. **`.claude/skills/claude-codex-collab/scripts/collab_event.py`**
   - 改为wrapper
   - 使用importlib导入新实现
   - 保持CLI接口兼容

2. **`.claude/skills/claude-codex-collab/scripts/collab_task.py`**
   - 修改line 8导入指向新脚本
   - 或改为调用新脚本的append_event

3. **`.omc/collaboration/scripts/invoke-gemini-analysis.sh`**
   - Lines 136, 212, 245更新调用方式
   - 使用新脚本路径
   - 保持参数格式（新脚本支持位置参数）

**验证：**
```bash
rg "collab_event.py" --type sh
rg "from collab_event import" --type py
```

---

### Step 6: 扩展验证（优先级：P0）

**Tempdir测试（7项）：**
1. py_compile验证语法
2. 初始化tempdir，调用append_event验证ID/JSONL/state
3. malformed line测试 → 拒绝
4. duplicate id测试 → 拒绝
5. 已有lock测试 → 不写事件
6. stale lock测试 → 只报告不删除
7. wrapper和调用点验证 → 都走新入口

**collab_task.py烟雾测试：**
```bash
cd .claude/skills/claude-codex-collab/scripts
python3 -c "from collab_task import claim_task; print('Import OK')"
```

**最终验证：**
```bash
.omc/collaboration/scripts/validate-journal.sh
```

---

### Step 7: 提交（优先级：P0）

**Commit消息：**
```
feat: Step 2 Phase 1完成 - 统一协作脚本入口

Phase 1a:
- 创建4个新脚本（lock/schema/journal/event）
- 包含所有P0/P1修正

Phase 1b:
- collab_event.py改为wrapper
- collab_task.py更新导入
- invoke-gemini-analysis.sh更新调用点

验证：
- 7项tempdir测试通过
- collab_task.py烟雾测试通过
- validate-journal.sh通过

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

**推送：**
```bash
git push
```

---

## 成功标准

- [ ] 6个阻塞问题全部解决
- [ ] Codex批准实施方案
- [ ] 4个新文件创建且语法正确
- [ ] 3个旧文件成功迁移为wrapper/更新调用
- [ ] 7项tempdir测试全部通过
- [ ] collab_task.py烟雾测试通过
- [ ] validate-journal.sh通过
- [ ] 提交并推送到GitHub

---

## 风险与依赖

**风险：**
- collab_task.py导入路径可能影响其他未知调用点
- invoke-gemini-analysis.sh参数格式变更可能影响运行中的流程

**缓解：**
- 新脚本支持位置参数和标志参数（向后兼容）
- wrapper保持原有接口不变
- 充分的tempdir测试验证行为一致性

**依赖：**
- Codex批准响应方案
- 无其他并行修改协作脚本

---

## 预计时间

- Step 1: Claude响应 - 30分钟
- Step 2: Codex审查 - 15分钟
- Step 3: 达成共识 - 10分钟
- Step 4: Phase 1a实施 - 45分钟
- Step 5: Phase 1b实施 - 30分钟
- Step 6: 扩展验证 - 30分钟
- Step 7: 提交 - 5分钟

**总计：** ~2.5小时

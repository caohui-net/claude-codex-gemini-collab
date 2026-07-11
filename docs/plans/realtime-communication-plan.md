# 实时通讯改进实施计划

**目标**: 为claude-codex-gemini-collab项目引入agent间实时通讯机制

**参考**: MassGen的Hub共享和并行协作架构

**计划周期**: 阶段1（1周）+ 阶段2（1-2月）

**总投入**: 160-205小时（1-1.5人月）

---

## 现状分析

### 当前架构

**执行模式**: 串行执行（scripts/collab_discuss.py:1908-1938）
- 循环调用agents: codex → gemini → claude
- 总耗时 = 求和（codex 60s + gemini 45s + claude 30s = 135s）

**通讯方式**: 文件状态共享
- `.collab/events.jsonl` - 事件日志
- `.collab/state.json` - 全局状态
- `.collab/artifacts/` - agent响应

**核心问题**:
1. ⏱️ 串行效率低（总时间=求和）
2. 🔇 信息孤岛（agent看不到其他agent进行中工作）
3. 📦 批处理模式（必须全部完成才共识）
4. ❌ 无法动态调整策略

### 现有能力

- ✅ ThreadPoolExecutor已导入
- ✅ 事件系统基础完善
- ✅ 状态管理框架清晰
- ✅ AgentReply数据结构统一

---

## 阶段1：流式感知机制（1周）

### 目标

让后续agent能实时看到前面agent的进行中工作，建立"上下文感知"。

**关键改进**: 从"事后共享"到"过程可见"

### 技术方案

**新增目录**:
```
.collab/streams/
  ├── codex.stream
  ├── gemini.stream
  └── claude.stream
```

**核心机制**:
1. Agent执行时边计算边写入流文件
2. 后续agent启动前读取已有流文件
3. 将前面agent的进度注入到prompt

**执行流程**:
```python
run_codex() → writes to codex.stream (实时)
run_gemini() → reads codex.stream + writes gemini.stream
run_claude() → reads codex+gemini streams + writes claude.stream
```

### 实施任务（总计20-25小时）

**Task 1.1: Agent流式输出** (4-6h)
- 文件: `scripts/agent_cli.py`
- 实现: `run_agent_streaming()` 函数

**Task 1.2: 流上下文构建** (4-6h)
- 文件: `scripts/collab_discuss.py`
- 实现: `build_stream_aware_prompt()` 函数

**Task 1.3: 集成到run_discussion** (3-4h)
- 文件: `scripts/collab_discuss.py`
- 修改: 行1908-1938，添加流式感知

**Task 1.4: 测试验证** (4-6h)
- 测试: 流式输出、上下文传递、边界情况

### 预期成果

**功能**:
- ✅ 后续agent看到前面agent思考过程
- ✅ 减少重复分析
- ✅ 提升响应连贯性

**性能**:
- ⚠️ 仍是串行执行（总时间无缩短）
- ✅ 流式IO开销<5%

**风险**:
- 流文件损坏 → 添加异常处理回退

---

## 阶段2：异步并行架构（1-2月）

### 目标

实现真正的并行协作，agents同时工作并通过Hub实时共享进展。

**关键改进**: 从"串行等待"到"异步并行"

**性能提升**: 总耗时从135s降至65-70s（提速2倍）

### 技术方案

**参考MassGen核心思想**:
- 不可变快照（immutable snapshots）
- 版本化存储（versioned storage）
- 原子性访问（atomic symlinks）
- 异步事件驱动（async event-driven）

**新增组件**:
```
.collab/hub/
  ├── coordination_events.jsonl
  ├── snapshots/
  │   ├── codex_v1/
  │   ├── codex_v2/
  │   └── codex_latest -> codex_v2
  └── notifications.json
```

### 核心设计

**CollaborationHub类**:
```python
class CollaborationHub:
    async def run_parallel_discussion(agents, prompt, max_rounds):
        # 启动所有agents（异步并行）
        tasks = [run_agent_with_hub(agent, prompt) for agent in agents]
        results = await asyncio.gather(*tasks)
        return check_consensus(results)
    
    async def run_agent_with_hub(agent, prompt):
        # 1. 获取peer快照
        # 2. 构建enriched prompt
        # 3. 执行agent
        # 4. 保存不可变快照
        # 5. 通知peers
        # 6. 检查是否restart
```

**SnapshotStore**:
- 不可变快照（写入后永不修改）
- 原子性符号链接（temp+replace避免竞态）
- 无锁读取（多agents并发读取无冲突）
- 版本化（支持restart后的多版本）

### 实施任务（总计140-180小时）

**Phase 2.1: Hub基础架构** (Week 1-2, 40-50h)
- Task 2.1.1: 创建CollaborationHub类框架
- Task 2.1.2: 实现SnapshotStore
- Task 2.1.3: 实现事件和通知系统
- Task 2.1.4: 单元测试

**Phase 2.2: 异步并行执行** (Week 3-4, 50-60h)
- Task 2.2.1: 改造agent_cli为async接口
- Task 2.2.2: 实现run_parallel_discussion
- Task 2.2.3: 实现restart机制
- Task 2.2.4: 集成测试

**Phase 2.3: 共识增强** (Week 5, 20-30h)
- Task 2.3.1: 实现投票机制
- Task 2.3.2: 增强共识检测算法
- Task 2.3.3: 测试和调优

**Phase 2.4: 向后兼容和迁移** (Week 6-7, 30-40h)
- Task 2.4.1: 提供模式切换（--mode=serial|parallel）
- Task 2.4.2: 数据迁移工具
- Task 2.4.3: 文档更新
- Task 2.4.4: 全面回归测试

### 预期成果

**性能提升**:
- ⚡ 总耗时从135s降至65-70s（提速2倍）
- ⚡ 动态优化：agents根据peer见解restart

**功能增强**:
- ✅ 真正实时通讯和协作
- ✅ 投票机制解决分歧
- ✅ 快照机制保证数据一致性

**复杂度代价**:
- ❌ 代码复杂度显著增加（新增~1000行）
- ❌ 并发调试难度提升
- ❌ 需要大量测试（~50个测试用例）

---

## 整体时间线

| 时间段 | 阶段 | 主要成果 | 累计投入 |
|--------|------|----------|----------|
| Week 1 | 阶段1 | 流式感知上线 | 20-25h |
| Week 2-3 | 阶段2.1 | Hub基础架构 | 60-75h |
| Week 4-5 | 阶段2.2 | 并行执行框架 | 110-135h |
| Week 6 | 阶段2.3 | 共识增强 | 130-165h |
| Week 7-8 | 阶段2.4 | 生产就绪 | 160-205h |

**总计**: 160-205小时（1-1.5人月）

---

## 技术风险与缓解

### 关键风险

**风险1: 流文件损坏（阶段1）**
- 影响: 后续agent无法读取peer context
- 缓解: 添加try-except，损坏时跳过peer context

**风险2: 并发竞态条件（阶段2）**
- 影响: 数据不一致、死锁
- 缓解: 不可变快照 + 原子性符号链接 + 充分并发测试

**风险3: 性能未达预期（阶段2）**
- 影响: 协调开销超过并行收益
- 缓解: 性能基准测试 + 可配置串行/并行模式

**风险4: 向后兼容性（阶段2）**
- 影响: 破坏现有工作流
- 缓解: 模式切换开关 + 默认串行 + 充分回归测试

**风险5: Restart无限循环（阶段2）**
- 影响: Agent永远无法收敛
- 缓解: 限制restart次数（MAX_RESTART=3）+ 超时机制

**风险6: 快照存储爆炸（阶段2）**
- 影响: 磁盘空间耗尽
- 缓解: 定期清理 + 压缩 + 限制保留版本

---

## 成功标准

### 阶段1成功标准

1. ✅ 功能验证: 后续agent能正确读取前面agent的流输出
2. ✅ 上下文质量: 注入的peer context准确且有价值
3. ✅ 稳定性: 所有现有测试通过，无回归
4. ✅ 性能: 流式IO开销<5%
5. ✅ 容错性: 流文件损坏时能优雅降级

### 阶段2成功标准

1. ✅ 并行执行: 三agents真正并行运行（asyncio.gather）
2. ✅ 性能提升: 总耗时缩短至65-70s（提速2倍）
3. ✅ 共识准确: 投票机制正常，共识检测准确率>90%
4. ✅ 数据一致性: 无并发竞态，快照读写正确
5. ✅ 向后兼容: 提供串行/并行模式切换
6. ✅ 可维护性: 代码清晰，文档完善，测试覆盖率>80%

---

## 后续优化方向

### 短期（阶段2完成后）
- Web监控界面（实时查看agent进展）
- 更智能的restart策略
- 快照智能清理

### 中期（3-6月）
- 支持更多agent类型
- 动态agent数量调整
- 负载均衡和限流

### 长期（6-12月）
- 分布式Hub（多机协作）
- AI辅助的协作策略优化
- 自适应restart策略

---

## 总结

### 核心价值

**阶段1（1周）**: 建立流式感知，让agents看到彼此思考过程，减少重复分析。**低风险、快速见效**。

**阶段2（1-2月）**: 实现真正并行协作，借鉴MassGen的Hub共享和不可变快照设计，实现**2倍性能提升**和动态优化能力。

### 关键技术点

- 不可变快照: 避免并发竞态
- 原子性符号链接: 无锁并发访问
- 异步事件驱动: 真正并行执行
- 多层次共识: 相似度+投票+冲突分析
- 动态restart: agents根据peer见解优化

### 实施建议

1. 先行阶段1: 快速验证流式感知价值
2. 充分测试: 每个Phase结束进行全面测试
3. 逐步迁移: 提供串行/并行模式切换
4. 持续监控: 建立性能基准，跟踪关键指标
5. 文档优先: 及时更新文档，降低维护成本

### 预期成果

- ✅ 阶段1: 响应质量提升，信息浪费减少
- ✅ 阶段2: 性能提升2倍，支持动态优化
- ✅ 整体: 建立可扩展的异步协作框架

---

**计划版本**: v1.0  
**制定日期**: 2026-07-11  
**制定人**: Claude (Background Session)  
**审批状态**: 待审批  
**预计总投入**: 160-205小时（1-1.5人月）

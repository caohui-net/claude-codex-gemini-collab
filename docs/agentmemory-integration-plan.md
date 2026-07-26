# agentmemory整合方案

**版本**: v1.0  
**日期**: 2026-06-07  
**状态**: 提案阶段  

## 执行摘要

基于agentmemory与claude-mem的对比分析，本方案提出**选择性整合策略**：保留claude-mem作为核心，将agentmemory的多智能体协作能力和跨平台兼容性作为**可选增强层**整合，实现两者优势互补。

**核心价值主张**：
- 保持claude-mem的Claude Code深度集成
- 扩展跨Agent协作能力（Codex/Gemini/Cursor统一内存）
- 提供多Agent协调原语（leases/signals/actions/routines）
- 实现跨项目内存共享

---

## 1. 架构设计

### 1.1 整合模式选择

**推荐方案：适配器层模式（Adapter Pattern）**

```
┌─────────────────────────────────────────────────┐
│           Claude Code / Codex / Gemini          │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│         MCP统一接口层（Unified MCP）            │
│  - 协议适配  - 路由决策  - 降级策略            │
└─────────────────────────────────────────────────┘
         ▼                              ▼
┌──────────────────────┐    ┌──────────────────────┐
│   claude-mem MCP     │    │  agentmemory MCP     │
│   (主要后端)         │    │  (协作增强层)        │
│                      │    │                      │
│ - 观察生成           │    │ - 跨Agent协调        │
│ - 时间线回溯         │    │ - Leases/Signals     │
│ - 知识语料库         │    │ - 跨平台内存         │
│ - SQLite/Chroma      │    │ - iii KV存储         │
└──────────────────────┘    └──────────────────────┘
         ▼                              ▼
┌──────────────────────┐    ┌──────────────────────┐
│  claude-mem Storage  │    │ agentmemory Server   │
│  (worker/server-beta)│    │ (可选，需常驻:3111)  │
└──────────────────────┘    └──────────────────────┘
```

### 1.2 架构层次

**L1 - 路由层（Router Layer）**
- 职责：根据操作类型决策使用claude-mem或agentmemory
- 实现：MCP工具调用拦截器
- 策略：
  - 单Agent操作 → claude-mem
  - 多Agent协作 → agentmemory
  - 跨项目内存 → agentmemory
  - 知识库查询 → claude-mem

**L2 - 适配层（Adapter Layer）**
- 职责：统一两个系统的数据模型和API
- 实现：
  - `claude-mem` ↔ `agentmemory` 数据转换器
  - 观察(Observation) ↔ 记忆(Memory) 映射
  - 会话(Session) ↔ 上下文(Context) 映射

**L3 - 同步层（Sync Layer）**
- 职责：可选的双向数据同步
- 实现：
  - claude-mem观察 → agentmemory记忆（单向推送）
  - 冲突检测与解决策略
  - 增量同步vs全量同步

**L4 - 协调层（Coordination Layer）**
- 职责：多Agent协作原语
- 实现：基于agentmemory的leases/signals/actions/routines
- 暴露：MCP工具接口

---

## 2. MCP接口整合

### 2.1 统一MCP服务器

**实现路径A：单一MCP进程（推荐）**

创建新的`claude-mem-unified` MCP服务器，内部桥接两个后端：

```typescript
// claude-mem-unified/src/server.ts
class UnifiedMcpServer {
  private claudeMemClient: ClaudeMemMcpClient;
  private agentMemoryClient: AgentMemoryMcpClient;
  
  async handleToolCall(tool: string, args: any) {
    // 路由决策
    if (MULTI_AGENT_TOOLS.includes(tool)) {
      return this.agentMemoryClient.call(tool, args);
    }
    return this.claudeMemClient.call(tool, args);
  }
}
```

**实现路径B：双MCP并存（低风险）**

Claude Code同时连接两个MCP服务器，通过工具名前缀区分：
- `claudemem_*`: claude-mem工具
- `agentmem_*`: agentmemory工具

### 2.2 工具映射表

| 功能域 | claude-mem工具 | agentmemory工具 | 路由策略 |
|--------|----------------|-----------------|----------|
| 搜索 | `search`, `timeline` | `memory_smart_search` | 优先claude-mem |
| 保存 | `observation_add` | `memory_save` | 双写（可选） |
| 召回 | `observation_context` | `memory_recall` | 优先claude-mem |
| 多Agent协调 | 无 | `lease_acquire`, `signal_send` | 仅agentmemory |
| 会话管理 | `session_*` | `memory_sessions` | 各自独立 |
| 知识库 | `build_corpus`, `query_corpus` | 无 | 仅claude-mem |

### 2.3 新增统一工具

```typescript
// 统一搜索工具
tool: "unified_search"
description: "跨claude-mem和agentmemory搜索"
parameters: {
  query: string,
  scope: "local" | "cross-agent" | "all",
  agent_filter?: string[]
}

// 多Agent召回工具
tool: "multi_agent_recall"
description: "召回跨Agent的相关上下文"
parameters: {
  query: string,
  agents: string[],  // ["claude", "codex", "gemini"]
  merge_strategy: "union" | "intersection"
}

// Agent协调工具
tool: "agent_coordinate"
description: "多Agent任务协调"
parameters: {
  operation: "lease" | "signal" | "action",
  target_agent: string,
  payload: any
}
```

---

## 3. 数据同步策略

### 3.1 同步模式

**模式1：单向推送（推荐初期）**

```
claude-mem observations → agentmemory memories
```

- 时机：PostToolUse hook触发后
- 频率：实时或批量（每10个观察）
- 过滤：仅推送标记为`shareable`的观察
- 转换：observation → memory格式映射

**模式2：双向同步（高级）**

```
claude-mem ↔ agentmemory
```

- 冲突解决：
  - 时间戳优先（latest-wins）
  - 来源优先（claude-mem优先）
  - 合并策略（保留两个版本）
- 实现：基于事件日志的增量同步

**模式3：按需查询（最简单）**

无持久同步，仅在需要时跨系统查询：
- claude-mem作为主存储
- agentmemory作为协作层查询

### 3.2 数据映射

**claude-mem Observation → agentmemory Memory**

```typescript
interface ObservationToMemoryMapping {
  // claude-mem字段 → agentmemory字段
  id: string;                    → memory_id: string;
  content: string;               → content: string;
  project_id: string;            → project: string;
  session_id: string;            → session_id: string;
  obs_type: string;              → type: "episodic" | "semantic";
  created_at: string;            → timestamp: number;
  metadata: Record<string, any>; → metadata: {
                                     source: "claude-mem",
                                     agent: "claude",
                                     ...metadata
                                   };
}
```

### 3.3 同步实现

**Webhook方式（推荐）**

```typescript
// claude-mem hook
PostToolUse: async (tool, result) => {
  if (isShareable(result)) {
    await agentMemoryClient.push({
      content: result.observation.content,
      metadata: {
        source: "claude-mem",
        agent: "claude",
        tool: tool.name
      }
    });
  }
}
```

**定时任务方式**

```bash
# Cron job每5分钟同步
*/5 * * * * node /path/to/sync-script.js
```

---

## 4. 风险评估与缓解

### 4.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| agentmemory服务器不稳定导致整体故障 | 高 | 中 | 降级策略：服务不可用时自动切回claude-mem单机模式 |
| 双存储数据不一致 | 中 | 高 | 明确主从关系：claude-mem为主，agentmemory为增强层 |
| iii-engine版本锁定限制升级 | 中 | 中 | 容器化部署，固定环境 |
| 向量暴力搜索性能瓶颈 | 中 | 低 | 限制agentmemory语料规模，或贡献HNSW索引PR |
| MCP工具命名冲突 | 低 | 中 | 使用前缀或命名空间隔离 |

### 4.2 运维风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 需要维护两套服务进程 | 中 | 高 | 提供统一启动脚本和健康检查 |
| 增加系统复杂度 | 中 | 高 | 充分文档化，提供故障诊断工具 |
| 用户配置门槛高 | 低 | 中 | 提供一键安装脚本和向导 |

### 4.3 生态风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| agentmemory项目停止维护 | 高 | 低 | Fork并自维护关键功能 |
| claude-mem与agentmemory发展方向分歧 | 中 | 中 | 保持适配层抽象，降低耦合 |

### 4.4 降级策略

**L1 - agentmemory完全不可用**
```typescript
if (!agentmemoryAvailable) {
  console.warn("agentmemory unavailable, falling back to claude-mem only");
  return claudeMemClient.handleAll(tool, args);
}
```

**L2 - agentmemory部分功能降级**
```typescript
if (tool === "lease_acquire" && !agentmemoryAvailable) {
  // 本地内存锁降级实现
  return localLockManager.acquire(args);
}
```

**L3 - 用户可选关闭agentmemory**
```json
// .claude/settings.json
{
  "claudeMem": {
    "enableAgentMemory": false,
    "agentMemoryUrl": "http://localhost:3111"
  }
}
```

---

## 5. 实施路线图

### Phase 0: 准备阶段（1-2天）

**目标**: 环境搭建和可行性验证

- [x] 完成对比分析（已完成）
- [ ] agentmemory本地安装测试
  ```bash
  npm install -g @agentmemory/agentmemory
  agentmemory  # 验证服务启动
  curl http://localhost:3111/health
  ```
- [ ] 验证agentmemory MCP代理模式
  ```bash
  agentmemory connect claude-code
  # 验证53工具可见
  ```
- [ ] 数据格式映射原型验证
- [ ] 技术栈兼容性确认

**交付物**: 
- 环境验证报告
- 数据映射原型代码

### Phase 1: 最小可行原型（MVP）（3-5天）

**目标**: 实现最基础的跨Agent内存共享

**实现范围**:
- [ ] 创建`claude-mem-agentmemory-adapter`包
- [ ] 实现单向推送：claude-mem → agentmemory
- [ ] 暴露3个核心工具：
  - `agent_memory_save`: 保存到agentmemory
  - `agent_memory_search`: 跨Agent搜索
  - `agent_status`: 查看已连接Agent状态
- [ ] 降级策略实现：agentmemory不可用时回退claude-mem
- [ ] 基础文档和使用示例

**验证标准**:
- Claude Code可以将观察推送到agentmemory
- Codex CLI可以查询到Claude Code的记忆
- 服务故障时不影响claude-mem正常工作

**交付物**:
- `claude-mem-agentmemory-adapter` v0.1.0
- MVP使用文档
- 测试报告

### Phase 2: 协调能力增强（1周）

**目标**: 整合agentmemory的多Agent协调原语

**实现范围**:
- [ ] 暴露Lease机制：
  - `agent_lease_acquire`
  - `agent_lease_release`
  - `agent_lease_status`
- [ ] 暴露Signal机制：
  - `agent_signal_send`
  - `agent_signal_wait`
  - `agent_signal_list`
- [ ] 暴露Action队列：
  - `agent_action_enqueue`
  - `agent_action_claim`
  - `agent_action_complete`
- [ ] 实现协调原语的Claude Code技能封装

**验证标准**:
- 多个Agent可以协调访问共享资源
- 跨Agent任务队列正常工作
- 信号通知及时送达

**交付物**:
- 协调工具集
- 多Agent协作示例
- 协调协议文档

### Phase 3: 数据同步优化（3-5天）

**目标**: 实现高效的数据同步机制

**实现范围**:
- [ ] 增量同步算法
- [ ] 批量推送优化（减少网络开销）
- [ ] 选择性同步规则配置
- [ ] 冲突检测与解决
- [ ] 同步状态监控面板

**验证标准**:
- 同步延迟<100ms（P95）
- 批量同步不阻塞主流程
- 冲突正确解决，无数据丢失

**交付物**:
- 同步引擎 v1.0
- 性能测试报告
- 监控仪表板

### Phase 4: 生产级加固（1周）

**目标**: 达到生产可用标准

**实现范围**:
- [ ] 完善错误处理和重试机制
- [ ] 健康检查和自愈策略
- [ ] 日志和追踪（OpenTelemetry）
- [ ] 性能优化和压力测试
- [ ] 安全加固（认证、授权、加密）
- [ ] 一键安装和配置向导
- [ ] 完整文档和故障排查指南

**验证标准**:
- 可用性99.9%+
- P99延迟<500ms
- 通过安全审计
- 新用户10分钟内完成安装

**交付物**:
- v1.0正式版
- 生产部署文档
- 故障排查手册
- 安全审计报告

### Phase 5: 生态整合（持续）

**目标**: 与其他Agent工具生态整合

**实现范围**:
- [ ] Cursor集成测试和文档
- [ ] GitHub Copilot CLI集成
- [ ] OpenCode集成
- [ ] 社区反馈收集和迭代
- [ ] 贡献agentmemory上游改进

**交付物**:
- 跨平台集成文档
- 社区使用案例库
- 上游贡献PR

---

## 6. 成功指标

### 技术指标
- [ ] agentmemory MCP成功率 >99%
- [ ] 跨Agent内存召回准确率 >90%
- [ ] 同步延迟P95 <100ms
- [ ] 降级切换时间 <5s
- [ ] 系统可用性 >99.9%

### 用户体验指标
- [ ] 安装完成时间 <10分钟
- [ ] 跨Agent协作场景覆盖率 >80%
- [ ] 用户满意度评分 >4.5/5
- [ ] 故障自愈成功率 >95%

### 生态指标
- [ ] 支持Agent数量 ≥4 (Claude/Codex/Gemini/Cursor)
- [ ] 社区贡献者 ≥3
- [ ] 活跃项目采用数 ≥10

---

## 7. 替代方案对比

### 方案A: 完全替换claude-mem（不推荐）

**优点**:
- 架构简单，单一存储后端
- agentmemory天生多Agent支持

**缺点**:
- 丢失claude-mem的Claude Code深度集成
- 丢失知识语料库、时间线等高级功能
- 迁移成本高，破坏性变更

**结论**: 不采纳。claude-mem与Claude Code生态紧密绑定，完全替换得不偿失。

### 方案B: 仅用agentmemory的MCP（不推荐）

**优点**:
- 实现简单，无需适配层
- 学习曲线低

**缺点**:
- agentmemory独立模式仅7工具，功能严重降级
- 无法利用claude-mem的高级功能
- 必须保持agentmemory服务器常驻

**结论**: 不采纳。独立模式功能不足，不满足需求。

### 方案C: 适配器层整合（推荐，本方案）

**优点**:
- 保留两者优势，互补增强
- 渐进式实施，风险可控
- 降级策略完善，高可用

**缺点**:
- 增加系统复杂度
- 需维护适配层代码

**结论**: 采纳。最平衡的方案，收益>成本。

---

## 8. 下一步行动

### 立即执行（本周）
1. [ ] 安装agentmemory并验证MCP代理模式
2. [ ] 创建`claude-mem-agentmemory-adapter`代码仓库
3. [ ] 实现数据映射原型
4. [ ] 编写技术设计文档（TDD）

### 短期计划（2周内）
1. [ ] 完成MVP开发（Phase 1）
2. [ ] 内部测试和反馈收集
3. [ ] 协调能力增强（Phase 2）

### 中期计划（1个月内）
1. [ ] 数据同步优化（Phase 3）
2. [ ] 生产级加固（Phase 4）
3. [ ] Alpha用户测试

### 长期计划（3个月内）
1. [ ] 正式发布v1.0
2. [ ] 生态整合（Phase 5）
3. [ ] 社区推广和文档完善

---

## 附录

### A. 参考资料
- agentmemory GitHub: https://github.com/rohitg00/agentmemory
- claude-mem文档: [本地安装路径]
- MCP协议规范: https://modelcontextprotocol.io
- Codex技术分析: `.omc/artifacts/ask/codex-fetch-and-analyze-agentmemory-repo-*.md`

### B. 术语表
- **MCP**: Model Context Protocol
- **Lease**: 分布式锁机制
- **Signal**: Agent间信号通知
- **Action**: 跨Agent任务队列
- **Routine**: 可复用的Agent协作流程
- **iii-engine**: agentmemory的底层运行时

### C. 联系方式
- 技术问题: [项目Issue跟踪器]
- 架构讨论: [项目Wiki]
- 紧急故障: [值班联系方式]

---

**文档状态**: ✅ 提案完成，待评审  
**下次评审**: Phase 0完成后  
**维护者**: Claude (主), Codex, Gemini

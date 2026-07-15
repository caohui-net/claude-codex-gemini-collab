# Ruflo vs Claude-Codex-Gemini-Collab 技术对比

## 1. 核心定位

### Ruflo
- **定位**: Agent meta-harness（元框架）
- **口号**: "Agent = Model + Harness"
- **作用**: 为Claude Code/Codex提供执行层
- **规模**: 100+ specialized agents, 60+ commands, 30 skills

### 当前项目 (claude-codex-gemini-collab)
- **定位**: 多agent讨论协作系统
- **作用**: Claude/Codex/Gemini协作讨论与共识达成
- **规模**: 3 agents (Claude/Codex/Gemini), 专注讨论场景
## 2. 技术架构对比

### Ruflo架构
```
User → Ruflo (CLI/MCP) → Router → Swarm → Agents → Memory → LLM Providers
                      ↑                            ↓
                      +-------- Learning Loop -----+
```
- **Router**: 任务路由分发
- **Swarm**: Agent集群协调
- **Learning Loop**: 自学习优化
- **Memory**: 跨session记忆
- **Federation**: 跨机器通信

### 当前项目架构
```
User → collab_discuss.py → [parallel_engine] → [Agent CLI] → LLM APIs
                                ↓
                              Hub (immutable snapshots)
                                ↓
                          Consensus Detection
```
- **parallel_engine**: AsyncIO并行执行
- **Hub**: 不可变快照存储
- **Consensus**: 相似度共识检测
- **State Management**: 讨论状态管理
## 3. 核心功能特性

### Ruflo特性
✅ Self-learning memory（自学习记忆）
✅ 100+ specialized agents
✅ Swarm coordination（集群协调）
✅ Federation（跨机器通信）
✅ RAG integration
✅ MCP server
✅ Hooks system
✅ Enterprise security guardrails

### 当前项目特性
✅ 3-agent讨论协作（Claude/Codex/Gemini）
✅ 流式感知机制（Phase 1）
✅ 实时进度显示
✅ Hub不可变快照
✅ 共识检测（相似度算法）
✅ AsyncIO并行执行
✅ 讨论状态持久化
✅ AgentMemory集成
## 4. 技术栈

### Ruflo
- **语言**: TypeScript
- **运行时**: Node.js
- **核心引擎**: Rust (Cognitum.One)
- **包管理**: npm/npx
- **部署**: CLI + MCP server

### 当前项目
- **语言**: Python 3.14
- **异步**: asyncio
- **CLI**: argparse
- **存储**: JSON + JSONL
- **测试**: pytest
## 5. 技术相似性

### 共同点
✅ **多agent协作架构**
✅ **Codex集成**（都支持Codex agent）
✅ **状态管理**（Ruflo: Learning Loop, 当前项目: Hub）
✅ **异步执行**（Ruflo: Swarm, 当前项目: asyncio）
✅ **记忆系统**（Ruflo: Self-learning, 当前项目: AgentMemory）
✅ **CLI接口**
✅ **MCP集成潜力**

### 设计理念相似
- Agent coordination（agent协调）
- Persistent state（状态持久化）
- Real-time communication（实时通信）
## 6. 关键差异

### 规模差异
- Ruflo: 100+ agents, 通用框架
- 当前项目: 3 agents, 专注讨论

### 语言差异
- Ruflo: TypeScript/Rust
- 当前项目: Python

### 定位差异
- Ruflo: Meta-harness（元框架层）
- 当前项目: Application（应用层）

### 部署差异
- Ruflo: npx一键安装，MCP server
- 当前项目: Python脚本，手动配置
## 7. 结论

### 关系判断
**当前项目未直接使用ruflo，但概念上高度相似**

### 可能的启发
1. ✅ 多agent协作架构思想
2. ✅ 状态持久化设计
3. ✅ 实时通信机制
4. ✅ Codex集成模式

### 技术独立性
- ❌ 无代码依赖
- ❌ 无直接引用
- ✅ 独立实现
- ✅ 相似问题域

### 建议
考虑未来整合ruflo作为底层框架，当前项目作为讨论场景的专业化实现。

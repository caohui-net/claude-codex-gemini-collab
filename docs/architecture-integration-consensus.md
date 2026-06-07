# 多智能体协作架构整合共识

**讨论ID**: DISCUSS-多智能体协作架构整合方案-用户需求-整合AGENTMEMORY跨项目协同能力与COLLAB讨论机制-1780823469  
**日期**: 2026-06-07  
**参与者**: Claude, Codex, Gemini  
**轮次**: 5轮  
**状态**: ✅ 达成完全共识

---

## 最终决策

**采用方案C：混合架构**

### 职责分工

| 系统 | 职责 | 核心能力 |
|------|------|----------|
| **collab** | 单次讨论编排 | 结构化往来、互相质疑、轮次收敛、结论产出 |
| **agentmemory** | 跨会话/跨项目持久化 | 历史检索、共识存储、跨项目复用、冲突检测 |

### 方案优势

1. **边界清晰** - 实时讨论编排 vs 长期记忆存储职责分离
2. **可渐进上线** - 先改造collab协议，再接入agentmemory
3. **兼容现有架构** - 与coordination抽象层、iii-sdk、lease/signal/action机制兼容
4. **避免职责混淆** - 方案A无法复用成果，方案B混淆编排与存储

---

## 三阶段实施计划

### Phase 1: 改造collab讨论协议

**目标**: 从"平行独立分析"升级为"真正往来讨论"

#### 核心数据结构

```python
@dataclass
class DiscussionSession:
    id: str
    topic: str
    participants: List[str]
    rounds: List[Round]
    conclusion: Optional[Conclusion]

@dataclass
class Round:
    number: int
    responses: List[Response]
    open_questions: List[str]
    
@dataclass
class Response:
    agent: str
    content: str
    previous_responses: List[str]  # 引用的前序回应ID
    targeted_challenges: List[Challenge]  # 针对性质疑
    
@dataclass
class Challenge:
    target_agent: str
    target_response_id: str
    question: str
    rationale: str

@dataclass
class Conclusion:
    decision: str
    dissent: Optional[str]  # 不同意见记录
    evidence: List[str]
    action_items: List[ActionItem]
```

#### 协议变更

**当前流程**:
```
发topic → 收集各自回复 → 无针对性往来
```

**改进流程**:
```
1. Pre-discuss: Claude初始分析 → 形成初始文档
2. Round 1: 提交给Codex/Gemini，要求针对Claude观点分析
3. Round N: 互相质疑，迭代完善
   - 每轮输入包含 previous_responses, open_questions
   - 要求直接引用他方观点
4. Conclude: 统一结论或记录分歧
```

---

### Phase 2: 接入agentmemory读写

**目标**: 跨会话记忆增强讨论质量，跨项目共享成果

#### 讨论前：历史检索

```python
# 伪代码
def start_discussion(topic: str):
    # 查询相关历史共识
    related = agentmemory.search(
        query=topic,
        type="discussion_consensus",
        scope=["current_project", "global"]
    )
    
    # 注入到初始上下文
    context = {
        "topic": topic,
        "related_consensus": related,
        "potential_conflicts": check_conflicts(topic, related)
    }
    
    return context
```

#### 讨论后：持久化共识

```python
@dataclass
class ConsensusArtifact:
    """结构化共识artifact，存入agentmemory"""
    topic: str
    participants: List[str]
    decision: str
    dissent: Optional[str]
    evidence: List[str]
    action_items: List[dict]
    project_scope: str  # "project-specific" | "cross-project" | "global"
    confidence: float  # 0.0-1.0
    supersedes: Optional[str]  # 替代的旧共识ID
    tags: List[str]
    
def conclude_discussion(session: DiscussionSession):
    artifact = ConsensusArtifact(
        topic=session.topic,
        participants=session.participants,
        decision=session.conclusion.decision,
        # ...
    )
    
    # 写入agentmemory
    agentmemory.save_memory(
        content=artifact.to_dict(),
        type="discussion_consensus",
        concepts=[session.topic, *artifact.tags],
        project=detect_project_scope(artifact)
    )
```

#### 数据分类

| 数据类型 | 生命周期 | 存储位置 | 用途 |
|---------|---------|---------|------|
| 临时讨论signal | 会话内 | agentmemory signals | 实时协调 |
| 待执行action | 短期 | agentmemory actions | 任务分配 |
| 长期共识memory | 永久 | agentmemory memories | 跨项目复用 |

---

### Phase 3: 高级功能

#### 冲突检测

```python
def check_conflicts(new_topic: str, related: List[Consensus]) -> List[Conflict]:
    """检测新讨论是否与历史共识冲突"""
    conflicts = []
    for old in related:
        if semantic_opposite(new_topic, old.decision):
            conflicts.append(Conflict(
                old_consensus_id=old.id,
                reason=f"New topic contradicts {old.decision}",
                severity="high" if old.confidence > 0.8 else "medium"
            ))
    return conflicts
```

#### 跨项目协同控制

需要的机制：
- **命名空间** - 区分项目级 vs 全局级共识
- **权限控制** - 谁可以读/写/覆盖特定共识
- **过期策略** - 旧共识何时标记为过期
- **版本控制** - 同一topic的多个版本如何管理

---

## 验证指标

Codex提出的三项可量化指标：

### 1. 引用率（讨论质量）
```
引用率 = 直接引用他方观点的回应数 / 总回应数
目标：>60%（当前接近0%）
```

### 2. Action Item可执行率（结论质量）
```
可执行率 = 明确可执行的action items / 总action items
标准：包含谁、做什么、何时、如何验证
目标：>80%
```

### 3. 历史共识复用命中率（跨项目价值）
```
命中率 = 检索到相关历史共识的讨论数 / 总讨论数
目标：>40%（说明知识库有价值）
```

---

## Action Items

### 立即执行（Phase 1核心）

1. **定义协议数据结构**
   - [ ] 实现DiscussionSession/Round/Response/Challenge/Conclusion类
   - [ ] 修改collab_discuss.py，支持previous_responses和targeted_challenges字段
   - [ ] 添加Pre-discuss阶段（Claude初始分析）
   - 文件：`scripts/collab_discuss.py`, `scripts/models.py`

2. **更新讨论模板**
   - [ ] Round context必须包含previous_responses
   - [ ] 参与者prompt要求引用他方观点并提出targeted_challenges
   - 文件：`scripts/collab_discuss.py` (generate_context函数)

3. **结论判定机制**
   - [ ] 实现consensus检测逻辑（所有参与者consensus=true）
   - [ ] 支持dissent记录（部分同意但有保留意见）
   - 文件：`scripts/collab_discuss.py` (check_consensus函数)

### 短期执行（Phase 2整合）

4. **agentmemory集成**
   - [ ] 讨论开始前：调用agentmemory recall查询相关历史
   - [ ] 讨论结束后：调用agentmemory save保存结构化共识
   - [ ] 定义ConsensusArtifact schema
   - 文件：`scripts/collab_discuss.py`, `scripts/agentmemory_bridge.py`

5. **跨项目scope识别**
   - [ ] 分析讨论topic和context，判断project-specific vs cross-project
   - [ ] 添加--scope参数手动指定
   - 文件：`scripts/collab_discuss.py`

### 长期优化（Phase 3）

6. **冲突检测**
   - [ ] 实现semantic_opposite检测逻辑
   - [ ] 讨论开始前显示潜在冲突警告
   
7. **质量指标dashboard**
   - [ ] 计算并展示引用率、可执行率、复用命中率
   - [ ] 生成讨论质量报告

---

## 技术细节补充

### 方案A vs B vs C对比

| 维度 | 方案A（增强流程） | 方案B（纯agentmemory） | 方案C（混合）✅ |
|------|------------------|---------------------|---------------|
| 讨论质量 | ✅ 解决 | ❌ 未涉及 | ✅ 解决 |
| 跨项目复用 | ❌ 无持久化 | ✅ 解决 | ✅ 解决 |
| 职责分离 | ✅ 清晰 | ❌ 混淆编排与存储 | ✅ 清晰 |
| 渐进上线 | ⚠️ 需同步改 | ❌ 大爆炸 | ✅ 分阶段 |
| 架构兼容 | ✅ | ⚠️ 需重构 | ✅ |

### 潜在风险与边界条件

Codex提出的关注点：

1. **命名空间隔离** - 避免不同项目的共识互相干扰
2. **权限控制** - 跨项目读写权限管理
3. **过期策略** - 旧共识何时失效
4. **版本冲突** - 同一topic的不同版本如何处理
5. **临时vs长期** - 区分临时讨论signal、待执行action和长期共识memory

---

## 参考文档

- 讨论产物: `.omc/collaboration/artifacts/DISCUSS-多智能体协作架构整合方案-*-1780823469-*.md`
- agentmemory集成: `docs/agentmemory-integration-progress.md`
- coordination抽象层: `scripts/coordination.py`
- iii-sdk文档: `docs/iii-sdk-integration.md`

---

**共识达成时间**: 2026-06-07  
**下一步**: 执行Phase 1 Action Items

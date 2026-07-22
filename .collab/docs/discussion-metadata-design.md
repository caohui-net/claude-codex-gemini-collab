# 讨论文件元数据设计 - 最终版

## 版本: v1.1 (添加round_info)
## 日期: 2026-07-21

---

## 核心结构(4层)

### 第一层:核心识别字段(必需)

```yaml
# 项目标识
project: "claude-codex-gemini-collab"
project_path: "/home/caohui/projects/claude-codex-gemini-collab"

# 讨论标识
topic: "PR review"
round: 1
discussion_id: "disc-20260721-091530-a3f2"

# 时间戳
generated_at: "2026-07-21T09:15:30Z"

# 发表者
author: "codex"
author_role: "reviewer"
```

**字段数**: 8个必需字段

### 第二层:上下文字段(推荐)

```yaml
# 讨论触发源
trigger:
  type: "pr_review"
  pr_number: 12
  branch: "worktree-fix-codex-timeout-file-path"

# 涉及文件
files:
  - path: "scripts/collab_discuss.py"
    lines_changed: 42
    change_type: "modified"

# 讨论模式
mode: "parallel"

# 整体agents(所有参与讨论的agents)
agents: ["codex", "gemini", "claude"]

# 本轮信息(新增)
round_info:
  participants: ["codex", "gemini"]  # 本轮实际参与者
  author_position: 1  # 本作者在本轮的顺序
  total_in_round: 2  # 本轮参与者总数
```

**字段说明**:
- `agents`: 整个讨论涉及的所有agents
- `round_info.participants`: 本轮实际参与的agents(子集)
- `round_info.author_position`: 本作者在本轮中的发言顺序

### 第三层:关系字段(可选)

```yaml
# 讨论链
parent_discussion: null
related_discussions: ["disc-20260720-143022-b7d1"]

# 决策记录
decisions:
  - decision: "采用validate_and_fix_file_paths方案"
    made_by: "claude"
    timestamp: "2026-07-21T09:00:00Z"

# 待办事项
todos:
  - task: "合并PR#12"
    assignee: "human"
    status: "pending"
```

### 第四层:统计与扩展字段(可选)

```yaml
# 统计信息
stats:
  tokens_used: 5200
  duration_sec: 45
  iterations: 3

# 质量指标
quality:
  consensus_reached: true
  actionable: true
  verified: true

# 自定义字段
custom:
  bug_id: "bug-086"
  tags: ["timeout", "file-path", "codex"]
```

---

## 完整示例

```markdown
---
# 第一层:核心识别(必需)
project: "claude-codex-gemini-collab"
project_path: "/home/caohui/projects/claude-codex-gemini-collab"
topic: "PR review"
round: 1
discussion_id: "disc-20260721-091530-a3f2"
generated_at: "2026-07-21T09:15:30Z"
author: "codex"
author_role: "reviewer"

# 第二层:上下文(推荐)
trigger:
  type: "pr_review"
  pr_number: 12
  branch: "worktree-fix-codex-timeout-file-path"

files:
  - path: "scripts/collab_discuss.py"
    lines_changed: 42
    change_type: "modified"

mode: "parallel"
agents: ["codex", "gemini", "claude"]

round_info:
  participants: ["codex", "gemini"]
  author_position: 1
  total_in_round: 2

# 第三层:关系(可选)
parent_discussion: null
related_discussions: ["disc-20260720-143022-b7d1"]

decisions:
  - decision: "采用validate_and_fix_file_paths方案"
    made_by: "claude"
    timestamp: "2026-07-21T09:00:00Z"

todos:
  - task: "合并PR#12"
    assignee: "human"
    status: "pending"

# 第四层:统计(可选)
stats:
  tokens_used: 5200
  duration_sec: 45
  iterations: 3

quality:
  consensus_reached: true
  actionable: true
  verified: true

custom:
  bug_id: "bug-086"
  tags: ["timeout", "file-path", "codex"]
---

# Codex 的评审意见

## 问题分析
文件路径不一致导致Codex timeout...

## 建议方案
采用validate_and_fix_file_paths()函数...

```

---

## 实施建议

### 必需实现(8个字段)
project, project_path, topic, round, discussion_id, generated_at, author, author_role

### 推荐实现
- trigger(触发源信息)
- files(变更文件)
- agents + round_info(整体参与者 + 本轮参与者)

### 目录结构
```
~/.claude/collab/discussions/
└── {project-slug}/
    └── {topic}_r{round}_{author}_{timestamp}.md
```

### 格式
YAML Frontmatter + Markdown内容

---

## 规范与约束 (Codex审核要求补充)

### 1. Schema版本策略

**当前版本:** v1.1 (2026-07-21)

**版本演进规则:**
- **Major版本** (v2.0): 删除必需字段、改变字段类型、破坏性语义变更
- **Minor版本** (v1.1): 新增可选字段、扩展现有字段约束
- **Patch版本** (v1.1.1): 文档修正、示例更新

**向后兼容承诺:**
- 解析器必须忽略未知字段(forward compatibility)
- 新增字段必须为可选,不可破坏v1.0文档解析

**版本标识(可选):**
```yaml
schema_version: "v1.1"  # 缺省时视为v1.0兼容
```

### 2. 字段类型定义

#### 第一层(必需) - 8个字段

| 字段 | 类型 | 格式 | 约束 |
|------|------|------|------|
| project | string | slug | 非空,字母数字连字符 |
| project_path | string | path | 绝对路径 |
| topic | string | 任意 | 非空, <=200字符 |
| round | integer | >= 0 | 0=pre-discuss |
| discussion_id | string | disc-YYYYMMDD-HHMMSS-HASH | 唯一标识 |
| generated_at | string | ISO 8601 UTC | 必须以Z结尾 |
| author | string | agent name | 非空 |
| author_role | string | enum | "initiator"/"participant"/"reviewer" |

#### 第二层(推荐)

- `trigger`: object, 触发源信息
- `files`: array[object], 相关文件,每个对象包含path/purpose
- `mode`: string, "parallel"/"sequential"/"full"/"fast"
- `agents`: array[string], 整体参与agent列表
- `round_info`: object, 包含participants/author_position/total_in_round

#### 第三层(可选) + 第四层(可选)

详见上方完整示例。

### 3. 必填规则

**严格必需(8个):**
```yaml
project: <string, 非空>
project_path: <string, 绝对路径>
topic: <string, 非空, <=200字符>
round: <integer, >= 0>
discussion_id: <string, disc-YYYYMMDD-HHMMSS-HASH>
generated_at: <string, ISO 8601 UTC, YYYY-MM-DDTHH:MM:SSZ>
author: <string, 非空>
author_role: <string, "initiator"|"participant"|"reviewer">
```

**推荐提供:**
- `mode`, `agents`, `round_info.participants`

### 4. participants与agents约束关系

**语义区别:**
- `agents`: 讨论整体的所有agents (全局)
- `round_info.participants`: 本轮实际参与的agents (局部)

**约束规则:**
```python
# 规则1: participants必须是agents的子集
assert set(round_info.participants) <= set(agents)

# 规则2: author必须在participants中
assert author in round_info.participants

# 规则3: pre-discuss时只有1个发起者
if round == 0:
    assert len(round_info.participants) == 1
    assert author_role == "initiator"
```

**示例:**
```yaml
agents: ["claude", "codex", "gemini"]
round_info:
  participants: ["codex", "gemini"]  # 子集✓
author: "codex"  # 在participants中✓
```

### 5. pre-discuss轮次语义

**round = 0的特殊含义:**

Pre-discuss是讨论前的需求澄清阶段,由Claude独立完成。

**约束:**
```yaml
round: 0
author: "claude"
author_role: "initiator"
round_info:
  participants: ["claude"]
  total_in_round: 1
mode: "sequential"
```

### 6. 时间格式与时区规范

**强制规范: ISO 8601 UTC**

```yaml
generated_at: "2026-07-21T09:15:30Z"  # 必须以Z结尾
           # YYYY-MM-DDTHH:MM:SSZ
```

**禁止:**
```yaml
generated_at: "2026-07-21 09:15:30"  # ✗ 缺少T和时区
generated_at: "2026-07-21T09:15:30+08:00"  # ✗ 禁止本地时区
```

**解析:**
- Python: `datetime.fromisoformat(timestamp.replace('Z', '+00:00'))`
- 时间范围: UTC 2020-01-01 到 2100-01-01

### 7. discussion_id稳定性保证

**生成算法:**
```python
timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
hash_input = f'{project_name}{topic}{round_num}'.encode()
hash_suffix = hashlib.sha256(hash_input).hexdigest()[:4]
discussion_id = f"disc-{timestamp_str}-{hash_suffix}"
```

**唯一性:**
- 时间部分: 秒级唯一
- 哈希部分: 同秒冲突时区分内容
- 冲突概率: ~1/65536 (同秒同project同topic同round)

**并发冲突处理:**
文件已存在时追加递增后缀: `disc-20260721-091530-a3f2-1`

**稳定性承诺:**
- ID一旦生成不可变更
- 用于跨文件引用
- 删除/移动文件不影响ID语义

### 8. 未知字段兼容策略

**Forward Compatibility:**

解析器必须**忽略**未知字段,不得报错:

```python
metadata = yaml.safe_load(frontmatter)
project = metadata.get('project')  # 已知字段
# metadata可能包含future_field,但不影响解析
```

**添加新字段:**
1. 新字段必须可选
2. 需有合理缺省值
3. 旧版本忽略后功能正常

**破坏性变更(需Major版本):**
- 修改字段类型
- 修改字段语义
- 删除必需字段

---

**文档完成!** 元数据设计v1.2 (v1.1 + 规范与约束补充),满足Codex审核要求。

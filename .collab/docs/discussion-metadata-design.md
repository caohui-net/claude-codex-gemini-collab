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

**文档完成!** 元数据设计v1.1,包含round_info新增字段。

# Artifact Path 规范

**版本:** v1.0  
**创建日期:** 2026-07-22  
**目的:** 定义discussion文件中artifact_path字段的路径规范与命名规则

---

## 1. 路径基准点

**artifact_path的相对路径基准:**

```
基准目录: project_path/.collab/artifacts/
相对路径: 相对于基准目录的路径
```

**示例:**
```yaml
project_path: "/home/user/projects/my-project"
artifact_path: "DISCUSS-topic-123456-r0-claude-20260722.md"

# 完整路径 = project_path/.collab/artifacts/ + artifact_path
# = /home/user/projects/my-project/.collab/artifacts/DISCUSS-topic-123456-r0-claude-20260722.md
```

**约束:**
- artifact_path必须是相对路径(不以`/`开头)
- 禁止目录遍历(`..`符号)
- 禁止包含隐藏文件前缀(`.`)

---

## 2. 命名规则

### 2.1 标准格式

```
DISCUSS-{topic_slug}-{discussion_id_suffix}-discuss-r{round}-{author}-{timestamp}.md
```

**字段说明:**

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| prefix | 固定 | `DISCUSS-` | 文件类型前缀 |
| topic_slug | slug | `代码审核-元数据系统实施` | topic字段的slug化版本 |
| discussion_id_suffix | numeric | `1784687102` | discussion_id中的时间戳部分 |
| round | integer | `r0`, `r1`, `r3` | 轮次标识 |
| author | string | `claude`, `codex`, `gemini` | 作者agent名称 |
| timestamp | datetime | `20260722-022502` | 生成时间(YYYYMMDDm-HHMMSS) |
| extension | 固定 | `.md` | Markdown格式 |

### 2.2 Topic Slug化规则

Topic → topic_slug 转换规则:

1. **截断**: 最多50字符
2. **字符约束**: 保留中文、英文、数字、连字符
3. **空格替换**: 空格→连字符
4. **去重连字符**: 多个连续连字符→单个
5. **修剪**: 去除首尾连字符

**Python实现:**
```python
import re

def slugify_topic(topic: str, max_length: int = 50) -> str:
    """将topic转换为文件名安全的slug"""
    slug = topic[:max_length]
    slug = re.sub(r'[^\w一-龥-]', '-', slug)  # 保留中英文数字连字符
    slug = re.sub(r'-+', '-', slug)  # 去重连字符
    return slug.strip('-')
```

**示例:**
```python
"代码审核: 元数据系统实施 (COMMIT)"
  → "代码审核-元数据系统实施-COMMIT"
  
"Fix bug in authentication flow"
  → "Fix-bug-in-authentication-flow"
```

### 2.3 discussion_id_suffix 提取

从discussion_id提取数字后缀用于文件名:

```python
discussion_id = "disc-20260722-022502-a3f2"
discussion_id_suffix = discussion_id.split('-')[1] + discussion_id.split('-')[2]
# → "20260722022502" 或简化为Unix timestamp
```

**实际使用中的变体:**
- 完整时间戳: `1784687102` (Unix timestamp)
- 日期时间: `20260722-022502`

两种格式均可接受,推荐使用Unix timestamp以确保唯一性。

### 2.4 时间戳格式

文件名中的timestamp字段:

```
格式: YYYYMMDD-HHMMSS
时区: UTC
示例: 20260722-022502 (2026年7月22日 02:25:02 UTC)
```

**与generated_at的关系:**
- generated_at: ISO 8601完整格式 (`2026-07-22T02:25:02Z`)
- timestamp: 紧凑格式,用于文件名

---

## 3. 目录结构约定

### 3.1 当前结构(v1.0)

```
project_path/
└── .collab/
    └── artifacts/
        ├── DISCUSS-topic1-123456-r0-claude-20260722-022502.md
        ├── DISCUSS-topic1-123456-r1-codex-20260722-022534.md
        ├── DISCUSS-topic1-123456-r1-gemini-20260722-022524.md
        └── DISCUSS-topic2-789012-r0-claude-20260722-030000.md
```

**特点:**
- 扁平结构,所有文件在同一目录
- 按文件名排序自然分组(相同discussion_id_suffix前缀)

### 3.2 未来可能的结构(v2.0+)

如果文件数量增长到1000+,可考虑按日期或discussion分组:

**按日期分组:**
```
.collab/artifacts/
├── 2026-07-22/
│   ├── DISCUSS-topic1-123456-r0-claude-022502.md
│   └── DISCUSS-topic1-123456-r1-codex-022534.md
└── 2026-07-23/
    └── DISCUSS-topic2-789012-r0-claude-030000.md
```

**按discussion分组:**
```
.collab/artifacts/
├── disc-20260722-022502-a3f2/
│   ├── r0-claude-20260722-022502.md
│   ├── r1-codex-20260722-022534.md
│   └── r1-gemini-20260722-022524.md
└── disc-20260722-030000-b1c4/
    └── r0-claude-20260722-030000.md
```

**v1.0承诺:**
- 当前保持扁平结构
- artifact_path不包含子目录
- 未来引入子目录时通过Major版本升级

---

## 4. 路径验证规则

### 4.1 安全约束

```python
def validate_artifact_path(artifact_path: str) -> bool:
    """验证artifact_path符合安全规范"""
    # 规则1: 必须是相对路径
    if artifact_path.startswith('/'):
        raise ValueError("artifact_path must be relative path")
    
    # 规则2: 禁止目录遍历
    if '..' in artifact_path:
        raise ValueError("directory traversal not allowed")
    
    # 规则3: 禁止隐藏文件
    if artifact_path.startswith('.'):
        raise ValueError("hidden file prefix not allowed")
    
    # 规则4: 必须是.md文件
    if not artifact_path.endswith('.md'):
        raise ValueError("artifact must be .md file")
    
    return True
```

### 4.2 格式约束

```python
import re

ARTIFACT_PATH_PATTERN = re.compile(
    r'^DISCUSS-[\w一-龥-]+-\d+-discuss-r\d+-[a-z]+-\d{8}-\d{6}\.md$'
)

def validate_artifact_format(artifact_path: str) -> bool:
    """验证artifact_path符合命名格式"""
    return bool(ARTIFACT_PATH_PATTERN.match(artifact_path))
```

### 4.3 文件系统约束

- **最大文件名长度:** 255字节(Linux/macOS限制)
- **禁用字符:** `/` (路径分隔符), `\0` (空字符)
- **建议避免:** `*`, `?`, `<`, `>`, `|`, `:`, `"`, `\` (跨平台兼容性)

---

## 5. 完整示例

### 5.1 Pre-discuss (round=0)

```yaml
# Metadata
project: "claude-codex-gemini-collab"
project_path: "/home/user/projects/claude-codex-gemini-collab"
round: 0
author: "claude"
discussion_id: "disc-20260722-022502-a3f2"
generated_at: "2026-07-22T02:25:02Z"

# Artifact path
artifact_path: "DISCUSS-代码审核-元数据系统实施-COMMIT-1784687102-discuss-r0-claude-20260722-022502.md"

# 完整路径计算
# /home/user/projects/claude-codex-gemini-collab/.collab/artifacts/DISCUSS-代码审核-元数据系统实施-COMMIT-1784687102-discuss-r0-claude-20260722-022502.md
```

### 5.2 Multi-round Discussion (round>=1)

```yaml
# Round 1 - Codex
artifact_path: "DISCUSS-代码审核-元数据系统实施-COMMIT-1784687102-discuss-r1-codex-20260722-022534.md"

# Round 1 - Gemini
artifact_path: "DISCUSS-代码审核-元数据系统实施-COMMIT-1784687102-discuss-r1-gemini-20260722-022524.md"

# Round 3 - Codex
artifact_path: "DISCUSS-代码审核-元数据系统实施-COMMIT-1784687102-discuss-r3-codex-20260722-022733.md"
```

**文件组织特点:**
- 相同discussion_id_suffix前缀 (`1784687102`) → 属于同一讨论
- 不同round编号 (`r0`, `r1`, `r3`) → 标识轮次
- 不同author (`claude`, `codex`, `gemini`) → 区分作者
- 时间戳递增 → 反映生成顺序

### 5.3 路径构建伪代码

```python
def build_artifact_path(
    topic: str,
    discussion_id: str,
    round: int,
    author: str,
    generated_at: str
) -> str:
    """构建artifact_path"""
    # 1. Slugify topic
    topic_slug = slugify_topic(topic, max_length=50)
    
    # 2. Extract discussion_id_suffix (Unix timestamp or datetime)
    parts = discussion_id.split('-')
    discussion_id_suffix = parts[1] + parts[2]  # e.g., "20260722022502"
    
    # 3. Format timestamp (YYYYMMDD-HHMMSS)
    dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
    timestamp = dt.strftime('%Y%m%d-%H%M%S')
    
    # 4. Build filename
    filename = (
        f"DISCUSS-{topic_slug}-{discussion_id_suffix}-"
        f"discuss-r{round}-{author}-{timestamp}.md"
    )
    
    return filename
```

---

## 6. 关键要点总结

### 6.1 路径安全

✅ **必须:**
- 相对路径(不以`/`开头)
- 基准目录: `project_path/.collab/artifacts/`
- 文件扩展名: `.md`

❌ **禁止:**
- 目录遍历(`..`)
- 隐藏文件(`.`前缀)
- 绝对路径

### 6.2 命名一致性

所有artifact文件必须遵循标准格式:
```
DISCUSS-{topic_slug}-{discussion_id_suffix}-discuss-r{round}-{author}-{timestamp}.md
```

### 6.3 版本演进

- **v1.0**: 扁平结构,所有文件在`.collab/artifacts/`
- **v2.0+**: 可能引入子目录(按日期/discussion分组)
- 版本升级时artifact_path格式可能包含路径分隔符

### 6.4 实现建议

1. 使用提供的验证函数确保路径安全
2. Topic slug化时限制长度(推荐50字符)
3. 时间戳统一使用UTC时区
4. discussion_id_suffix可以是Unix timestamp或datetime格式

---

**规范版本:** v1.0  
**状态:** 完成  
**相关文档:** 
- `.collab/docs/discussion-metadata-design.md` (元数据设计)
- `scripts/collab_discuss.py:create_discussion_file_with_metadata()` (实现)

**满足需求:** Codex审核反馈任务4 (定义artifact_path规范)

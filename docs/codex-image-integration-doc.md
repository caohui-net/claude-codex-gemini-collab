# Codex --image参数集成功能说明

## 背景

之前taolun讨论工具使用inject_files()将文件内容嵌入prompt，导致：
- Prompt极大（几十KB到几百KB）
- 处理时间长（360秒超时）
- 无法处理超大文件

## 解决方案

使用Codex CLI原生的`--image`参数直接附加文件：

```bash
echo "prompt" | codex exec --image /path/to/file.md -
```

## 实现细节

### 修改点1：移除inject_files调用

**位置**：agent_cli.py 第231-236行

**原代码**：
```python
if files:
    prompt, needs_multi_turn = inject_files(prompt, base_dir, files)
    if needs_multi_turn:
        print("⚠️  文件过大已分块", file=sys.stderr)
```

**新代码**：
```python
file_paths = []
if files:
    file_paths = [str(base_dir / f) for f in files]
    print(f"📎 [Codex] 附加文件: {len(file_paths)}个", file=sys.stderr, flush=True)
```

### 修改点2：Daemon模式添加--image参数

**位置**：agent_cli.py 第260-264行

在`cmd.append("-")`之前添加：
```python
# 添加文件附件
for file_path in file_paths:
    cmd.extend(["--image", file_path])
```

### 修改点3：Tmux模式添加--image参数

**位置**：agent_cli.py 第386-389行

在`cmd.append("-")`之前添加：
```python
# 添加文件附件
for file_path in file_paths:
    cmd.extend(["--image", file_path])
```

## 验证结果

### 测试1：Markdown文件
- 文件：test-doc.md（3个列表项）
- Token使用：11,507
- 结果：✅ 准确返回"3"

### 测试2：HTML文件
- 文件：test-doc.html（4个列表项）
- Token使用：14,194
- 结果：✅ 准确返回"4"

## 预期效果

| 指标 | 改进 |
|------|------|
| Prompt大小 | ↓ 90%+ |
| 处理速度 | ↑ 50%+ |
| 文件大小限制 | 突破prompt长度限制 |

## 提交记录

- Commit: 9de6b27
- Branch: worktree-fix-agent-type-error
- 日期: 2026-07-19

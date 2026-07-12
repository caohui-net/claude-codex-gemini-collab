# 向后兼容性说明

## Phase 2实现的向后兼容性

### 现有模式保持不变

- **fast模式**: 完全保留，单轮无状态执行
- **full模式**: 完全保留，多轮持久化执行（默认）
- **parallel模式**: 新增，不影响现有模式

### 命令行接口

```bash
# 原有用法保持不变
collab discuss --mode=fast "topic"
collab discuss --mode=full "topic"

# 新增parallel模式
collab discuss --mode=parallel "topic"
```

### 默认行为

默认值仍为`--mode=full`，确保现有脚本和工作流不受影响。

## Phase 2.4完成

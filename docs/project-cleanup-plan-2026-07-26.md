# 项目清理计划

## 执行时间
2026-07-26

## 清理目标
对claude-codex-gemini-collab项目进行整体清理，包括目录分类、文档归总、去除无效文件

## 识别的清理内容

### 1. 根目录散落文档（需归类）
- `agentmemory-integration-plan.md` → 移至 `docs/`
- `codex-image-integration-doc.md` → 移至 `docs/`
- `discussion-reliability-analysis.md` → 移至 `docs/`
- `discussion_ux_proposal.md` → 移至 `docs/`
- `findings.md` → 移至 `docs/archive/`（历史记录）
- `progress.md` → 移至 `docs/archive/`（历史记录）
- `task_plan.md` → 移至 `docs/archive/`（历史记录）
- `WORK_SUMMARY_2026-07-26.md` → 移至 `PRD/`

### 2. 历史讨论artifacts（需归档）
- `.omc/collaboration/artifacts/` 下有数百个 `DISCUSS-*` 文件
- 按日期归档到 `.omc/collaboration/artifacts/archive/2026-06/` 等子目录
- 保留最近30天的讨论文件在主目录

### 3. 历史advisor artifacts（需归档）
- `.omc/artifacts/ask/` 下有大量 codex/gemini advisor artifacts
- 归档到 `.omc/artifacts/ask/archive/`

### 4. 临时分析产物（可删除）
- `.understand-anything/` 整个目录
- 包含 batch-*.json 和临时脚本

### 5. 过时worktree（需检查清理）
- `.claude/worktrees/` 下的已合并分支对应的worktree
- 需要在主项目检查，当前在worktree内

### 6. 其他临时文件
- `.pytest_cache/` 可删除（会自动重建）
- `response.json` 根目录的临时文件
- 各种 `__pycache__/` 目录

## 执行计划

### Phase 1: 文档整理（Task #16）
1. 创建 `docs/archive/` 目录
2. 移动历史文档到archive
3. 移动当前文档到docs/
4. 移动工作总结到PRD/

### Phase 2: 历史artifacts归档（Task #15）
1. 创建归档目录结构
2. 按日期归档DISCUSS文件
3. 归档advisor artifacts

### Phase 3: 清理临时文件（Task #17）
1. 删除 `.understand-anything/`
2. 删除 `.pytest_cache/`
3. 删除临时json文件

### Phase 4: worktree清理（Task #18）
1. 在主项目检查worktree状态
2. 清理已合并分支的worktree

## 注意事项
- 当前在worktree中操作，某些清理需要在主项目执行
- 删除前确认内容不重要
- 重要文档移动而非删除

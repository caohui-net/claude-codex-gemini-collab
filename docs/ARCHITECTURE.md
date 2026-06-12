# 系统架构与模块职责

## 概述

Claude-Codex-Gemini Collaboration (CCG) 框架旨在实现多AI代理间的任务流转、状态共享和协同讨论。本框架由一系列CLI脚本驱动，依赖文件系统作为状态同步媒介，确保在无常驻服务的环境中依然能保证操作的原子性和数据的持久性。

## 模块架构

### 1. 核心协作层 (Core Collaboration)
这是基础流转框架，负责单一任务的派发和交接。
*   `collab_init.py`: 框架初始化。
*   `collab_task.py`: 任务的创建与管理。
*   `collab_execute.py` / `collab_event.py`: 事件日志追溯和执行控制。
*   `collab_state.py`: 核心状态更新，维护项目级别的共享状态。
*   `collab_paths.py`: 统一的项目路径管理（管理 `.collab/` 目录结构）。

### 2. 多代理讨论层 (Discussion Engine)
此模块处理需要多个代理多次交互以达成一致的复杂任务。
*   `collab_discuss.py`: 主协调脚本，控制讨论的多轮次流转。解析代理的回复、管理超时与轮次限制。
*   `collab_state.py` (Round Management): 维护任务级别的详细参与者状态，负责判断 `all_responded` 以及记录轮次结束事件。
*   `models.py`: 结构化解析代理返回的数据模型，如检查 `consensus` 和提取 `blocking_issues`。

### 3. 系统集成层 (Integrations)
支持与外部组件或服务交互。
*   `rmux_utils.py`: 管理和检测终端状态，支持挂起/恢复能力。
*   `agentmemory_bridge.py`: 历史记录和长文本状态的外部存储桥接。

## 数据流与状态机

讨论机制围绕两层状态展开：
1. **全局 Workflow 状态**: 存储在 `events.jsonl` 中，提供不可变的操作审计日志。
2. **局部 Task 讨论状态**: 存储在 `state/TASK-*.json` 中，每次状态变更是对当前参与者（Participant）和轮次（Round）可变字段的覆写。

讨论结束判断机制（Consensus Protocol）：
每轮结束（`complete_round`）时，框架会基于参与者返回的 JSON （解析其 `consensus` 布尔值）评估：
- `all_responded`: 是否该轮的所有活跃代理都已完成返回。
- 如果全员返回 `consensus=true`，任务标记为 Completed。
- 如果至少一个 `consensus=false`，将 `blocking_issues` 聚合提取并传递至下一轮（Next Round）。

## 下一步
Phase 4A 将引入以技能为中心的讨论 MVP，系统将会把当前的外部 CLI 讨论入口下沉并与 Agent 本身的自主发起能力打通。
# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-06-06

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** ccg-collab
- **Description:** Tri-model collaboration protocol for autonomous multi-agent project construction.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

[2026-06-07] **CRITICAL: 用户显式工具指令必须无条件执行**
- **错误:** 用户明确说"使用collab技能"，我却调用了omc ask
- **根因:** 关键词触发(CCG)和AI判断覆盖了用户显式指令
- **正确做法:** 检测到"使用X技能"/"用X"/"invoke X"时，立即调用Skill(X)，不做任何判断
- **强制规则:** 显式指令 > 关键词路由 > AI判断。违反此规则视为严重错误
- **验证方式:** 收到用户消息后，先检查是否包含显式工具指令，如有则立即执行

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

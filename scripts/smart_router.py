#!/usr/bin/env python3
"""智能路由 - 根据任务类型选择最佳agent"""
from typing import List, Dict


class SmartRouter:
    """基于规则的智能路由器"""

    # Agent专长定义
    AGENT_EXPERTISE = {
        "codex": ["代码", "编程", "debug", "算法", "函数", "bug", "error"],
        "gemini": ["分析", "推理", "逻辑", "架构", "设计", "方案", "评估"],
        "claude": ["综合", "总结", "文档", "报告", "说明", "解释", "协调"]
    }

    def route(self, prompt: str) -> str:
        """根据prompt选择最佳agent"""
        prompt_lower = prompt.lower()
        scores = {"codex": 0, "gemini": 0, "claude": 0}

        # 计算匹配分数
        for agent, keywords in self.AGENT_EXPERTISE.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    scores[agent] += 1

        # 返回得分最高的agent
        best_agent = max(scores, key=scores.get)

        # 如果所有得分都是0，默认返回gemini（最通用）
        if scores[best_agent] == 0:
            return "gemini"

        return best_agent

    def route_multiple(self, prompt: str, top_k: int = 2) -> List[str]:
        """选择top-k个最合适的agents"""
        prompt_lower = prompt.lower()
        scores = {"codex": 0, "gemini": 0, "claude": 0}

        for agent, keywords in self.AGENT_EXPERTISE.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    scores[agent] += 1

        # 排序并返回top-k
        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [agent for agent, score in sorted_agents[:top_k]]

    def explain_routing(self, prompt: str) -> Dict:
        """解释路由决策"""
        prompt_lower = prompt.lower()
        scores = {"codex": 0, "gemini": 0, "claude": 0}
        matches = {"codex": [], "gemini": [], "claude": []}

        for agent, keywords in self.AGENT_EXPERTISE.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    scores[agent] += 1
                    matches[agent].append(keyword)

        best_agent = max(scores, key=scores.get)
        if scores[best_agent] == 0:
            best_agent = "gemini"

        return {
            "best_agent": best_agent,
            "scores": scores,
            "matches": matches
        }

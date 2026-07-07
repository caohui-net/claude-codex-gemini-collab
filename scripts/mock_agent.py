#!/usr/bin/env python3
"""Mock agent for testing - 返回简单的测试响应"""
import sys

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mock_agent.py <agent_name> <prompt>", file=sys.stderr)
        sys.exit(1)

    agent_name = sys.argv[1]
    prompt = sys.argv[2]

    # 返回简单的mock响应
    responses = {
        "codex": f"[Codex分析] {prompt[:50]}... (代码角度分析)",
        "gemini": f"[Gemini分析] {prompt[:50]}... (逻辑角度分析)",
        "claude": f"[Claude分析] {prompt[:50]}... (综合角度分析)"
    }

    print(responses.get(agent_name, f"[{agent_name}] Mock response"))

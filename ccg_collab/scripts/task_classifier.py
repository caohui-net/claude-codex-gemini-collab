#!/usr/bin/env python3
"""
Task Classifier - Rule-based classification with confidence scoring

Classification taxonomy:
- ui: UI/style/layout/component work (confidence >= 0.85)
- code: Implementation/logic/API work (confidence >= 0.80)
- audit: Review/verification/quality check (confidence >= 0.90)
- reasoning: Analysis/design/architecture (confidence >= 0.75)
- discussion: Multi-perspective evaluation (confidence >= 0.70)
- mixed: Cross-domain tasks (confidence >= 0.60)
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    task_type: str
    confidence: float
    matched_rules: List[str]
    required_capabilities: List[str]
    risk_level: str


# Capability matrix
CAPABILITY_MATRIX = {
    "claude": ["reasoning", "analysis", "planning", "coordination"],
    "codex": ["code_review", "audit", "verification", "debugging"],
    "gemini": ["ui_design", "ux", "visual", "interaction"],
}

# Task type rules with keywords and confidence thresholds
TASK_TYPE_RULES = {
    "ui": {
        "keywords": ["ui", "界面", "样式", "布局", "组件", "页面", "颜色", "字体", "间距", "响应式", "交互动画", "显示", "展示", "视觉", "用户体验", "交互", "design", "按钮", "button", "表单", "form", "输入", "input", "图标", "icon"],
        "file_patterns": [r"\.css$", r"\.scss$", r"/components/", r"/pages/", r"/styles/"],
        "confidence_threshold": 0.85,
        "required_capabilities": ["ui_design", "ux"],
    },
    "code": {
        "keywords": ["代码", "实现", "功能", "api", "逻辑", "算法", "函数", "方法", "类", "模块"],
        "file_patterns": [r"\.py$", r"\.js$", r"\.ts$", r"\.java$", r"\.go$"],
        "confidence_threshold": 0.80,
        "required_capabilities": ["code_review", "debugging"],
    },
    "audit": {
        "keywords": ["审计", "review", "审查", "验证", "检查", "质量", "测试", "检验"],
        "file_patterns": [],
        "confidence_threshold": 0.90,
        "required_capabilities": ["code_review", "audit", "verification"],
    },
    "reasoning": {
        "keywords": ["分析", "推理", "方案", "决策", "权衡", "架构", "设计", "评估", "研究"],
        "file_patterns": [],
        "confidence_threshold": 0.75,
        "required_capabilities": ["reasoning", "analysis", "planning"],
    },
    "discussion": {
        "keywords": ["讨论", "共识", "评估", "意见", "评价", "考虑"],
        "file_patterns": [],
        "confidence_threshold": 0.70,
        "required_capabilities": ["reasoning", "analysis", "code_review", "ui_design"],
    },
}


def classify_task(description: str, file_paths: Optional[List[str]] = None) -> ClassificationResult:
    """
    Classify task using rule-based matching.

    Returns ClassificationResult with task_type, confidence, matched_rules,
    required_capabilities, and risk_level.
    """
    description_lower = description.lower()
    file_paths = file_paths or []

    scores = {}
    matched_rules = {}

    for task_type, rules in TASK_TYPE_RULES.items():
        score = 0.0
        type_matched_rules = []

        # Keyword matching (0.30 per keyword, up to 3 keywords)
        keyword_matches = 0
        for keyword in rules["keywords"]:
            if keyword in description_lower:
                keyword_matches += 1
                type_matched_rules.append(f"keyword:{keyword}")
        score += min(keyword_matches * 0.30, 0.90)

        # File pattern matching (0.40 per file, up to 2 files)
        file_matches = 0
        for file_path in file_paths:
            for pattern in rules["file_patterns"]:
                if re.search(pattern, file_path):
                    file_matches += 1
                    type_matched_rules.append(f"file_pattern:{pattern}")
                    break  # Only count once per file
        score += min(file_matches * 0.40, 0.80)

        # Normalize score to [0, 1]
        score = min(score, 1.0)

        scores[task_type] = score
        matched_rules[task_type] = type_matched_rules

    # Get best match
    if not scores:
        return ClassificationResult(
            task_type="mixed",
            confidence=0.50,
            matched_rules=["default:fallback"],
            required_capabilities=["reasoning", "code_review"],
            risk_level="medium",
        )

    best_type = max(scores.items(), key=lambda x: x[1])
    task_type, confidence = best_type

    # Check if confidence meets threshold
    threshold = TASK_TYPE_RULES[task_type]["confidence_threshold"]
    if confidence < threshold:
        # Fallback to mixed if below threshold
        task_type = "mixed"
        confidence = max(0.60, confidence)

    # Assess risk level
    risk_level = _assess_risk_level(description, file_paths)

    return ClassificationResult(
        task_type=task_type,
        confidence=confidence,
        matched_rules=matched_rules.get(task_type, []),
        required_capabilities=TASK_TYPE_RULES.get(task_type, {}).get("required_capabilities", []),
        risk_level=risk_level,
    )


def _assess_risk_level(description: str, file_paths: List[str]) -> str:
    """Assess risk level based on description and files."""
    description_lower = description.lower()

    # High risk indicators
    high_risk_keywords = ["架构", "architecture", "database", "数据库", "migration", "迁移", "删除", "delete"]
    if any(keyword in description_lower for keyword in high_risk_keywords):
        return "high"

    # Medium risk: multiple files
    if len(file_paths) > 3:
        return "medium"

    # Default: low risk
    return "low"


def route_to_agents(classification: ClassificationResult) -> List[str]:
    """
    Determine which agents should handle the task based on classification.

    Returns list of agent names.
    """
    task_type = classification.task_type

    # Direct mapping
    routing_map = {
        "ui": ["gemini"],
        "code": ["codex"],
        "audit": ["codex"],
        "reasoning": ["claude"],
        "discussion": ["claude", "codex", "gemini"],
        "mixed": ["claude", "codex"],  # Claude coordinates, Codex helps
    }

    return routing_map.get(task_type, ["claude"])

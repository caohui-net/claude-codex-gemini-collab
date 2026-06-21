"""Agent-skills技能加载器 - Prompt注入模式"""
import re
from pathlib import Path

SKILLS_DIR = Path.home() / ".claude/skills/agent-skills"

def load_skill_prompt(skill_name):
    """加载技能Markdown并提取工作流"""
    # 尝试多个可能的路径
    paths = [
        SKILLS_DIR / "define" / f"{skill_name}.md",
        SKILLS_DIR / "build" / f"{skill_name}.md",
        SKILLS_DIR / "review" / f"{skill_name}.md",
    ]

    for path in paths:
        if path.exists():
            content = path.read_text(encoding='utf-8')
            return extract_workflow(content)

    return None  # 降级：技能不存在

def extract_workflow(markdown):
    """提取工作流section"""
    # 匹配中英文工作流标题
    match = re.search(r'##\s*(工作流|Workflow)\s*\n(.*?)(?=\n##|$)', markdown, re.DOTALL)
    if match:
        return match.group(2).strip()

    # 降级：返回整个文档（去除frontmatter）
    no_frontmatter = re.sub(r'^---\n.*?\n---\n', '', markdown, flags=re.DOTALL)
    return no_frontmatter.strip()

def topic_is_vague(topic):
    """检测topic是否模糊需要澄清"""
    vague_words = ["整合", "优化", "改进", "分析", "讨论", "研究"]

    # 技术关键词表明topic具体
    tech_keywords = ["实现", "修复", "JWT", "API", "bug", "src/", ".py", ".ts", "函数", "class", "第", "行"]
    has_tech = any(kw in topic for kw in tech_keywords)

    # 有技术关键词→具体topic
    if has_tech:
        return False

    # 只有模糊词+短→vague
    has_vague = any(word in topic for word in vague_words)
    return len(topic) < 30 or (has_vague and len(topic) < 50)

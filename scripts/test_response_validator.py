"""测试响应验证器"""
from agent_response_validator import validate_response


def test_dangerous_command():
    resp = {"content": "rm -rf /", "consensus": True}
    result = validate_response(resp, "test")
    assert result["consensus"] == False
    assert "安全风险" in result["blocking_issues"][0]
    print("✓ 危险命令拦截")


def test_long_citation():
    long_quote = " ".join(["word"] * 20)
    resp = {"content": f'"{long_quote}"', "consensus": True}
    result = validate_response(resp, "test")
    assert "引用过长" in str(result.get("blocking_issues", []))
    print("✓ 长引用检测")


def test_safe_content():
    resp = {"content": "分析完成", "consensus": True}
    result = validate_response(resp, "test")
    assert result["consensus"] == True
    print("✓ 安全内容通过")


if __name__ == "__main__":
    test_dangerous_command()
    test_long_citation()
    test_safe_content()
    print("\n✅ 所有测试通过")

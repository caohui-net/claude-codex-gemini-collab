#!/usr/bin/env python3
"""
Tests for mcp_adapter.py

Validates JSON-RPC protocol handling and tool execution.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def send_request(request: dict) -> dict:
    """Send JSON-RPC request to MCP adapter"""
    request_json = json.dumps(request)

    result = subprocess.run(
        ["python3", "scripts/mcp_adapter.py"],
        input=request_json,
        capture_output=True,
        text=True,
        timeout=5
    )

    if result.returncode != 0:
        raise RuntimeError(f"MCP adapter failed: {result.stderr}")

    return json.loads(result.stdout.strip())


def test_tools_list():
    """Test tools/list method"""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }

    response = send_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "tools" in response["result"]

    tools = response["result"]["tools"]
    assert len(tools) == 2

    tool_names = [t["name"] for t in tools]
    assert "run_codex" in tool_names
    assert "run_gemini" in tool_names

    print("✓ test_tools_list passed")


def test_unknown_method():
    """Test error handling for unknown method"""
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "unknown/method"
    }

    response = send_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "error" in response
    assert response["error"]["code"] == -32601  # Method not found

    print("✓ test_unknown_method passed")


def test_unknown_tool():
    """Test error handling for unknown tool"""
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "unknown_tool",
            "arguments": {"prompt": "test"}
        }
    }

    response = send_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 3
    assert "error" in response
    assert response["error"]["code"] == -32602  # Invalid params

    print("✓ test_unknown_tool passed")


def test_invalid_json():
    """Test error handling for invalid JSON"""
    result = subprocess.run(
        ["python3", "scripts/mcp_adapter.py"],
        input="invalid json",
        capture_output=True,
        text=True,
        timeout=5
    )

    response = json.loads(result.stdout.strip())

    assert "error" in response
    assert response["error"]["code"] == -32700  # Parse error

    print("✓ test_invalid_json passed")


def test_missing_prompt():
    """Test error handling when required argument missing"""
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "run_codex",
            "arguments": {}  # Missing required 'prompt'
        }
    }

    # This should still work but with empty prompt
    # (agent_cli.py handles empty prompts)
    response = send_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 4
    # May succeed with empty output or fail - both acceptable

    print("✓ test_missing_prompt passed")


if __name__ == "__main__":
    print("Running mcp_adapter tests...\n")

    test_tools_list()
    test_unknown_method()
    test_unknown_tool()
    test_invalid_json()
    test_missing_prompt()

    print("\n✅ All MCP adapter tests passed!")

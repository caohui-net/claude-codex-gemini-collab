#!/usr/bin/env python3
"""
MCP Adapter for Codex/Gemini CLIs

Wraps existing agent CLIs with Model Context Protocol (MCP) stdio interface.
Minimal implementation focusing on core functionality.

Usage:
    # As MCP server
    python3 scripts/mcp_adapter.py

    # Send JSON-RPC request via stdin
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 scripts/mcp_adapter.py
"""

import json
import sys
import subprocess
from typing import Dict, Any, List, Optional


class MCPAdapter:
    """MCP stdio adapter for agent CLIs"""

    def __init__(self):
        self.tools = {
            "run_codex": {
                "description": "Execute Codex agent with given prompt",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Prompt for Codex"}
                    },
                    "required": ["prompt"]
                }
            },
            "run_gemini": {
                "description": "Execute Gemini agent with given prompt",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Prompt for Gemini"}
                    },
                    "required": ["prompt"]
                }
            }
        }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle JSON-RPC request"""
        method = request.get("method")
        request_id = request.get("id")

        if method == "tools/list":
            return self._tools_list(request_id)
        elif method == "tools/call":
            return self._tools_call(request_id, request.get("params", {}))
        else:
            return self._error(request_id, -32601, f"Method not found: {method}")

    def _tools_list(self, request_id: int) -> Dict[str, Any]:
        """Return list of available tools"""
        tools_list = [
            {"name": name, **meta}
            for name, meta in self.tools.items()
        ]
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools_list}
        }

    def _tools_call(self, request_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return self._error(request_id, -32602, f"Unknown tool: {tool_name}")

        try:
            if tool_name == "run_codex":
                result = self._run_codex(arguments.get("prompt", ""))
            elif tool_name == "run_gemini":
                result = self._run_gemini(arguments.get("prompt", ""))
            else:
                return self._error(request_id, -32603, f"Tool not implemented: {tool_name}")

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        except Exception as e:
            return self._error(request_id, -32603, f"Tool execution failed: {str(e)}")

    def _run_codex(self, prompt: str) -> str:
        """Execute Codex CLI"""
        result = subprocess.run(
            ["python3", "scripts/agent_cli.py", "run_codex", prompt],
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            raise RuntimeError(f"Codex failed: {result.stderr}")

        return result.stdout.strip()

    def _run_gemini(self, prompt: str) -> str:
        """Execute Gemini CLI"""
        result = subprocess.run(
            ["python3", "scripts/agent_cli.py", "run_gemini", prompt],
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            raise RuntimeError(f"Gemini failed: {result.stderr}")

        return result.stdout.strip()

    def _error(self, request_id: int, code: int, message: str) -> Dict[str, Any]:
        """Create JSON-RPC error response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


def main():
    """Main entry point - read requests from stdin, write responses to stdout"""
    adapter = MCPAdapter()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = adapter.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()

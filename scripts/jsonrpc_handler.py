#!/usr/bin/env python3
"""
JSON-RPC 2.0 Handler
替代当前的5层markdown解析fallback
"""
import json
from typing import Any, Dict, Optional, Callable


class JSONRPCError(Exception):
    """JSON-RPC错误基类"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")


class JSONRPCHandler:
    """JSON-RPC 2.0请求处理器"""

    # 标准错误码
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    def __init__(self):
        self.methods: Dict[str, Callable] = {}

    def register(self, method_name: str, func: Callable):
        """注册可调用方法"""
        self.methods[method_name] = func

    def handle_request(self, request_str: str) -> str:
        """
        处理JSON-RPC请求

        Args:
            request_str: JSON-RPC请求字符串

        Returns:
            JSON-RPC响应字符串
        """
        try:
            # 解析请求
            req = json.loads(request_str)

            # 验证JSON-RPC版本
            if req.get("jsonrpc") != "2.0":
                return self._error_response(
                    req.get("id"),
                    self.INVALID_REQUEST,
                    "Invalid JSON-RPC version"
                )

            # 验证必需字段
            if "method" not in req:
                return self._error_response(
                    req.get("id"),
                    self.INVALID_REQUEST,
                    "Missing 'method' field"
                )

            # 查找方法
            method = self.methods.get(req["method"])
            if not method:
                return self._error_response(
                    req["id"],
                    self.METHOD_NOT_FOUND,
                    f"Method '{req['method']}' not found"
                )

            # 调用方法
            params = req.get("params", {})
            if isinstance(params, dict):
                result = method(**params)
            elif isinstance(params, list):
                result = method(*params)
            else:
                return self._error_response(
                    req["id"],
                    self.INVALID_PARAMS,
                    "Params must be object or array"
                )

            # 返回成功响应
            return json.dumps({
                "jsonrpc": "2.0",
                "result": result,
                "id": req["id"]
            }, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return self._error_response(
                None,
                self.PARSE_ERROR,
                f"Parse error: {str(e)}"
            )

        except JSONRPCError as e:
            return self._error_response(
                req.get("id"),
                e.code,
                e.message,
                e.data
            )

        except Exception as e:
            return self._error_response(
                req.get("id"),
                self.INTERNAL_ERROR,
                f"Internal error: {str(e)}"
            )

    def _error_response(self, req_id: Optional[Any],
                       code: int, message: str,
                       data: Any = None) -> str:
        """生成错误响应"""
        error_obj = {
            "code": code,
            "message": message
        }
        if data is not None:
            error_obj["data"] = data

        return json.dumps({
            "jsonrpc": "2.0",
            "error": error_obj,
            "id": req_id
        }, ensure_ascii=False)

    @staticmethod
    def create_request(method: str, params: Any = None,
                      req_id: Any = "1") -> str:
        """
        创建JSON-RPC请求（工具函数）

        Args:
            method: 方法名
            params: 参数（dict或list）
            req_id: 请求ID

        Returns:
            JSON-RPC请求字符串
        """
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id
        }
        if params is not None:
            req["params"] = params

        return json.dumps(req, ensure_ascii=False)

    @staticmethod
    def parse_response(response_str: str) -> Dict[str, Any]:
        """
        解析JSON-RPC响应（工具函数）

        Args:
            response_str: JSON-RPC响应字符串

        Returns:
            解析后的响应dict

        Raises:
            JSONRPCError: 如果响应包含错误
        """
        resp = json.loads(response_str)

        if "error" in resp:
            raise JSONRPCError(
                code=resp["error"]["code"],
                message=resp["error"]["message"],
                data=resp["error"].get("data")
            )

        return resp.get("result")


# 向后兼容：markdown解析fallback
def parse_markdown_json(text: str) -> dict:
    """
    5层markdown解析fallback（向后兼容）
    尝试解析markdown包裹的JSON
    """
    # Layer 1: ```json\n
    if text.startswith("```json\n"):
        text = text[8:]
    # Layer 2: ```json
    elif text.startswith("```json"):
        text = text[7:]
    # Layer 3: ```\n
    elif text.startswith("```\n"):
        text = text[4:]
    # Layer 4: ```
    elif text.startswith("```"):
        text = text[3:]

    # Layer 5: ending ```
    if text.endswith("\n```"):
        text = text[:-4]
    elif text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())


if __name__ == "__main__":
    # 测试用例
    handler = JSONRPCHandler()

    # 注册测试方法
    def echo(message: str) -> str:
        return f"Echo: {message}"

    def add(a: int, b: int) -> int:
        return a + b

    handler.register("echo", echo)
    handler.register("add", add)

    # 测试1: 正常请求
    req1 = JSONRPCHandler.create_request("echo", {"message": "Hello"}, "req-1")
    resp1 = handler.handle_request(req1)
    print("Test 1:", resp1)

    # 测试2: 方法未找到
    req2 = JSONRPCHandler.create_request("unknown", {}, "req-2")
    resp2 = handler.handle_request(req2)
    print("Test 2:", resp2)

    # 测试3: 解析错误
    req3 = "invalid json"
    resp3 = handler.handle_request(req3)
    print("Test 3:", resp3)

    # 测试4: 数组参数
    req4 = JSONRPCHandler.create_request("add", [10, 20], "req-4")
    resp4 = handler.handle_request(req4)
    print("Test 4:", resp4)

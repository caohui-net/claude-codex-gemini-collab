#!/usr/bin/env python3
"""A2A消息路由器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from a2a_protocol import A2AMessage
from typing import Dict, Callable, List


class A2ARouter:
    """简单的A2A消息路由器"""

    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = {}

    def register(self, receiver: str, handler: Callable):
        """注册消息处理器"""
        if receiver not in self.handlers:
            self.handlers[receiver] = []
        self.handlers[receiver].append(handler)

    def route(self, message: A2AMessage) -> bool:
        """路由消息到接收者"""
        if message.receiver not in self.handlers:
            return False

        for handler in self.handlers[message.receiver]:
            try:
                handler(message)
            except Exception as e:
                print(f"⚠️  Handler error: {e}", file=sys.stderr)
                return False
        return True

    def broadcast(self, message: A2AMessage):
        """广播消息到所有agent"""
        for receiver_handlers in self.handlers.values():
            for handler in receiver_handlers:
                try:
                    handler(message)
                except Exception as e:
                    print(f"⚠️  Broadcast error: {e}", file=sys.stderr)

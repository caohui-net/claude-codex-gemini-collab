#!/usr/bin/env python3
"""Agent-to-Agent (A2A) 通信协议"""
import json
from typing import Dict, Optional, Callable
from datetime import datetime
from pathlib import Path


class A2AMessage:
    """A2A消息"""

    def __init__(self, msg_type: str, sender: str, receiver: str, content: dict):
        self.msg_type = msg_type  # request, response, event
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.timestamp = datetime.now().isoformat()
        self.msg_id = f"{sender}-{receiver}-{datetime.now().timestamp()}"

    def to_dict(self) -> dict:
        return {
            "msg_type": self.msg_type,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp,
            "msg_id": self.msg_id
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "A2AMessage":
        data = json.loads(json_str)
        msg = cls(
            msg_type=data["msg_type"],
            sender=data["sender"],
            receiver=data["receiver"],
            content=data["content"]
        )
        msg.timestamp = data.get("timestamp", msg.timestamp)
        msg.msg_id = data.get("msg_id", msg.msg_id)
        return msg

#!/usr/bin/env python3
"""P0组件单元测试"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / ".collab"))

from jsonrpc_handler import JSONRPCHandler
from chunker import MarkdownChunker
from state_manager import StateManager
from file_injector import inject_files


class TestJSONRPCHandler:
    def test_echo_method(self):
        handler = JSONRPCHandler()
        handler.register("echo", lambda msg: msg)

        request = json.dumps({"jsonrpc": "2.0", "method": "echo", "params": {"msg": "hello"}, "id": 1})
        response = json.loads(handler.handle_request(request))

        assert response["jsonrpc"] == "2.0"
        assert response["result"] == "hello"

    def test_method_not_found(self):
        handler = JSONRPCHandler()
        request = json.dumps({"jsonrpc": "2.0", "method": "unknown", "params": {}, "id": 2})
        response = json.loads(handler.handle_request(request))

        assert "error" in response
        assert response["error"]["code"] == -32601


class TestMarkdownChunker:
    def test_small_text(self):
        chunker = MarkdownChunker(max_chars=100, overlap_chars=20)
        chunks = chunker.chunk("短文本")
        assert len(chunks) == 1

    def test_large_text(self):
        chunker = MarkdownChunker(max_chars=50, overlap_chars=10)
        text = "## 章节1\n" + "内容" * 20 + "\n\n## 章节2\n" + "内容" * 20
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2


class TestStateManager:
    def test_workflow_save_recover(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = StateManager(str(Path(tmpdir) / "test.db"))
            sm.save_workflow("wf-1", "running", "step1", {"key": "value"})
            wf = sm.recover_workflow("wf-1")
            assert wf["workflow_id"] == "wf-1"
            assert wf["status"] == "running"


class TestFileInjector:
    def test_inject_small_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# 测试内容")

            result, multi = inject_files("请分析", Path(tmpdir), ["test.md"])
            assert not multi
            assert "测试内容" in result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

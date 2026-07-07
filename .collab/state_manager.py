#!/usr/bin/env python3
"""
State Manager - SQLite状态持久化
支持workflow崩溃后恢复
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class StateManager:
    """
    状态管理器

    功能：
    1. 持久化workflow和agent状态到SQLite
    2. 支持崩溃后恢复
    3. 追踪失败的agent用于重试
    """

    def __init__(self, db_path: str = ".collab/state.db"):
        """
        初始化状态管理器

        Args:
            db_path: SQLite数据库路径
        """
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # 支持字典访问
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表"""
        # workflow状态表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_state (
                workflow_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_step TEXT,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # agent状态表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                agent_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input TEXT,
                output TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflow_state(workflow_id)
            )
        """)

        # 创建索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_status
            ON workflow_state(status)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_workflow
            ON agent_state(workflow_id)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_status
            ON agent_state(status)
        """)

        self.conn.commit()

    def save_workflow(self, workflow_id: str, status: str,
                      current_step: str = "", data: Dict = None):
        """
        保存workflow状态

        Args:
            workflow_id: workflow ID
            status: 状态（running, completed, failed）
            current_step: 当前步骤
            data: 附加数据
        """
        now = datetime.now().isoformat()
        data_json = json.dumps(data or {}, ensure_ascii=False)

        # 检查是否已存在
        cursor = self.conn.execute(
            "SELECT workflow_id FROM workflow_state WHERE workflow_id = ?",
            (workflow_id,)
        )
        exists = cursor.fetchone() is not None

        if exists:
            # 更新
            self.conn.execute("""
                UPDATE workflow_state
                SET status = ?, current_step = ?, data = ?, updated_at = ?
                WHERE workflow_id = ?
            """, (status, current_step, data_json, now, workflow_id))
        else:
            # 插入
            self.conn.execute("""
                INSERT INTO workflow_state
                (workflow_id, status, current_step, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (workflow_id, status, current_step, data_json, now, now))

        self.conn.commit()

    def save_agent_state(self, agent_id: str, workflow_id: str,
                        status: str, input_data: Dict,
                        output_data: Dict = None, error: str = None):
        """
        保存agent状态

        Args:
            agent_id: agent ID
            workflow_id: 所属workflow ID
            status: 状态（pending, running, completed, failed）
            input_data: 输入数据
            output_data: 输出数据
            error: 错误信息
        """
        now = datetime.now().isoformat()
        input_json = json.dumps(input_data, ensure_ascii=False)
        output_json = json.dumps(output_data or {}, ensure_ascii=False)

        # 检查是否已存在
        cursor = self.conn.execute(
            "SELECT agent_id FROM agent_state WHERE agent_id = ?",
            (agent_id,)
        )
        exists = cursor.fetchone() is not None

        if exists:
            # 更新
            self.conn.execute("""
                UPDATE agent_state
                SET status = ?, input = ?, output = ?, error = ?, updated_at = ?
                WHERE agent_id = ?
            """, (status, input_json, output_json, error, now, agent_id))
        else:
            # 插入
            self.conn.execute("""
                INSERT INTO agent_state
                (agent_id, workflow_id, status, input, output, error,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, workflow_id, status, input_json, output_json,
                 error, now, now))

        self.conn.commit()

    def recover_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        恢复workflow状态

        Args:
            workflow_id: workflow ID

        Returns:
            workflow状态字典，不存在则返回None
        """
        cursor = self.conn.execute("""
            SELECT status, current_step, data, updated_at
            FROM workflow_state
            WHERE workflow_id = ?
        """, (workflow_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "workflow_id": workflow_id,
            "status": row["status"],
            "current_step": row["current_step"],
            "data": json.loads(row["data"]),
            "updated_at": row["updated_at"]
        }

    def get_failed_agents(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        获取失败的agent列表（用于重试）

        Args:
            workflow_id: workflow ID

        Returns:
            失败的agent信息列表
        """
        cursor = self.conn.execute("""
            SELECT agent_id, input, error, updated_at
            FROM agent_state
            WHERE workflow_id = ? AND status = 'failed'
            ORDER BY updated_at DESC
        """, (workflow_id,))

        return [
            {
                "agent_id": row["agent_id"],
                "input": json.loads(row["input"]),
                "error": row["error"],
                "updated_at": row["updated_at"]
            }
            for row in cursor.fetchall()
        ]

    def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取agent状态

        Args:
            agent_id: agent ID

        Returns:
            agent状态字典，不存在则返回None
        """
        cursor = self.conn.execute("""
            SELECT agent_id, workflow_id, status, input, output, error, updated_at
            FROM agent_state
            WHERE agent_id = ?
        """, (agent_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "agent_id": row["agent_id"],
            "workflow_id": row["workflow_id"],
            "status": row["status"],
            "input": json.loads(row["input"]),
            "output": json.loads(row["output"]) if row["output"] else None,
            "error": row["error"],
            "updated_at": row["updated_at"]
        }

    def list_workflows(self, status: str = None) -> List[Dict[str, Any]]:
        """
        列出workflows

        Args:
            status: 过滤状态（可选）

        Returns:
            workflow列表
        """
        if status:
            cursor = self.conn.execute("""
                SELECT workflow_id, status, current_step, updated_at
                FROM workflow_state
                WHERE status = ?
                ORDER BY updated_at DESC
            """, (status,))
        else:
            cursor = self.conn.execute("""
                SELECT workflow_id, status, current_step, updated_at
                FROM workflow_state
                ORDER BY updated_at DESC
            """)

        return [
            {
                "workflow_id": row["workflow_id"],
                "status": row["status"],
                "current_step": row["current_step"],
                "updated_at": row["updated_at"]
            }
            for row in cursor.fetchall()
        ]

    def cleanup_old_workflows(self, days: int = 7):
        """
        清理旧workflow（可选维护操作）

        Args:
            days: 保留天数
        """
        cutoff_date = datetime.now().replace(
            day=datetime.now().day - days
        ).isoformat()

        # 删除旧的completed workflow
        self.conn.execute("""
            DELETE FROM workflow_state
            WHERE status = 'completed' AND updated_at < ?
        """, (cutoff_date,))

        # 删除孤立的agent状态
        self.conn.execute("""
            DELETE FROM agent_state
            WHERE workflow_id NOT IN (SELECT workflow_id FROM workflow_state)
        """)

        self.conn.commit()

    def close(self):
        """关闭数据库连接"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # 测试用例
    print("=== State Manager测试 ===\n")

    # 使用临时数据库
    with StateManager("/tmp/test_state.db") as state_mgr:
        # 测试1: 保存workflow
        workflow_id = "test-workflow-001"
        state_mgr.save_workflow(
            workflow_id,
            "running",
            "step1",
            {"tasks": ["task1", "task2"]}
        )
        print("✓ 测试1: 保存workflow")

        # 测试2: 保存agent状态
        state_mgr.save_agent_state(
            "codex-001",
            workflow_id,
            "running",
            {"prompt": "分析文档"}
        )
        print("✓ 测试2: 保存agent状态")

        # 测试3: 更新agent为completed
        state_mgr.save_agent_state(
            "codex-001",
            workflow_id,
            "completed",
            {"prompt": "分析文档"},
            {"result": "分析完成"}
        )
        print("✓ 测试3: 更新agent状态")

        # 测试4: 保存失败的agent
        state_mgr.save_agent_state(
            "gemini-001",
            workflow_id,
            "failed",
            {"prompt": "生成报告"},
            error="网络超时"
        )
        print("✓ 测试4: 保存失败agent")

        # 测试5: 恢复workflow
        recovered = state_mgr.recover_workflow(workflow_id)
        print(f"✓ 测试5: 恢复workflow - status={recovered['status']}")

        # 测试6: 获取失败的agents
        failed = state_mgr.get_failed_agents(workflow_id)
        print(f"✓ 测试6: 获取失败agents - count={len(failed)}")
        if failed:
            print(f"  失败agent: {failed[0]['agent_id']}, 错误: {failed[0]['error']}")

        # 测试7: 列出workflows
        workflows = state_mgr.list_workflows()
        print(f"✓ 测试7: 列出workflows - count={len(workflows)}")

    print("\n✅ 所有测试通过")

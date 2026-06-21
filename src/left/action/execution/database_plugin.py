"""
数据库操作插件

第一性原理：结构化数据持久化是复杂系统的基石
- 连接：建立与数据库的可靠连接
- 查询：从数据库获取信息
- 写入：将信息持久化到数据库
- 事务：保证数据一致性

类比：生物的"长期记忆"——将经验结构化存储，随时提取
"""

import time
import logging
import sqlite3
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class DatabasePlugin(PluginBase):
    """
    数据库操作插件（SQLite实现）

    支持：连接、查询、执行、事务
    """

    def __init__(self) -> None:
        meta = PluginMetadata(
            name="database_plugin",
            version="1.0.0",
            plugin_type=PluginType.DATABASE,
            capabilities=[
                PluginCapability.QUERY,
                PluginCapability.WRITE,
                PluginCapability.CONNECT,
            ],
            description="数据库操作插件，支持SQLite",
        )
        super().__init__(meta)
        self.db_path: str = ":memory:"
        self._connection: Optional[sqlite3.Connection] = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        self.db_path = config.get("db_path", ":memory:")
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialized = True
        return True

    def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized or self._connection is None:
            return False
        try:
            self._connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行数据库操作"""
        start = time.time()
        try:
            result = self._dispatch(action, params)
            result.execution_time = time.time() - start
            return result
        except Exception as e:
            return PluginResult(
                success=False,
                message=str(e),
                execution_time=time.time() - start,
            )

    def _dispatch(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """分发到具体动作"""
        if action == "query":
            return self._action_query(params)
        if action == "execute":
            return self._action_execute(params)
        if action == "executemany":
            return self._action_executemany(params)
        if action == "transaction":
            return self._action_transaction(params)
        if action == "create_table":
            return self._action_create_table(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _action_query(self, params: Dict[str, Any]) -> PluginResult:
        """执行查询"""
        sql = params.get("sql", "")
        if not sql:
            raise ValueError("sql is required")
        parameters = params.get("parameters", ())
        cursor = self._connection.execute(sql, parameters)
        rows = [dict(row) for row in cursor.fetchall()]
        return PluginResult(
            success=True,
            message=f"Query returned {len(rows)} rows",
            data={"rows": rows, "columns": [desc[0] for desc in cursor.description] if rows else []},
        )

    def _action_execute(self, params: Dict[str, Any]) -> PluginResult:
        """执行SQL"""
        sql = params.get("sql", "")
        if not sql:
            raise ValueError("sql is required")
        parameters = params.get("parameters", ())
        cursor = self._connection.execute(sql, parameters)
        self._connection.commit()
        return PluginResult(
            success=True,
            message=f"Executed, rows affected: {cursor.rowcount}",
            data={"rowcount": cursor.rowcount, "lastrowid": cursor.lastrowid},
        )

    def _action_executemany(self, params: Dict[str, Any]) -> PluginResult:
        """批量执行"""
        sql = params.get("sql", "")
        if not sql:
            raise ValueError("sql is required")
        parameters_list = params.get("parameters_list", [])
        cursor = self._connection.executemany(sql, parameters_list)
        self._connection.commit()
        return PluginResult(
            success=True,
            message=f"Executed {len(parameters_list)} batches",
            data={"rowcount": cursor.rowcount},
        )

    def _action_transaction(self, params: Dict[str, Any]) -> PluginResult:
        """执行事务"""
        statements = params.get("statements", [])
        try:
            with self._connection:
                for stmt in statements:
                    self._connection.execute(stmt["sql"], stmt.get("parameters", ()))
            return PluginResult(
                success=True,
                message=f"Transaction committed with {len(statements)} statements",
            )
        except sqlite3.Error as e:
            return PluginResult(
                success=False,
                message=f"Transaction failed: {e}",
            )

    def _action_create_table(self, params: Dict[str, Any]) -> PluginResult:
        """创建表"""
        table_name = params.get("table_name", "")
        columns = params.get("columns", {})
        if not table_name or not columns:
            raise ValueError("table_name and columns are required")
        sql = self._build_create_sql(table_name, columns)
        return self._execute_ddl(sql, table_name)

    def _build_create_sql(self, table_name: str, columns: Dict[str, str]) -> str:
        """构建建表SQL"""
        col_defs = ", ".join(f"{name} {dtype}" for name, dtype in columns.items())
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})"

    def _execute_ddl(self, sql: str, table_name: str) -> PluginResult:
        """执行DDL"""
        self._connection.execute(sql)
        self._connection.commit()
        return PluginResult(success=True, message=f"Table {table_name} created")

    def shutdown(self) -> None:
        """关闭连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
        super().shutdown()

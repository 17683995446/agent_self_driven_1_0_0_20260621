"""
数据库插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
import tempfile
import os

from src.left.action.execution.database_plugin import DatabasePlugin


class TestDatabasePlugin:
    """数据库插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = DatabasePlugin()
        p.initialize({"db_path": ":memory:"})
        return p

    def test_initialize(self):
        """测试初始化"""
        p = DatabasePlugin()
        assert p.initialize({"db_path": ":memory:"}) is True
        assert p.health_check() is True

    def test_initialize_default(self):
        """测试默认初始化"""
        p = DatabasePlugin()
        assert p.initialize({}) is True
        assert p.db_path == ":memory:"

    def test_health_check_not_initialized(self):
        """测试未初始化健康检查"""
        p = DatabasePlugin()
        assert p.health_check() is False

    def test_create_table_normal(self, plugin):
        """测试正常创建表"""
        result = plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        assert result.success is True
        assert "users" in result.message

    def test_create_table_empty_name(self, plugin):
        """测试空表名"""
        result = plugin.execute("create_table", {
            "table_name": "",
            "columns": {"id": "INTEGER"}
        })
        assert result.success is False

    def test_create_table_empty_columns(self, plugin):
        """测试空列定义"""
        result = plugin.execute("create_table", {
            "table_name": "test",
            "columns": {}
        })
        assert result.success is False

    def test_execute_insert(self, plugin):
        """测试执行插入"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        result = plugin.execute("execute", {
            "sql": "INSERT INTO users (name) VALUES (?)",
            "parameters": ("Alice",)
        })
        assert result.success is True
        assert result.data["rowcount"] == 1

    def test_execute_empty_sql(self, plugin):
        """测试空SQL"""
        result = plugin.execute("execute", {"sql": ""})
        assert result.success is False

    def test_query_normal(self, plugin):
        """测试正常查询"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        plugin.execute("execute", {
            "sql": "INSERT INTO users (name) VALUES (?)",
            "parameters": ("Bob",)
        })
        result = plugin.execute("query", {"sql": "SELECT * FROM users"})
        assert result.success is True
        assert len(result.data["rows"]) == 1
        assert result.data["rows"][0]["name"] == "Bob"

    def test_query_empty_sql(self, plugin):
        """测试空查询SQL"""
        result = plugin.execute("query", {"sql": ""})
        assert result.success is False

    def test_query_no_results(self, plugin):
        """测试无结果查询"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        result = plugin.execute("query", {"sql": "SELECT * FROM users WHERE 1=0"})
        assert result.success is True
        assert result.data["rows"] == []

    def test_executemany_normal(self, plugin):
        """测试批量执行"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        result = plugin.execute("executemany", {
            "sql": "INSERT INTO users (name) VALUES (?)",
            "parameters_list": [("A",), ("B",), ("C",)]
        })
        assert result.success is True

    def test_executemany_empty(self, plugin):
        """测试空批量执行"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        result = plugin.execute("executemany", {
            "sql": "INSERT INTO users (name) VALUES (?)",
            "parameters_list": []
        })
        assert result.success is True

    def test_transaction_normal(self, plugin):
        """测试正常事务"""
        plugin.execute("create_table", {
            "table_name": "users",
            "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT"}
        })
        result = plugin.execute("transaction", {
            "statements": [
                {"sql": "INSERT INTO users (name) VALUES ('Alice')"},
                {"sql": "INSERT INTO users (name) VALUES ('Bob')"},
            ]
        })
        assert result.success is True

    def test_transaction_failure(self, plugin):
        """测试失败事务"""
        result = plugin.execute("transaction", {
            "statements": [
                {"sql": "INVALID SQL"},
            ]
        })
        assert result.success is False

    def test_transaction_empty(self, plugin):
        """测试空事务"""
        result = plugin.execute("transaction", {"statements": []})
        assert result.success is True

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message

    def test_persistence(self):
        """测试持久化"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            p = DatabasePlugin()
            p.initialize({"db_path": db_path})
            p.execute("create_table", {
                "table_name": "test",
                "columns": {"id": "INTEGER PRIMARY KEY"}
            })
            p.shutdown()
            p2 = DatabasePlugin()
            p2.initialize({"db_path": db_path})
            result = p2.execute("query", {"sql": "SELECT name FROM sqlite_master WHERE type='table'"})
            assert result.success is True
            assert any(row["name"] == "test" for row in result.data["rows"])
            p2.shutdown()
        finally:
            os.unlink(db_path)

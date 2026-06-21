"""
文件插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

from src.left.action.execution.file_plugin import FilePlugin
from src.platform.support.models.base.plugin import PluginResult


class TestFilePlugin:
    """文件插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = FilePlugin()
        p.initialize({"base_path": "."})
        return p

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_initialize(self):
        """测试初始化"""
        p = FilePlugin()
        assert p.initialize({"base_path": "/tmp"}) is True
        assert p.health_check() is True

    def test_initialize_default(self):
        """测试默认初始化"""
        p = FilePlugin()
        assert p.initialize({}) is True
        assert p.base_path == Path(".")

    def test_health_check_not_initialized(self):
        """测试未初始化健康检查"""
        p = FilePlugin()
        assert p.health_check() is False

    def test_read_normal(self, plugin, temp_dir):
        """测试正常读取"""
        path = Path(temp_dir) / "test.txt"
        path.write_text("hello world")
        result = plugin.execute("read", {"path": str(path)})
        assert result.success is True
        assert result.data["content"] == "hello world"

    def test_read_empty_path(self, plugin):
        """测试空路径"""
        result = plugin.execute("read", {"path": ""})
        assert result.success is False

    def test_read_missing_path(self, plugin):
        """测试缺少路径参数"""
        result = plugin.execute("read", {})
        assert result.success is False

    def test_read_not_found(self, plugin):
        """测试文件不存在"""
        result = plugin.execute("read", {"path": "/nonexistent/file.txt"})
        assert result.success is False

    def test_write_normal(self, plugin, temp_dir):
        """测试正常写入"""
        path = str(Path(temp_dir) / "write.txt")
        result = plugin.execute("write", {"path": path, "content": "test content"})
        assert result.success is True
        assert Path(path).read_text() == "test content"

    def test_write_empty_content(self, plugin, temp_dir):
        """测试写入空内容"""
        path = str(Path(temp_dir) / "empty.txt")
        result = plugin.execute("write", {"path": path, "content": ""})
        assert result.success is True
        assert Path(path).read_text() == ""

    def test_read_json_normal(self, plugin, temp_dir):
        """测试正常读取JSON"""
        path = Path(temp_dir) / "data.json"
        path.write_text(json.dumps({"key": "value"}))
        result = plugin.execute("read_json", {"path": str(path)})
        assert result.success is True
        assert result.data["data"]["key"] == "value"

    def test_read_json_invalid(self, plugin, temp_dir):
        """测试读取非法JSON"""
        path = Path(temp_dir) / "bad.json"
        path.write_text("not json")
        result = plugin.execute("read_json", {"path": str(path)})
        assert result.success is False

    def test_write_json_normal(self, plugin, temp_dir):
        """测试正常写入JSON"""
        path = str(Path(temp_dir) / "out.json")
        result = plugin.execute("write_json", {"path": path, "data": {"a": 1}})
        assert result.success is True
        loaded = json.loads(Path(path).read_text())
        assert loaded["a"] == 1

    def test_read_csv_normal(self, plugin, temp_dir):
        """测试正常读取CSV"""
        path = Path(temp_dir) / "data.csv"
        path.write_text("name,age\nAlice,30\nBob,25")
        result = plugin.execute("read_csv", {"path": str(path)})
        assert result.success is True
        assert len(result.data["rows"]) == 2
        assert result.data["columns"] == ["name", "age"]

    def test_read_csv_empty(self, plugin, temp_dir):
        """测试读取空CSV"""
        path = Path(temp_dir) / "empty.csv"
        path.write_text("")
        result = plugin.execute("read_csv", {"path": str(path)})
        assert result.success is True
        assert result.data["rows"] == []

    def test_list_dir_normal(self, plugin, temp_dir):
        """测试正常列出目录"""
        result = plugin.execute("list_dir", {"path": temp_dir})
        assert result.success is True
        assert isinstance(result.data["items"], list)

    def test_list_dir_not_found(self, plugin):
        """测试列出不存在目录"""
        result = plugin.execute("list_dir", {"path": "/nonexistent/dir"})
        assert result.success is False

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message

    def test_read_large_file(self, plugin, temp_dir):
        """测试读取大文件（边界）"""
        path = Path(temp_dir) / "large.txt"
        content = "x" * 100000
        path.write_text(content)
        result = plugin.execute("read", {"path": str(path)})
        assert result.success is True
        assert len(result.data["content"]) == 100000

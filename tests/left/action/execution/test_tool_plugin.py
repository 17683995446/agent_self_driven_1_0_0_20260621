"""
工具插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
import math

from src.left.action.execution.tool_plugin import ToolPlugin


class TestToolPlugin:
    """工具插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = ToolPlugin()
        p.initialize({})
        return p

    def test_initialize(self):
        """测试初始化"""
        p = ToolPlugin()
        assert p.initialize({}) is True
        assert p.health_check() is True

    def test_calculate_normal(self, plugin):
        """测试正常计算"""
        result = plugin.execute("calculate", {"expression": "2 + 3"})
        assert result.success is True
        assert result.data["result"] == 5

    def test_calculate_decimal(self, plugin):
        """测试小数计算"""
        result = plugin.execute("calculate", {"expression": "2.5 * 4"})
        assert result.success is True
        assert result.data["result"] == 10.0

    def test_calculate_empty_expression(self, plugin):
        """测试空表达式"""
        result = plugin.execute("calculate", {"expression": ""})
        assert result.success is False

    def test_calculate_division_by_zero(self, plugin):
        """测试除零"""
        result = plugin.execute("calculate", {"expression": "1/0"})
        assert result.success is False

    def test_calculate_parentheses(self, plugin):
        """测试括号运算"""
        result = plugin.execute("calculate", {"expression": "(2 + 3) * 4"})
        assert result.success is True
        assert result.data["result"] == 20.0

    def test_calculate_invalid_chars(self, plugin):
        """测试非法字符"""
        result = plugin.execute("calculate", {"expression": "2 + __import__('os')"})
        assert result.success is False

    def test_search_normal(self, plugin):
        """测试正常搜索"""
        items = ["apple", "banana", "cherry", "date"]
        result = plugin.execute("search", {"query": "an", "items": items})
        assert result.success is True
        assert len(result.data["results"]) == 1

    def test_search_empty_query(self, plugin):
        """测试空查询"""
        result = plugin.execute("search", {"query": "", "items": ["a", "b"]})
        assert result.success is False

    def test_search_no_match(self, plugin):
        """测试无匹配"""
        result = plugin.execute("search", {"query": "xyz", "items": ["a", "b"]})
        assert result.success is True
        assert result.data["results"] == []

    def test_time_iso(self, plugin):
        """测试获取ISO时间"""
        result = plugin.execute("time", {"format": "iso"})
        assert result.success is True
        assert "T" in result.data["time"]

    def test_time_timestamp(self, plugin):
        """测试获取时间戳"""
        result = plugin.execute("time", {"format": "timestamp"})
        assert result.success is True
        assert float(result.data["time"]) > 0

    def test_time_default(self, plugin):
        """测试默认格式"""
        result = plugin.execute("time", {})
        assert result.success is True
        assert len(result.data["time"]) > 0

    def test_convert_normal(self, plugin):
        """测试正常转换"""
        result = plugin.execute("convert", {"value": 1000, "from": "m", "to": "km"})
        assert result.success is True
        assert result.data["result"] == 1.0

    def test_convert_same_unit(self, plugin):
        """测试相同单位"""
        result = plugin.execute("convert", {"value": 100, "from": "m", "to": "m"})
        assert result.success is True
        assert result.data["result"] == 100

    def test_convert_unsupported(self, plugin):
        """测试不支持的转换"""
        result = plugin.execute("convert", {"value": 1, "from": "x", "to": "y"})
        assert result.success is False

    def test_count_tokens_normal(self, plugin):
        """测试正常计数"""
        result = plugin.execute("count_tokens", {"text": "hello world"})
        assert result.success is True
        assert result.data["chars"] == 11
        assert result.data["tokens"] >= 0

    def test_count_tokens_empty(self, plugin):
        """测试空文本"""
        result = plugin.execute("count_tokens", {"text": ""})
        assert result.success is True
        assert result.data["tokens"] == 0

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message

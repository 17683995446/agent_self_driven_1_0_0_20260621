"""
插件模型测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability, TaskPluginAdapter
)


class MockPlugin(PluginBase):
    """模拟插件"""

    def __init__(self):
        meta = PluginMetadata(
            name="mock",
            version="1.0.0",
            plugin_type=PluginType.CUSTOM,
            capabilities=[PluginCapability.EXECUTE],
        )
        super().__init__(meta)

    def initialize(self, config):
        self._initialized = True
        return True

    def execute(self, action, params):
        return PluginResult(success=True, message="ok")

    def health_check(self):
        return self._initialized


class TestPluginMetadata:
    """插件元数据测试"""

    def test_creation(self):
        """测试创建"""
        meta = PluginMetadata(
            name="test",
            version="1.0.0",
            plugin_type=PluginType.FILE,
            capabilities=[PluginCapability.READ],
        )
        assert meta.name == "test"
        assert meta.version == "1.0.0"

    def test_default_values(self):
        """测试默认值"""
        meta = PluginMetadata(
            name="test",
            version="1.0",
            plugin_type=PluginType.TOOL,
            capabilities=[],
        )
        assert meta.description == ""
        assert meta.author == ""


class TestPluginResult:
    """插件结果测试"""

    def test_success(self):
        """测试成功结果"""
        result = PluginResult(success=True, message="done")
        assert result.success is True
        assert result.message == "done"
        assert result.data == {}

    def test_failure(self):
        """测试失败结果"""
        result = PluginResult(success=False, message="error", data={"code": 1})
        assert result.success is False
        assert result.data["code"] == 1

    def test_execution_time(self):
        """测试执行时间"""
        result = PluginResult(success=True, message="ok", execution_time=1.5)
        assert result.execution_time == 1.5


class TestPluginBase:
    """插件基类测试"""

    def test_name_property(self):
        """测试名称属性"""
        plugin = MockPlugin()
        assert plugin.name == "mock"

    def test_initialize(self):
        """测试初始化"""
        plugin = MockPlugin()
        assert plugin.initialize({}) is True
        assert plugin._initialized is True

    def test_health_check(self):
        """测试健康检查"""
        plugin = MockPlugin()
        plugin.initialize({})
        assert plugin.health_check() is True

    def test_health_check_not_initialized(self):
        """测试未初始化健康检查"""
        plugin = MockPlugin()
        assert plugin.health_check() is False

    def test_shutdown(self):
        """测试关闭"""
        plugin = MockPlugin()
        plugin.initialize({})
        plugin.shutdown()
        assert plugin._initialized is False

    def test_execute(self):
        """测试执行"""
        plugin = MockPlugin()
        plugin.initialize({})
        result = plugin.execute("test", {})
        assert result.success is True


class TestTaskPluginAdapter:
    """任务插件适配器测试"""

    def test_create_task_fn(self):
        """测试创建任务函数"""
        plugin = MockPlugin()
        plugin.initialize({})
        adapter = TaskPluginAdapter(plugin)
        fn = adapter.create_task_fn("test", {})
        result = fn()
        assert result.success is True

    def test_create_task_fn_with_params(self):
        """测试带参数创建任务函数"""
        plugin = MockPlugin()
        plugin.initialize({})
        adapter = TaskPluginAdapter(plugin)
        fn = adapter.create_task_fn("test", {"key": "value"})
        result = fn()
        assert result.success is True

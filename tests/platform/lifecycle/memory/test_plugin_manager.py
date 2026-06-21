"""
插件管理器测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.lifecycle.memory.plugin_manager import PluginManager
from src.left.action.execution.tool_plugin import ToolPlugin
from src.left.action.execution.file_plugin import FilePlugin


class TestPluginManager:
    """插件管理器测试类"""

    @pytest.fixture
    def manager(self):
        m = PluginManager()
        m.initialize()
        return m

    def test_initialize(self):
        """测试初始化"""
        m = PluginManager()
        m.initialize()
        assert m._initialized is True

    def test_register(self, manager):
        """测试注册插件"""
        plugin = ToolPlugin()
        result = manager.register("tool", plugin, {})
        assert result is True
        assert "tool" in manager.list_plugins()

    def test_register_overwrite(self, manager):
        """测试重复注册"""
        p1 = ToolPlugin()
        p2 = FilePlugin()
        manager.register("test", p1, {})
        manager.register("test", p2, {})
        assert manager.get_plugin("test") is p2

    def test_load(self, manager):
        """测试加载插件"""
        plugin = ToolPlugin()
        manager.register("tool", plugin, {})
        assert manager.load("tool") is True
        assert plugin._initialized is True

    def test_load_not_found(self, manager):
        """测试加载不存在插件"""
        assert manager.load("nonexistent") is False

    def test_load_all(self, manager):
        """测试加载所有插件"""
        manager.register("tool", ToolPlugin(), {})
        manager.register("file", FilePlugin(), {})
        results = manager.load_all()
        assert results["tool"] is True
        assert results["file"] is True

    def test_execute(self, manager):
        """测试执行插件"""
        plugin = ToolPlugin()
        manager.register("tool", plugin, {})
        manager.load("tool")
        result = manager.execute("tool", "calculate", {"expression": "1+1"})
        assert result.success is True

    def test_execute_not_found(self, manager):
        """测试执行不存在插件"""
        result = manager.execute("none", "action", {})
        assert result.success is False
        assert "not found" in result.message

    def test_execute_not_initialized(self, manager):
        """测试执行未初始化插件"""
        manager.register("tool", ToolPlugin(), {})
        result = manager.execute("tool", "action", {})
        assert result.success is False
        assert "not initialized" in result.message

    def test_health_check(self, manager):
        """测试健康检查"""
        plugin = ToolPlugin()
        manager.register("tool", plugin, {})
        manager.load("tool")
        assert manager.health_check("tool") is True

    def test_health_check_not_found(self, manager):
        """测试检查不存在插件"""
        assert manager.health_check("none") is False

    def test_health_check_all(self, manager):
        """测试检查所有插件"""
        manager.register("tool", ToolPlugin(), {})
        manager.load("tool")
        results = manager.health_check_all()
        assert results["tool"] is True

    def test_get_plugin(self, manager):
        """测试获取插件"""
        plugin = ToolPlugin()
        manager.register("tool", plugin, {})
        assert manager.get_plugin("tool") is plugin

    def test_get_plugin_not_found(self, manager):
        """测试获取不存在插件"""
        assert manager.get_plugin("none") is None

    def test_list_plugins_empty(self, manager):
        """测试空插件列表"""
        assert manager.list_plugins() == []

    def test_list_plugins(self, manager):
        """测试插件列表"""
        manager.register("a", ToolPlugin(), {})
        manager.register("b", FilePlugin(), {})
        plugins = manager.list_plugins()
        assert len(plugins) == 2
        assert "a" in plugins
        assert "b" in plugins

    def test_get_plugins_by_type(self, manager):
        """测试按类型获取插件"""
        from src.platform.support.models.base.plugin import PluginType
        manager.register("tool", ToolPlugin(), {})
        manager.load("tool")
        tools = manager.get_plugins_by_type(PluginType.TOOL)
        assert len(tools) == 1

    def test_shutdown(self, manager):
        """测试关闭插件"""
        plugin = ToolPlugin()
        manager.register("tool", plugin, {})
        manager.load("tool")
        manager.shutdown("tool")
        assert plugin._initialized is False

    def test_shutdown_all(self, manager):
        """测试关闭所有插件"""
        p1 = ToolPlugin()
        p2 = ToolPlugin()
        manager.register("a", p1, {})
        manager.register("b", p2, {})
        manager.load("a")
        manager.load("b")
        manager.shutdown_all()
        assert p1._initialized is False
        assert p2._initialized is False

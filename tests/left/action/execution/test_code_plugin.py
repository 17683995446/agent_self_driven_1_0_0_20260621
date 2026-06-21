"""
代码执行插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.execution.code_plugin import CodePlugin


class TestCodePlugin:
    """代码插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = CodePlugin()
        p.initialize({})
        return p

    def test_initialize(self):
        """测试初始化"""
        p = CodePlugin()
        assert p.initialize({}) is True
        assert p.health_check() is True

    def test_run_python_normal(self, plugin):
        """测试正常执行Python"""
        result = plugin.execute("run_python", {"code": "print('hello')"})
        assert result.success is True
        assert "hello" in result.data["stdout"]

    def test_run_python_return_value(self, plugin):
        """测试Python返回值"""
        result = plugin.execute("run_python", {"code": "print(2 + 2)"})
        assert result.success is True
        assert "4" in result.data["stdout"]

    def test_run_python_empty_code(self, plugin):
        """测试空代码"""
        result = plugin.execute("run_python", {"code": ""})
        assert result.success is False

    def test_run_python_syntax_error(self, plugin):
        """测试语法错误"""
        result = plugin.execute("run_python", {"code": "print("})
        assert result.success is False

    def test_run_shell_normal(self, plugin):
        """测试正常执行Shell"""
        result = plugin.execute("run_shell", {"command": "echo hello"})
        assert result.success is True
        assert "hello" in result.data["stdout"]

    def test_run_shell_empty_command(self, plugin):
        """测试空命令"""
        result = plugin.execute("run_shell", {"command": ""})
        assert result.success is False

    def test_run_shell_invalid_command(self, plugin):
        """测试非法命令"""
        result = plugin.execute("run_shell", {"command": "nonexistent_command_xyz"})
        assert result.success is False

    def test_run_script_normal(self, plugin):
        """测试正常执行脚本"""
        result = plugin.execute("run_script", {"script": "print('from script')", "interpreter": "python3"})
        assert result.success is True
        assert "from script" in result.data["stdout"]

    def test_run_script_empty(self, plugin):
        """测试空脚本"""
        result = plugin.execute("run_script", {"script": ""})
        assert result.success is False

    def test_run_script_invalid_interpreter(self, plugin):
        """测试非法解释器"""
        result = plugin.execute("run_script", {"script": "print(1)", "interpreter": "invalid"})
        assert result.success is False

    def test_run_python_timeout(self, plugin):
        """测试超时（边界）"""
        result = plugin.execute("run_python", {"code": "import time; time.sleep(10)", "timeout": 0.1})
        assert result.success is False

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message

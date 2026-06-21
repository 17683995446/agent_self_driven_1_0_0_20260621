"""
U3：可安装包化测试

验证项目可安装性和console_scripts入口：
1. pyproject.toml 存在且配置正确
2. src/ 包结构完整（__init__.py）
3. pip install -e . 成功
4. console_scripts 入口可用
5. 可选依赖声明正确

第一性原理：用户应能通过 pip install 一键安装
"""

import pytest
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU3PyprojectToml:
    """测试pyproject.toml配置"""

    def test_pyproject_exists(self):
        """pyproject.toml 存在"""
        assert (PROJECT_ROOT / "pyproject.toml").is_file()

    def test_pyproject_has_name(self):
        """pyproject.toml 有项目名"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert 'name = "self-driven-agent"' in content

    def test_pyproject_has_version(self):
        """pyproject.toml 有版本号"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert 'version = "1.0.0"' in content

    def test_pyproject_has_console_scripts(self):
        """pyproject.toml 有 console_scripts"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[project.scripts]" in content
        assert 'self-driven-agent = "src.main:main"' in content

    def test_pyproject_has_core_dependency(self):
        """pyproject.toml 声明核心依赖"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "pyyaml" in content

    def test_pyproject_has_optional_dependencies(self):
        """pyproject.toml 声明可选依赖"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[project.optional-dependencies]" in content
        assert "psutil" in content
        assert "numpy" in content

    def test_pyproject_has_dev_dependencies(self):
        """pyproject.toml 声明开发依赖"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "pytest" in content

    def test_pyproject_has_build_system(self):
        """pyproject.toml 有构建系统配置"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[build-system]" in content
        assert "setuptools" in content

    def test_pyproject_has_packages_find(self):
        """pyproject.toml 配置包发现"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[tool.setuptools.packages.find]" in content


class TestU3PackageStructure:
    """测试src/包结构完整性"""

    def test_src_has_init(self):
        """src/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "__init__.py").is_file()

    def test_left_has_init(self):
        """src/left/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "left" / "__init__.py").is_file()

    def test_platform_has_init(self):
        """src/platform/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "platform" / "__init__.py").is_file()

    def test_cognition_has_init(self):
        """src/left/cognition/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "left" / "cognition" / "__init__.py").is_file()

    def test_action_has_init(self):
        """src/left/action/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "left" / "action" / "__init__.py").is_file()

    def test_support_has_init(self):
        """src/platform/support/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "platform" / "support" / "__init__.py").is_file()

    def test_lifecycle_has_init(self):
        """src/platform/lifecycle/__init__.py 存在"""
        assert (PROJECT_ROOT / "src" / "platform" / "lifecycle" / "__init__.py").is_file()


class TestU3Installable:
    """测试可安装性"""

    def test_package_importable(self):
        """src.main 可导入"""
        from src.main import main, AgentSystem, __version__
        assert callable(main)
        assert __version__ == "1.0.0"

    def test_console_script_available(self):
        """console_scripts 入口可用"""
        result = subprocess.run(
            ["self-driven-agent", "--version"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_console_script_help(self):
        """console_scripts --help 可用"""
        result = subprocess.run(
            ["self-driven-agent", "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--env" in result.stdout
        assert "--log-level" in result.stdout

    def test_pip_show_works(self):
        """pip show 能找到包"""
        result = subprocess.run(
            ["pip", "show", "self-driven-agent"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "self-driven-agent" in result.stdout


class TestU3LogDirAutoCreate:
    """测试日志目录自动创建"""

    def test_log_dir_created_on_import(self, tmp_path, monkeypatch):
        """导入时自动创建日志目录"""
        monkeypatch.setenv("AGENT_LOG_DIR", str(tmp_path / "custom_logs"))
        # 重新导入模块会触发日志配置
        import importlib
        import src.main
        importlib.reload(src.main)
        assert (tmp_path / "custom_logs").is_dir()

    def test_cli_log_dir_works(self, tmp_path):
        """--log-dir CLI参数生效"""
        from src.main import AgentSystem
        custom_log_dir = str(tmp_path / "cli_logs")
        agent = AgentSystem(log_dir=custom_log_dir)
        assert os.path.isdir(custom_log_dir)
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

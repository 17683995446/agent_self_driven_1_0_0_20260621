"""
U7：错误信息和启动反馈优化测试

验证错误信息和启动反馈：
1. 配置文件不存在时明确提示路径
2. 配置加载时打印实际文件路径
3. 启动时打印配置摘要
4. start.sh 核心依赖缺失时exit
5. start.sh 可选依赖缺失时warn

第一性原理：出错时用户应能定位和修复
X3：异常类型由 FileNotFoundError 统一为 ValidationError
"""

import pytest
import os
import logging
from pathlib import Path
from unittest.mock import patch

from src.platform.lifecycle.memory.config_loader import ConfigLoader
from src.platform.support.models.base.error_code import ErrorCode, ValidationError


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU7ConfigLoadErrorMessages:
    """测试配置加载错误信息（X2：显式失败而非静默回退，X3：错误码体系）"""

    def test_missing_config_raises_with_path(self, tmp_path):
        """X2/X3：配置文件不存在时抛出 ValidationError 包含路径"""
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(nonexistent)
        assert nonexistent in str(exc_info.value)

    def test_missing_config_has_config_not_found_code(self, tmp_path):
        """X3：错误码为 CONFIG_NOT_FOUND"""
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(nonexistent)
        assert exc_info.value.error_code == ErrorCode.CONFIG_NOT_FOUND

    def test_missing_config_error_mentions_available_configs(self, tmp_path):
        """X2：错误信息提示可用配置"""
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(nonexistent)
        error_msg = str(exc_info.value)
        assert "dev.yaml" in error_msg
        assert "prod.yaml" in error_msg

    def test_missing_config_error_mentions_env_var(self, tmp_path):
        """X2：错误信息提示环境变量"""
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(nonexistent)
        assert "AGENT_CONFIG_PATH" in str(exc_info.value)

    def test_successful_load_logs_path(self, caplog):
        """成功加载时日志包含文件路径"""
        os.chdir(str(PROJECT_ROOT))
        with caplog.at_level(logging.INFO):
            loader = ConfigLoader("./config/dev.yaml")
        assert "dev.yaml" in caplog.text


class TestU7ConfigSummary:
    """测试启动配置摘要"""

    def test_config_summary_printed_on_init(self, caplog):
        """初始化时打印配置摘要"""
        os.chdir(str(PROJECT_ROOT))
        with caplog.at_level(logging.INFO):
            from src.main import AgentSystem
            agent = AgentSystem()
        assert "配置摘要" in caplog.text
        assert "环境" in caplog.text
        assert "配置文件" in caplog.text
        # 清理
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

    def test_config_summary_contains_env(self, caplog):
        """配置摘要包含环境信息"""
        os.chdir(str(PROJECT_ROOT))
        with caplog.at_level(logging.INFO):
            from src.main import AgentSystem
            agent = AgentSystem()
        assert "dev" in caplog.text
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

    def test_config_summary_contains_resource_limits(self, caplog):
        """配置摘要包含资源限制"""
        os.chdir(str(PROJECT_ROOT))
        with caplog.at_level(logging.INFO):
            from src.main import AgentSystem
            agent = AgentSystem()
        assert "CPU" in caplog.text or "cpu" in caplog.text.lower()
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass


class TestU7StartScriptImprovements:
    """测试start.sh改进"""

    def test_start_script_exists(self):
        """start.sh 存在"""
        assert (PROJECT_ROOT / "scripts" / "start.sh").is_file()

    def test_start_script_has_core_dep_check(self):
        """start.sh 检查核心依赖"""
        content = (PROJECT_ROOT / "scripts" / "start.sh").read_text()
        assert "核心依赖" in content or "core_deps" in content

    def test_start_script_has_optional_dep_check(self):
        """start.sh 检查可选依赖"""
        content = (PROJECT_ROOT / "scripts" / "start.sh").read_text()
        assert "可选依赖" in content or "optional_deps" in content

    def test_start_script_exits_on_core_dep_missing(self):
        """start.sh 核心依赖缺失时exit"""
        content = (PROJECT_ROOT / "scripts" / "start.sh").read_text()
        # 检查核心依赖检查部分有exit
        assert "exit 1" in content

    def test_start_script_has_install_hint(self):
        """start.sh 有安装提示"""
        content = (PROJECT_ROOT / "scripts" / "start.sh").read_text()
        assert "pip install" in content

    def test_start_script_not_check_pytest_as_runtime(self):
        """start.sh 不再将pytest作为运行时依赖检查"""
        content = (PROJECT_ROOT / "scripts" / "start.sh").read_text()
        # pytest不应在核心或可选依赖列表中
        lines = content.split("\n")
        dep_lines = [l for l in lines if "deps=" in l]
        for line in dep_lines:
            assert "pytest" not in line, f"pytest不应在依赖检查列表中: {line}"


class TestU7DryRunFeedback:
    """测试dry-run模式反馈"""

    def test_dry_run_prints_config_path(self, capsys):
        """dry-run打印配置文件路径"""
        os.chdir(str(PROJECT_ROOT))
        from src.main import _run_dry_check
        _run_dry_check(None, None)
        captured = capsys.readouterr()
        assert "配置文件" in captured.out

    def test_dry_run_prints_env(self, capsys):
        """dry-run打印环境"""
        os.chdir(str(PROJECT_ROOT))
        from src.main import _run_dry_check
        _run_dry_check(None, None)
        captured = capsys.readouterr()
        assert "环境" in captured.out

    def test_dry_run_error_has_path(self, capsys, tmp_path):
        """dry-run配置不存在时错误信息包含路径"""
        from src.main import _run_dry_check
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(SystemExit):
            _run_dry_check(nonexistent, None)
        captured = capsys.readouterr()
        assert nonexistent in captured.out
        assert "错误" in captured.out

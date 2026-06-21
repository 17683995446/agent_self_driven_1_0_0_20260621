"""
U2：CLI参数入口测试

验证命令行参数解析和生效：
1. argparse 参数定义正确
2. --config 指定配置路径
3. --env 快捷选择环境
4. --log-level 设置日志级别
5. --version 显示版本
6. --dry-run 验证配置不启动
7. 优先级：CLI > 环境变量 > 默认

第一性原理：用户应能通过命令行控制所有关键行为
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

from src.main import parse_args, resolve_config_from_args, __version__


class TestU2ArgparseDefinition:
    """测试argparse参数定义"""

    def test_version_attribute_exists(self):
        """__version__ 存在"""
        assert __version__ == "1.0.0"

    def test_no_args_returns_default_namespace(self):
        """无参数时返回默认Namespace"""
        args = parse_args([])
        assert args.config_path is None
        assert args.env is None
        assert args.log_level is None
        assert args.log_dir is None
        assert args.dry_run is False

    def test_config_short_option(self):
        """-c 短选项指定配置"""
        args = parse_args(["-c", "config/prod.yaml"])
        assert args.config_path == "config/prod.yaml"

    def test_config_long_option(self):
        """--config 长选项指定配置"""
        args = parse_args(["--config", "config/test.yaml"])
        assert args.config_path == "config/test.yaml"

    def test_env_dev(self):
        """--env dev"""
        args = parse_args(["--env", "dev"])
        assert args.env == "dev"

    def test_env_prod(self):
        """--env prod"""
        args = parse_args(["--env", "prod"])
        assert args.env == "prod"

    def test_env_test(self):
        """--env test"""
        args = parse_args(["--env", "test"])
        assert args.env == "test"

    def test_env_invalid_rejected(self):
        """无效环境被拒绝"""
        with pytest.raises(SystemExit):
            parse_args(["--env", "staging"])

    def test_log_level_choices(self):
        """--log-level 选项"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            args = parse_args(["--log-level", level])
            assert args.log_level == level

    def test_log_level_invalid_rejected(self):
        """无效日志级别被拒绝"""
        with pytest.raises(SystemExit):
            parse_args(["--log-level", "TRACE"])

    def test_log_dir_option(self):
        """--log-dir 指定日志目录"""
        args = parse_args(["--log-dir", "/var/log/agent"])
        assert args.log_dir == "/var/log/agent"

    def test_dry_run_flag(self):
        """--dry-run 标志"""
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_dry_run_default_false(self):
        """dry-run 默认 False"""
        args = parse_args([])
        assert args.dry_run is False


class TestU2VersionOutput:
    """测试 --version 输出"""

    def test_version_prints_and_exits(self, capsys):
        """--version 打印版本后退出"""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_version_short_flag(self, capsys):
        """-v 短选项"""
        with pytest.raises(SystemExit):
            parse_args(["-v"])
        captured = capsys.readouterr()
        assert __version__ in captured.out


class TestU2ResolveConfigFromArgs:
    """测试从参数解析配置路径"""

    def test_config_path_takes_priority(self):
        """--config 优先于 --env"""
        args = parse_args(["--config", "custom.yaml", "--env", "prod"])
        path = resolve_config_from_args(args)
        assert path == "custom.yaml"

    def test_env_resolves_to_config_path(self):
        """--env 解析为配置路径"""
        args = parse_args(["--env", "prod"])
        path = resolve_config_from_args(args)
        assert path == "./config/prod.yaml"

    def test_env_dev_resolves(self):
        """--env dev 解析"""
        args = parse_args(["--env", "dev"])
        path = resolve_config_from_args(args)
        assert path == "./config/dev.yaml"

    def test_no_config_no_env_returns_none(self):
        """无 --config 无 --env 返回 None"""
        args = parse_args([])
        path = resolve_config_from_args(args)
        assert path is None


class TestU2DryRun:
    """测试 --dry-run 模式"""

    def test_dry_run_with_dev_config(self, capsys, monkeypatch):
        """dry-run 验证dev配置"""
        os.chdir("/workspace/self_driven_agent")
        from src.main import _run_dry_check
        _run_dry_check(None, None)
        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out
        assert "dev" in captured.out
        # X10：dry-run 增强后输出"所有检查通过，配置有效"
        assert "所有检查通过" in captured.out or "配置有效" in captured.out

    def test_dry_run_with_explicit_config(self, capsys, monkeypatch, tmp_path):
        """dry-run 指定配置文件"""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("environment: custom\nlog_level: DEBUG\n")
        from src.main import _run_dry_check
        _run_dry_check(str(config_file), None)
        captured = capsys.readouterr()
        assert "custom" in captured.out
        assert "DEBUG" in captured.out

    def test_dry_run_nonexistent_config_exits(self, capsys):
        """dry-run 配置不存在时退出"""
        from src.main import _run_dry_check
        with pytest.raises(SystemExit) as exc_info:
            _run_dry_check("/nonexistent/config.yaml", None)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "错误" in captured.out

    def test_dry_run_with_log_level_override(self, capsys):
        """dry-run CLI覆盖日志级别"""
        os.chdir("/workspace/self_driven_agent")
        from src.main import _run_dry_check
        _run_dry_check(None, "WARNING")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out


class TestU2AgentSystemAcceptsParams:
    """测试AgentSystem接受CLI参数"""

    def test_agent_system_accepts_config_path(self, monkeypatch, tmp_path):
        """AgentSystem接受config_path参数"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("environment: test\nlog_level: INFO\n")
        from src.main import AgentSystem
        agent = AgentSystem(config_path=str(config_file))
        assert agent.config_loader.config_path == str(config_file)
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

    def test_agent_system_accepts_log_level(self, monkeypatch):
        """AgentSystem接受log_level参数"""
        os.chdir("/workspace/self_driven_agent")
        import logging
        from src.main import AgentSystem
        agent = AgentSystem(log_level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

    def test_agent_system_defaults_to_dev(self, monkeypatch):
        """AgentSystem无参数时默认dev配置"""
        os.chdir("/workspace/self_driven_agent")
        from src.main import AgentSystem
        agent = AgentSystem()
        assert "dev" in agent.config_loader.config_path or "dev.yaml" in agent.config_loader.config_path
        agent.running = False
        try:
            agent._stop_hot_reload()
        except Exception:
            pass

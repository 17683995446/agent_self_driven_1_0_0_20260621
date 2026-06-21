"""
X6：交互反馈优化测试

验证交互反馈优化：
1. 彩色日志格式化器（终端检测，非TTY纯文本）（M1）
2. 节流时打印说明日志（M3）
3. 区分终端日志和文件日志（M14）

第一性原理：用户应能视觉区分日志级别，节流时知道发生了什么
"""

import pytest
import os
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.main import ColoredFormatter, _setup_logging
from src.platform.support.models.base.state import EnvironmentState


def _make_system():
    """创建最小化 AgentSystem 实例"""
    from src.main import AgentSystem
    from dataclasses import replace
    system = object.__new__(AgentSystem)
    system.cycle_count = 10
    system.start_time = time.time()
    system.total_tasks_executed = 5
    system.total_tasks_succeeded = 4
    system.guardrail = MagicMock()
    system.guardrail.max_cpu = 0.2
    return system


def _make_state(cpu=0.5, memory=0.3):
    """创建 EnvironmentState"""
    from dataclasses import replace
    base = EnvironmentState()
    return replace(base, system=replace(base.system, cpu_overall=cpu, memory_usage=memory))


class TestX6ColoredFormatter:
    """测试彩色日志格式化器"""

    def test_color_enabled_adds_color_codes(self):
        """启用颜色时添加 ANSI 颜色码"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="test error", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[31m" in output  # 红色
        assert "\033[0m" in output   # 重置

    def test_color_disabled_no_color_codes(self):
        """禁用颜色时不添加 ANSI 颜色码"""
        formatter = ColoredFormatter(use_color=False)
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="test error", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[" not in output

    def test_error_is_red(self):
        """ERROR 级别为红色"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="err", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[31m" in output

    def test_warning_is_yellow(self):
        """WARNING 级别为黄色"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="warn", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[33m" in output

    def test_info_is_green(self):
        """INFO 级别为绿色"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="info", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[32m" in output

    def test_debug_is_cyan(self):
        """DEBUG 级别为青色"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="debug", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "\033[36m" in output

    def test_message_content_preserved(self):
        """日志消息内容被保留"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "hello world" in output

    def test_no_color_still_formats_message(self):
        """无颜色时仍格式化消息"""
        formatter = ColoredFormatter(use_color=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None
        )
        output = formatter.format(record)
        assert "hello" in output
        assert "INFO" in output


class TestX6SetupLogging:
    """测试日志系统配置"""

    def test_setup_creates_file_handler(self):
        """_setup_logging 创建文件 handler"""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        _setup_logging()
        has_file = any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
        # 恢复
        root_logger.handlers = original_handlers
        assert has_file

    def test_setup_creates_stream_handler(self):
        """_setup_logging 创建流 handler"""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        _setup_logging()
        has_stream = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                        for h in root_logger.handlers)
        # 恢复
        root_logger.handlers = original_handlers
        assert has_stream

    def test_setup_clears_existing_handlers(self):
        """_setup_logging 清除已有 handlers"""
        root_logger = logging.getLogger()
        # 添加一个临时 handler
        temp_handler = logging.NullHandler()
        root_logger.addHandler(temp_handler)
        _setup_logging()
        has_null = any(isinstance(h, logging.NullHandler) for h in root_logger.handlers)
        assert not has_null, "NullHandler 应被清除"

    def test_setup_file_handler_uses_plain_formatter(self):
        """文件 handler 使用纯文本格式化器"""
        root_logger = logging.getLogger()
        _setup_logging()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
        assert type(file_handlers[0].formatter).__name__ != "ColoredFormatter"

    def test_setup_stream_handler_uses_colored_formatter(self):
        """流 handler 使用 ColoredFormatter"""
        root_logger = logging.getLogger()
        _setup_logging()
        stream_handlers = [h for h in root_logger.handlers
                          if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert len(stream_handlers) > 0
        assert type(stream_handlers[0].formatter).__name__ == "ColoredFormatter"


class TestX6ThrottleExplanation:
    """测试节流说明日志（M3）"""

    def test_throttle_logs_warning(self, caplog):
        """节流时记录 WARNING 日志"""
        system = _make_system()
        result = MagicMock()
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep"):
                system._throttle_if_needed(_make_state(cpu=0.9), result)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_throttle_log_contains_cpu(self, caplog):
        """节流日志包含 CPU 信息"""
        system = _make_system()
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep"):
                system._throttle_if_needed(_make_state(cpu=0.9), result=MagicMock())
        assert "CPU" in caplog.text or "cpu" in caplog.text.lower()

    def test_throttle_log_contains_throttle_keyword(self, caplog):
        """节流日志包含"节流"关键词"""
        system = _make_system()
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep"):
                system._throttle_if_needed(_make_state(cpu=0.9), result=MagicMock())
        assert "节流" in caplog.text

    def test_throttle_log_contains_duration(self, caplog):
        """节流日志包含节流时长"""
        system = _make_system()
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep"):
                system._throttle_if_needed(_make_state(cpu=0.9), result=MagicMock())
        assert "2" in caplog.text and "秒" in caplog.text

    def test_throttle_log_contains_cpu_values(self, caplog):
        """节流日志包含当前CPU和限制CPU值"""
        system = _make_system()
        system.guardrail.max_cpu = 0.2
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep"):
                system._throttle_if_needed(_make_state(cpu=0.8), result=MagicMock())
        # 应包含当前值和限制值
        assert "80" in caplog.text or "0.8" in caplog.text  # 当前CPU
        assert "20" in caplog.text or "0.2" in caplog.text  # 限制CPU

    def test_no_throttle_when_cpu_within_limit(self, caplog):
        """CPU未超限时不节流"""
        system = _make_system()
        system.guardrail.max_cpu = 0.9
        with caplog.at_level(logging.WARNING):
            with patch("src.main.time.sleep") as mock_sleep:
                system._throttle_if_needed(_make_state(cpu=0.3), result=MagicMock())
        mock_sleep.assert_not_called()
        assert "节流" not in caplog.text

    def test_throttle_calls_sleep(self):
        """节流时调用 sleep"""
        system = _make_system()
        with patch("src.main.time.sleep") as mock_sleep:
            system._throttle_if_needed(_make_state(cpu=0.9), result=MagicMock())
        mock_sleep.assert_called_once_with(2)


class TestX6NoColorEnvVar:
    """测试 AGENT_NO_COLOR 环境变量"""

    def test_no_color_env_disables_color(self):
        """AGENT_NO_COLOR 环境变量禁用颜色"""
        with patch.dict(os.environ, {"AGENT_NO_COLOR": "1"}):
            with patch("sys.stdout.isatty", return_value=True):
                root_logger = logging.getLogger()
                _setup_logging()
                stream_handlers = [h for h in root_logger.handlers
                                  if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
                assert len(stream_handlers) > 0
                assert stream_handlers[0].formatter._use_color is False


class TestX6SourceCodeStructure:
    """测试源码结构"""

    def test_main_has_colored_formatter(self):
        """main.py 有 ColoredFormatter 类"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "class ColoredFormatter" in content
        assert "_COLORS" in content

    def test_main_has_setup_logging(self):
        """main.py 有 _setup_logging 函数"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "def _setup_logging" in content

    def test_main_has_color_codes(self):
        """main.py 有 ANSI 颜色码定义"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "\\033[31m" in content or "\033[31m" in content  # 红色
        assert "\\033[32m" in content or "\033[32m" in content  # 绿色
        assert "\\033[33m" in content or "\033[33m" in content  # 黄色

    def test_throttle_has_explanation_log(self):
        """_throttle_if_needed 有说明日志"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _throttle_if_needed\(self.*?\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_throttle_if_needed not found"
        body = match.group()
        assert "logger.warning" in body or "logger.info" in body
        assert "节流" in body

    def test_setup_logging_has_tty_detection(self):
        """_setup_logging 有 TTY 检测"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "isatty" in content

    def test_setup_logging_has_no_color_env(self):
        """_setup_logging 支持 AGENT_NO_COLOR 环境变量"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "AGENT_NO_COLOR" in content

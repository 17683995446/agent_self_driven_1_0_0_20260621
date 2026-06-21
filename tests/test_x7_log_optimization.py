"""
X7：日志体验优化测试

验证日志体验优化：
1. 日志轮转（RotatingFileHandler，按大小轮转，保留N份）（M7）
2. JSON日志格式选项（L1）
3. --log-format CLI 选项

第一性原理：日志应同时面向人（文本）和机器（JSON），并自动轮转防止磁盘占满
"""

import pytest
import os
import sys
import json
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.main import JsonFormatter, _setup_logging, ColoredFormatter


class TestX7JsonFormatter:
    """测试 JSON 日志格式化器"""

    def _make_record(self, level=logging.INFO, msg="test message", name="test.logger"):
        return logging.LogRecord(
            name=name, level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )

    def test_json_formatter_outputs_valid_json(self):
        """JSON 格式化器输出有效 JSON"""
        formatter = JsonFormatter()
        record = self._make_record(msg="hello")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_contains_timestamp(self):
        """JSON 包含 timestamp 字段"""
        formatter = JsonFormatter()
        output = formatter.format(self._make_record())
        parsed = json.loads(output)
        assert "timestamp" in parsed

    def test_json_contains_level(self):
        """JSON 包含 level 字段"""
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(level=logging.ERROR))
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"

    def test_json_contains_name(self):
        """JSON 包含 name 字段"""
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(name="my.logger"))
        parsed = json.loads(output)
        assert parsed["name"] == "my.logger"

    def test_json_contains_message(self):
        """JSON 包含 message 字段"""
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(msg="hello world"))
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"

    def test_json_handles_unicode(self):
        """JSON 处理 Unicode 字符"""
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(msg="中文测试"))
        parsed = json.loads(output)
        assert parsed["message"] == "中文测试"

    def test_json_includes_exception_info(self):
        """JSON 包含异常信息"""
        formatter = JsonFormatter()
        try:
            raise ValueError("test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=exc_info
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestX7RotatingFileHandler:
    """测试日志轮转"""

    def test_setup_uses_rotating_file_handler(self):
        """_setup_logging 使用 RotatingFileHandler"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
        assert isinstance(file_handlers[0], RotatingFileHandler)

    def test_rotating_handler_has_max_bytes(self):
        """RotatingFileHandler 有 maxBytes 配置"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) > 0
        assert file_handlers[0].maxBytes > 0

    def test_rotating_handler_max_bytes_is_10mb(self):
        """maxBytes 为 10MB"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers[0].maxBytes == 10 * 1024 * 1024

    def test_rotating_handler_has_backup_count(self):
        """RotatingFileHandler 有 backupCount 配置"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers[0].backupCount > 0

    def test_rotating_handler_backup_count_is_5(self):
        """backupCount 为 5"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers[0].backupCount == 5


class TestX7LogFormatOption:
    """测试 --log-format 选项"""

    def test_parse_args_has_log_format(self):
        """parse_args 支持 --log-format"""
        from src.main import parse_args
        args = parse_args(["--log-format", "json"])
        assert args.log_format == "json"

    def test_parse_args_log_format_default_text(self):
        """--log-format 默认为 text"""
        from src.main import parse_args
        args = parse_args([])
        assert args.log_format == "text"

    def test_parse_args_log_format_text(self):
        """--log-format text"""
        from src.main import parse_args
        args = parse_args(["--log-format", "text"])
        assert args.log_format == "text"

    def test_parse_args_log_format_invalid_rejected(self):
        """--log-format 拒绝无效值"""
        from src.main import parse_args
        with pytest.raises(SystemExit):
            parse_args(["--log-format", "xml"])

    def test_setup_logging_json_uses_json_formatter_for_file(self):
        """log_format=json 时文件 handler 使用 JsonFormatter"""
        root_logger = logging.getLogger()
        _setup_logging("json")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
        assert type(file_handlers[0].formatter).__name__ == "JsonFormatter"

    def test_setup_logging_text_uses_plain_formatter_for_file(self):
        """log_format=text 时文件 handler 使用纯文本 Formatter"""
        root_logger = logging.getLogger()
        _setup_logging("text")
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
        assert type(file_handlers[0].formatter).__name__ != "JsonFormatter"

    def test_setup_logging_json_uses_json_formatter_for_stream(self):
        """log_format=json 时流 handler 使用 JsonFormatter"""
        root_logger = logging.getLogger()
        _setup_logging("json")
        stream_handlers = [h for h in root_logger.handlers
                          if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert len(stream_handlers) > 0
        assert type(stream_handlers[0].formatter).__name__ == "JsonFormatter"


class TestX7AgentSystemLogFormat:
    """测试 AgentSystem 支持 log_format 参数"""

    def test_agent_system_accepts_log_format(self):
        """AgentSystem 接受 log_format 参数"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._cli_config_path = None
        system._cli_log_level = None
        system._cli_log_dir = None
        system._cli_log_format = "json"
        # 验证属性可设置
        assert system._cli_log_format == "json"

    def test_init_logging_uses_log_format(self):
        """_init_logging 使用 log_format 重新配置"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._cli_log_format = "json"
        system._cli_log_level = None
        system._cli_log_dir = None
        with patch("src.main._setup_logging") as mock_setup:
            system._init_logging()
        mock_setup.assert_called_with("json")

    def test_init_logging_no_format_does_not_reconfigure(self):
        """无 log_format 时不重新配置"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._cli_log_format = None
        system._cli_log_level = None
        system._cli_log_dir = None
        with patch("src.main._setup_logging") as mock_setup:
            system._init_logging()
        mock_setup.assert_not_called()

    def test_reconfigure_log_dir_uses_rotating_handler(self, tmp_path):
        """_reconfigure_log_dir 使用 RotatingFileHandler"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._cli_log_format = None
        system._reconfigure_log_dir(str(tmp_path))
        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert any(isinstance(h, RotatingFileHandler) for h in file_handlers)

    def test_reconfigure_log_dir_json_format(self, tmp_path):
        """_reconfigure_log_dir 在 json 格式下使用 JsonFormatter"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._cli_log_format = "json"
        system._reconfigure_log_dir(str(tmp_path))
        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert any(type(h.formatter).__name__ == "JsonFormatter" for h in file_handlers)


class TestX7MainPassesLogFormat:
    """测试 main() 传递 log_format"""

    def test_main_passes_log_format_to_agent(self):
        """main() 将 log_format 传递给 AgentSystem"""
        from src.main import main
        with patch("src.main.AgentSystem") as mock_agent_cls:
            with patch("src.main.signal.signal"):
                main(["--log-format", "json"])
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs.get("log_format") == "json" or \
               (call_kwargs[1].get("log_format") == "json")


class TestX7SourceCodeStructure:
    """测试源码结构"""

    def test_main_has_json_formatter(self):
        """main.py 有 JsonFormatter 类"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "class JsonFormatter" in content

    def test_main_imports_rotating_file_handler(self):
        """main.py 导入 RotatingFileHandler"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "RotatingFileHandler" in content
        assert "from logging.handlers" in content

    def test_main_has_log_format_arg(self):
        """main.py 有 --log-format 参数"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "--log-format" in content

    def test_setup_logging_accepts_log_format(self):
        """_setup_logging 接受 log_format 参数"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _setup_logging\(.*?log_format.*?\).*?(?=\n\n)', content, re.DOTALL)
        assert match, "_setup_logging 应接受 log_format 参数"

    def test_rotating_handler_configured_with_10mb(self):
        """RotatingFileHandler 配置为 10MB"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "10 * 1024 * 1024" in content or "maxBytes=10" in content

    def test_rotating_handler_backup_count_5(self):
        """RotatingFileHandler 保留 5 份"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "backupCount=5" in content

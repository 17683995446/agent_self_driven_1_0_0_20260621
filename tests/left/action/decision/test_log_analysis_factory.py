"""
日志异常检测任务工厂测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.left.action.decision.log_analysis_factory import (
    LogEntry,
    LogAnalysisResult,
    LogParser,
    StandardLogParser,
    LogAnomalyDetector,
    LogAnalysisTaskFactory,
)
from src.platform.support.models.base.state import EnvironmentState, GapState, LogState


class TestLogEntry:
    """测试日志条目"""

    def test_normal_creation(self):
        entry = LogEntry(timestamp="2024-01-01", level="ERROR", message="fail")
        assert entry.level == "ERROR"
        assert entry.source == ""

    def test_to_dict(self):
        entry = LogEntry(
            timestamp="2024-01-01", level="INFO", message="ok", source="app.log"
        )
        data = entry.to_dict()
        assert data["level"] == "INFO"
        assert data["source"] == "app.log"


class TestLogAnalysisResult:
    """测试日志分析结果"""

    def test_empty(self):
        result = LogAnalysisResult()
        assert result.total_lines == 0
        assert result.error_rate == 0.0

    def test_to_dict(self):
        result = LogAnalysisResult(
            total_lines=100,
            level_counts={"ERROR": 10, "INFO": 90},
            error_rate=0.1,
        )
        data = result.to_dict()
        assert data["total_lines"] == 100
        assert data["error_rate"] == 0.1
        assert data["level_counts"]["ERROR"] == 10


class TestStandardLogParser:
    """测试标准日志解析器"""

    def setup_method(self):
        self.parser = StandardLogParser()

    def test_standard_format(self):
        """测试标准格式"""
        line = "2024-01-01 12:00:00 - app - ERROR - something broke"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "ERROR"
        assert "something broke" in entry.message

    def test_simple_format_error(self):
        """测试简单格式ERROR"""
        line = "ERROR connection refused"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "ERROR"

    def test_simple_format_warning(self):
        """测试简单格式WARNING"""
        line = "WARNING disk almost full"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "WARNING"

    def test_simple_format_info(self):
        """测试简单格式INFO"""
        line = "INFO server started"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "INFO"

    def test_simple_format_debug(self):
        """测试简单格式DEBUG"""
        line = "DEBUG checking value"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "DEBUG"

    def test_non_log_line(self):
        """测试非日志行"""
        line = "just some random text"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is None

    def test_empty_line(self):
        """测试空行"""
        entry = self.parser.parse_line("", "app.log")
        assert entry is None

    def test_critical_level(self):
        """测试CRITICAL级别"""
        line = "CRITICAL system failure"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "CRITICAL"

    def test_fatal_level(self):
        """测试FATAL级别"""
        line = "FATAL system failure"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "FATAL"

    def test_warn_level(self):
        """测试WARN级别"""
        line = "WARN something"
        entry = self.parser.parse_line(line, "app.log")
        assert entry is not None
        assert entry.level == "WARN"


class TestLogAnomalyDetector:
    """测试日志异常检测器"""

    def setup_method(self):
        self.detector = LogAnomalyDetector()

    def test_no_anomaly(self):
        """测试无异常"""
        result = LogAnalysisResult(error_rate=0.01, warning_rate=0.05)
        alerts = self.detector.detect(result)
        assert len(alerts) == 0

    def test_high_error_rate(self):
        """测试高错误率"""
        result = LogAnalysisResult(error_rate=0.15)
        alerts = self.detector.detect(result)
        assert any("HIGH_ERROR_RATE" in a for a in alerts)

    def test_high_warning_rate(self):
        """测试高警告率"""
        result = LogAnalysisResult(warning_rate=0.35)
        alerts = self.detector.detect(result)
        assert any("HIGH_WARNING_RATE" in a for a in alerts)

    def test_rising_trend(self):
        """测试上升趋势"""
        rates = [0.01, 0.02, 0.10, 0.20]
        for rate in rates:
            result = LogAnalysisResult(error_rate=rate)
            self.detector.detect(result)
        assert result.trend == "rising"

    def test_stable_trend(self):
        """测试稳定趋势"""
        rates = [0.05, 0.05, 0.05, 0.05]
        for rate in rates:
            result = LogAnalysisResult(error_rate=rate)
            self.detector.detect(result)
        assert result.trend == "stable"

    def test_repeated_errors(self):
        """测试重复错误"""
        result = LogAnalysisResult(
            top_error_patterns=[("connection failed", 15)]
        )
        alerts = self.detector.detect(result)
        assert any("REPEATED_ERROR" in a for a in alerts)

    def test_repeated_errors_below_threshold(self):
        """测试重复错误低于阈值"""
        result = LogAnalysisResult(
            top_error_patterns=[("minor issue", 5)]
        )
        alerts = self.detector.detect(result)
        assert not any("REPEATED_ERROR" in a for a in alerts)


class TestLogAnalysisTaskFactory:
    """测试日志分析任务工厂"""

    def setup_method(self):
        self.factory = LogAnalysisTaskFactory(log_dir="logs")

    def test_create_tasks_high_gap(self):
        """测试高安全缺口时创建任务"""
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "log_anomaly_detection"

    def test_create_tasks_low_gap_high_error(self):
        """测试低缺口高错误率时创建任务"""
        state = EnvironmentState(logs=LogState(error_rate=0.1))
        tasks = self.factory.create_tasks(GapState(safety=0.1), state)
        assert len(tasks) == 1

    def test_create_tasks_low_gap_low_error_with_history(self):
        """测试有历史结果时低缺口也创建任务"""
        self.factory._last_result = LogAnalysisResult()
        tasks = self.factory.create_tasks(GapState(safety=0.1), EnvironmentState())
        assert len(tasks) == 1

    def test_create_tasks_skip(self):
        """测试低缺口低错误无历史时不创建"""
        tasks = self.factory.create_tasks(GapState(safety=0.1), EnvironmentState())
        assert len(tasks) == 0

    def test_analyze_nonexistent_dir(self):
        """测试分析不存在的目录"""
        factory = LogAnalysisTaskFactory(log_dir="/nonexistent/path")
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is False

    def test_analyze_real_logs(self, tmp_path):
        """测试分析真实日志"""
        log_file = tmp_path / "app.log"
        log_file.write_text(
            "2024-01-01 12:00:00 - app - INFO - started\n"
            "2024-01-01 12:00:01 - app - INFO - running\n"
            "2024-01-01 12:00:02 - app - INFO - processing\n"
            "2024-01-01 12:00:03 - app - INFO - done\n"
            "2024-01-01 12:00:04 - app - INFO - finished\n"
            "2024-01-01 12:00:05 - app - INFO - complete\n"
            "2024-01-01 12:00:06 - app - INFO - ok\n"
            "2024-01-01 12:00:07 - app - INFO - success\n"
            "2024-01-01 12:00:08 - app - INFO - running\n"
            "2024-01-01 12:01:00 - app - ERROR - connection failed\n"
            "2024-01-01 12:02:00 - app - WARNING - slow response\n"
        )
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["total_lines"] == 11
        assert result.data["level_counts"]["ERROR"] == 1
        assert result.data["level_counts"]["WARNING"] == 1

    def test_analyze_empty_dir(self, tmp_path):
        """测试分析空目录"""
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_lines"] == 0

    def test_analyze_dir_with_non_log_files(self, tmp_path):
        """测试目录中有非日志文件"""
        (tmp_path / "readme.txt").write_text("not a log")
        (tmp_path / "app.log").write_text("INFO started\n")
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["files_scanned"] == 1

    def test_high_error_rate_triggers_alert(self, tmp_path):
        """测试高错误率触发告警"""
        lines = ["ERROR something broke\n"] * 20 + ["INFO ok\n"] * 10
        (tmp_path / "app.log").write_text("".join(lines))
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is False
        assert len(result.data["alerts"]) > 0

    def test_recent_errors_extracted(self, tmp_path):
        """测试最近错误提取"""
        lines = []
        for i in range(15):
            lines.append(f"ERROR error number {i}\n")
        (tmp_path / "app.log").write_text("".join(lines))
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["recent_errors"]) <= 10

    def test_error_patterns_extracted(self, tmp_path):
        """测试错误模式提取"""
        (tmp_path / "app.log").write_text(
            "ERROR connection to 192.168.1.1 failed\n"
            "ERROR connection to 192.168.1.2 failed\n"
            "ERROR connection to 10.0.0.1 failed\n"
        )
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["top_error_patterns"]) >= 1
        top = result.data["top_error_patterns"][0]
        assert top["count"] == 3

    def test_get_last_result(self):
        """测试获取上次结果"""
        assert self.factory.get_last_result() is None

    def test_pattern_normalization(self):
        """测试模式归一化"""
        factory = LogAnalysisTaskFactory(log_dir="logs")
        normalized = factory._normalize_pattern("error at 0x1234abcd in line 42")
        assert "N" in normalized
        assert "HEXADDR" in normalized

    def test_unreadable_file_skipped(self, tmp_path):
        """测试不可读文件被跳过"""
        log_file = tmp_path / "app.log"
        log_file.write_text("INFO ok\n")
        factory = LogAnalysisTaskFactory(log_dir=str(tmp_path))
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.data["total_lines"] == 0

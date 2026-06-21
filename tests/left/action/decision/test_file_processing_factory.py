"""
文件处理管道任务工厂测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.left.action.decision.file_processing_factory import (
    FileInfo,
    FileProcessingReport,
    FileAnalyzer,
    StandardFileAnalyzer,
    FileProcessingTaskFactory,
)
from src.platform.support.models.base.state import EnvironmentState, GapState


class TestFileInfo:
    """测试文件信息"""

    def test_normal_creation(self):
        info = FileInfo(name="test.py", path="/a/test.py", extension=".py", size_bytes=100)
        assert info.extension == ".py"
        assert info.is_empty is False

    def test_to_dict(self):
        info = FileInfo(
            name="a.log", path="/a/a.log", extension=".log", size_bytes=2048,
            is_empty=False, is_large=True, line_count=50,
        )
        data = info.to_dict()
        assert data["size_kb"] == 2.0
        assert data["is_large"] is True
        assert data["line_count"] == 50


class TestFileProcessingReport:
    """测试文件处理报告"""

    def test_empty(self):
        report = FileProcessingReport()
        assert report.total_files == 0
        assert report.anomalies == []

    def test_to_dict(self):
        report = FileProcessingReport(
            target_dir="src", total_files=10, total_size_bytes=1048576,
            type_distribution={".py": 10},
        )
        data = report.to_dict()
        assert data["total_files"] == 10
        assert data["total_size_mb"] == 1.0
        assert data["type_distribution"][".py"] == 10


class TestStandardFileAnalyzer:
    """测试标准文件分析器"""

    def setup_method(self):
        self.analyzer = StandardFileAnalyzer()

    def test_analyze_normal_file(self, tmp_path):
        """测试分析正常文件"""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n")
        info = self.analyzer.analyze(str(f))
        assert info.extension == ".py"
        assert info.size_bytes > 0
        assert info.is_empty is False
        assert info.is_large is False
        assert info.is_readable is True
        assert info.line_count == 3
        assert len(info.md5_prefix) == 8

    def test_analyze_empty_file(self, tmp_path):
        """测试分析空文件"""
        f = tmp_path / "empty.txt"
        f.write_text("")
        info = self.analyzer.analyze(str(f))
        assert info.is_empty is True
        assert info.size_bytes == 0
        assert info.md5_prefix == ""

    def test_analyze_large_file(self, tmp_path):
        """测试分析大文件"""
        f = tmp_path / "big.log"
        f.write_text("x" * 200000)
        info = self.analyzer.analyze(str(f))
        assert info.is_large is True

    def test_analyze_no_extension(self, tmp_path):
        """测试无扩展名文件"""
        f = tmp_path / "Makefile"
        f.write_text("all: build\n")
        info = self.analyzer.analyze(str(f))
        assert info.extension == ""

    def test_analyze_nonexistent_file(self):
        """测试分析不存在的文件"""
        info = self.analyzer.analyze("/nonexistent/file.txt")
        assert info.size_bytes == 0
        assert info.is_empty is True

    def test_analyze_unreadable_file(self, tmp_path):
        """测试不可读文件"""
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02")
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            info = self.analyzer.analyze(str(f))
        assert info.is_readable is False

    def test_md5_prefix_consistency(self, tmp_path):
        """测试MD5前缀一致性"""
        f1 = tmp_path / "a.txt"
        f1.write_text("same content")
        f2 = tmp_path / "b.txt"
        f2.write_text("same content")
        info1 = self.analyzer.analyze(str(f1))
        info2 = self.analyzer.analyze(str(f2))
        assert info1.md5_prefix == info2.md5_prefix

    def test_line_count_binary_file(self, tmp_path):
        """测试二进制文件行数"""
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\x03")
        info = self.analyzer.analyze(str(f))
        assert info.is_readable is True
        assert info.line_count >= 0


class TestFileProcessingTaskFactory:
    """测试文件处理管道任务工厂"""

    def setup_method(self):
        self.factory = FileProcessingTaskFactory(target_dir="src")

    def test_create_tasks_high_gap(self):
        """测试高收益缺口时创建任务"""
        tasks = self.factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "file_processing_pipeline"

    def test_create_tasks_low_gap_with_no_history(self):
        """测试低缺口无历史时创建任务"""
        tasks = self.factory.create_tasks(GapState(gain=0.05), EnvironmentState())
        assert len(tasks) == 1

    def test_create_tasks_low_gap_with_history(self):
        """测试低缺口有历史时不创建任务"""
        self.factory._last_report = FileProcessingReport()
        tasks = self.factory.create_tasks(GapState(gain=0.05), EnvironmentState())
        assert len(tasks) == 0

    def test_process_nonexistent_dir(self):
        """测试处理不存在的目录"""
        factory = FileProcessingTaskFactory(target_dir="/nonexistent/path")
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is False

    def test_process_real_files(self, tmp_path):
        """测试处理真实文件"""
        (tmp_path / "a.py").write_text("print(1)\n")
        (tmp_path / "b.py").write_text("print(2)\nprint(3)\n")
        (tmp_path / "c.log").write_text("INFO ok\n")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_files"] == 3
        assert ".py" in result.data["type_distribution"]
        assert result.data["type_distribution"][".py"] == 2

    def test_process_empty_dir(self, tmp_path):
        """测试处理空目录"""
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_files"] == 0

    def test_detect_empty_files(self, tmp_path):
        """测试检测空文件"""
        (tmp_path / "empty.txt").write_text("")
        (tmp_path / "normal.txt").write_text("content")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["empty_files"]) == 1
        assert any("EMPTY_FILES" in a for a in result.data["anomalies"])

    def test_detect_large_files(self, tmp_path):
        """测试检测大文件"""
        (tmp_path / "big.log").write_text("x" * 200000)
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["large_files"]) == 1
        assert any("LARGE_FILES" in a for a in result.data["anomalies"])

    def test_skip_pycache_dirs(self, tmp_path):
        """测试跳过__pycache__目录"""
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.pyc").write_text("cached")
        (tmp_path / "main.py").write_text("print(1)")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["total_files"] == 1
        assert ".pyc" not in result.data["type_distribution"]

    def test_nested_directories(self, tmp_path):
        """测试嵌套目录"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.py").write_text("a")
        (sub / "b.py").write_text("b")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["total_files"] == 2

    def test_type_distribution(self, tmp_path):
        """测试类型分布统计"""
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.log").write_text("c")
        (tmp_path / "d.json").write_text("{}")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        dist = result.data["type_distribution"]
        assert dist[".py"] == 2
        assert dist[".log"] == 1
        assert dist[".json"] == 1

    def test_get_last_report(self):
        """测试获取上次报告"""
        assert self.factory.get_last_report() is None

    def test_set_target_dir(self):
        """测试设置目标目录"""
        self.factory.set_target_dir("/new/path")
        assert self.factory._target_dir == "/new/path"

    def test_no_anomalies_normal(self, tmp_path):
        """测试正常文件无异常"""
        (tmp_path / "normal.py").write_text("print(1)\n")
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["anomalies"]) == 0
        assert len(result.data["empty_files"]) == 0
        assert len(result.data["large_files"]) == 0

    def test_total_size_calculation(self, tmp_path):
        """测试总大小计算"""
        (tmp_path / "a.txt").write_text("a" * 1048576)  # 1MB
        (tmp_path / "b.txt").write_text("b" * 524288)    # 0.5MB
        factory = FileProcessingTaskFactory(target_dir=str(tmp_path))
        tasks = factory.create_tasks(GapState(gain=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["total_size_mb"] >= 1.0

    def test_custom_analyzer(self):
        """测试自定义分析器"""
        mock_analyzer = MagicMock(spec=FileAnalyzer)
        mock_analyzer.analyze.return_value = FileInfo(
            name="x", path="/x", extension=".x", size_bytes=0, is_empty=True,
        )
        factory = FileProcessingTaskFactory(
            target_dir=".", analyzer=mock_analyzer,
        )
        assert factory._analyzer is mock_analyzer

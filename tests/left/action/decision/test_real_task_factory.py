"""
真实任务工厂测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.left.action.decision.real_task_factory import (
    RealTaskFactory,
    RealTaskFactoryBase,
    SystemHealthCheckFactory,
    LogScanFactory,
    FileInventoryFactory,
    DiskUsageReportFactory,
    ProcessAuditFactory,
    _safe_import_psutil,
)
from src.platform.support.models.base.state import (
    EnvironmentState, GapState, SystemState, LogState,
)
from src.platform.support.models.base.task import TaskResult


class TestSystemHealthCheckFactory:
    """测试系统健康检查工厂"""

    def setup_method(self):
        self.factory = SystemHealthCheckFactory()

    def test_task_type_name(self):
        assert self.factory.task_type_name() == "system_health_check"

    def test_create_tasks_normal(self):
        """测试正常创建任务"""
        tasks = self.factory.create_tasks(GapState(), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "system_health_check"
        assert tasks[0].execute_fn is not None

    def test_execute_task_with_psutil(self):
        """测试有psutil时执行"""
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 45.0
        mock_mem = MagicMock()
        mock_mem.percent = 60.0
        mock_mem.available = 1073741824
        mock_disk = MagicMock()
        mock_disk.percent = 70.0
        mock_disk.free = 10737418240
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_psutil.disk_usage.return_value = mock_disk

        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=mock_psutil,
        ):
            tasks = self.factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["cpu_percent"] == 45.0
        assert result.data["memory_percent"] == 60.0

    def test_execute_task_without_psutil(self):
        """测试无psutil时降级执行"""
        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=None,
        ):
            tasks = self.factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert "python_version" in result.data
        assert result.data["cpu_percent"] == -1.0


class TestLogScanFactory:
    """测试日志扫描工厂"""

    def setup_method(self):
        self.factory = LogScanFactory()

    def test_task_type_name(self):
        assert self.factory.task_type_name() == "log_scan"

    def test_create_tasks_high_gap(self):
        """测试高安全缺口时创建任务"""
        gaps = GapState(safety=0.5)
        tasks = self.factory.create_tasks(gaps, EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "log_scan"

    def test_create_tasks_low_gap_low_error(self):
        """测试低缺口低错误率时不创建任务"""
        gaps = GapState(safety=0.1)
        state = EnvironmentState(logs=LogState(error_rate=0.01))
        tasks = self.factory.create_tasks(gaps, state)
        assert len(tasks) == 0

    def test_scan_logs_with_real_files(self, tmp_path):
        """测试扫描真实日志文件"""
        log_file = tmp_path / "test.log"
        log_file.write_text("INFO start\nERROR something broke\nWARNING小心\n")
        factory = LogScanFactory()
        with patch.object(factory, "_find_log_dir", return_value=str(tmp_path)):
            tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["counts"]["ERROR"] == 1
        assert result.data["counts"]["WARNING"] == 1
        assert result.data["counts"]["INFO"] == 1

    def test_scan_logs_empty_dir(self, tmp_path):
        """测试扫描空目录"""
        factory = LogScanFactory()
        with patch.object(factory, "_find_log_dir", return_value=str(tmp_path)):
            tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["counts"]["ERROR"] == 0
        assert result.data["files_scanned"] == 0

    def test_scan_logs_nonexistent_dir(self):
        """测试扫描不存在的目录"""
        factory = LogScanFactory()
        with patch.object(factory, "_find_log_dir", return_value="/nonexistent/path"):
            tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is False


class TestFileInventoryFactory:
    """测试文件清单工厂"""

    def setup_method(self):
        self.factory = FileInventoryFactory()

    def test_task_type_name(self):
        assert self.factory.task_type_name() == "file_inventory"

    def test_create_tasks(self):
        tasks = self.factory.create_tasks(GapState(), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "file_inventory"

    def test_scan_files_real(self, tmp_path):
        """测试扫描真实文件"""
        (tmp_path / "a.py").write_text("print(1)")
        (tmp_path / "b.py").write_text("print(2)")
        (tmp_path / "c.log").write_text("log")
        factory = FileInventoryFactory()
        with patch.object(factory, "_find_target_dir", return_value=str(tmp_path)):
            tasks = factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_files"] == 3
        assert ".py" in result.data["type_distribution"]

    def test_scan_files_nonexistent_dir(self):
        """测试扫描不存在的目录"""
        factory = FileInventoryFactory()
        with patch.object(factory, "_find_target_dir", return_value="/nonexistent"):
            tasks = factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is False

    def test_large_file_detection(self, tmp_path):
        """测试大文件检测"""
        large_content = "x" * 200000
        (tmp_path / "big.log").write_text(large_content)
        factory = FileInventoryFactory()
        with patch.object(factory, "_find_target_dir", return_value=str(tmp_path)):
            tasks = factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert len(result.data["large_files"]) >= 1


class TestDiskUsageReportFactory:
    """测试磁盘使用报告工厂"""

    def setup_method(self):
        self.factory = DiskUsageReportFactory()

    def test_task_type_name(self):
        assert self.factory.task_type_name() == "disk_usage_report"

    def test_create_tasks_high_efficiency_gap(self):
        """测试高能效缺口时创建任务"""
        gaps = GapState(efficiency=0.5)
        tasks = self.factory.create_tasks(gaps, EnvironmentState())
        assert len(tasks) == 1

    def test_create_tasks_low_efficiency_gap(self):
        """测试低能效缺口时不创建任务"""
        gaps = GapState(efficiency=0.1)
        tasks = self.factory.create_tasks(gaps, EnvironmentState())
        assert len(tasks) == 0

    def test_execute_with_psutil(self):
        """测试有psutil时执行"""
        mock_psutil = MagicMock()
        mock_disk = MagicMock()
        mock_disk.total = 107374182400
        mock_disk.used = 53687091200
        mock_disk.free = 53687091200
        mock_disk.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_disk

        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=mock_psutil,
        ):
            tasks = self.factory.create_tasks(GapState(efficiency=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["percent"] == 50.0

    def test_execute_without_psutil(self):
        """测试无psutil时降级执行"""
        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=None,
        ):
            tasks = self.factory.create_tasks(GapState(efficiency=0.5), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert "percent" in result.data


class TestProcessAuditFactory:
    """测试进程审计工厂"""

    def setup_method(self):
        self.factory = ProcessAuditFactory()

    def test_task_type_name(self):
        assert self.factory.task_type_name() == "process_audit"

    def test_create_tasks(self):
        tasks = self.factory.create_tasks(GapState(), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "process_audit"

    def test_execute_with_psutil(self):
        """测试有psutil时执行"""
        mock_psutil = MagicMock()
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1, "name": "test", "cpu_percent": 50.0, "memory_percent": 10.0}
        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception

        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=mock_psutil,
        ):
            tasks = self.factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_processes"] == 1

    def test_execute_without_psutil(self):
        """测试无psutil时降级执行"""
        with patch(
            "src.left.action.decision.real_task_factory._safe_import_psutil",
            return_value=None,
        ):
            tasks = self.factory.create_tasks(GapState(), EnvironmentState())
            result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["total_processes"] == 1


class TestRealTaskFactory:
    """测试真实任务工厂聚合器"""

    def test_create_tasks(self):
        """测试聚合创建任务"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(GapState(safety=0.5, efficiency=0.5), EnvironmentState())
        assert len(tasks) >= 3

    def test_get_factory_names(self):
        """测试获取工厂名称"""
        factory = RealTaskFactory()
        names = factory.get_factory_names()
        assert "system_health_check" in names
        assert "log_scan" in names
        assert "file_inventory" in names

    def test_add_factory(self):
        """测试添加自定义工厂"""

        class CustomFactory(RealTaskFactoryBase):
            def task_type_name(self) -> str:
                return "custom"

            def create_tasks(self, gaps, state):
                return []

        factory = RealTaskFactory()
        factory.add_factory(CustomFactory())
        names = factory.get_factory_names()
        assert "custom" in names

    def test_task_diversity(self):
        """测试任务多样性"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(GapState(safety=0.5, efficiency=0.5), EnvironmentState())
        names = {t.name for t in tasks}
        assert len(names) >= 3

    def test_tasks_have_execute_fn(self):
        """测试所有任务都有执行函数"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(GapState(safety=0.5, efficiency=0.5), EnvironmentState())
        for task in tasks:
            assert task.execute_fn is not None

    def test_empty_gaps_produces_tasks(self):
        """测试空缺口仍产生基础任务"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(GapState(), EnvironmentState())
        assert len(tasks) >= 2


class TestSafeImportPsutil:
    """测试psutil安全导入"""

    def test_returns_psutil_if_available(self):
        result = _safe_import_psutil()
        # 在测试环境中psutil可能可用也可能不可用
        assert result is None or hasattr(result, "cpu_percent")

    def test_returns_none_if_not_available(self):
        """测试psutil不可用时返回None"""
        import sys
        original = sys.modules.get("psutil")
        sys.modules["psutil"] = None
        try:
            result = _safe_import_psutil()
            assert result is None
        finally:
            if original is not None:
                sys.modules["psutil"] = original
            else:
                sys.modules.pop("psutil", None)

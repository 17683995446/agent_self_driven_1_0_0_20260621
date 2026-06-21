"""
HTTP健康监控任务工厂测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
from unittest.mock import patch, MagicMock

from src.left.action.decision.health_check_factory import (
    HealthCheckTarget,
    HealthCheckRecord,
    HealthCheckSummary,
    HealthCheckExecutor,
    HttpHealthCheckExecutor,
    HealthCheckTaskFactory,
)
from src.platform.support.models.base.state import EnvironmentState, GapState


class TestHealthCheckTarget:
    """测试健康检查目标"""

    def test_normal_creation(self):
        target = HealthCheckTarget(name="test", url="https://example.com")
        assert target.name == "test"
        assert target.expected_status == 200
        assert target.timeout == 10.0

    def test_to_dict(self):
        target = HealthCheckTarget(
            name="api", url="https://api.example.com", expected_status=204, timeout=5.0
        )
        data = target.to_dict()
        assert data["name"] == "api"
        assert data["expected_status"] == 204
        assert data["timeout"] == 5.0

    def test_boundary_default_values(self):
        target = HealthCheckTarget(name="x", url="https://x.com")
        assert target.expected_status == 200
        assert target.timeout == 10.0


class TestHealthCheckRecord:
    """测试健康检查记录"""

    def test_normal_creation(self):
        record = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=True, status_code=200, response_time=0.5,
        )
        assert record.success is True
        assert record.error == ""

    def test_to_dict(self):
        record = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=False, status_code=500, response_time=0.3, error="Server Error",
        )
        data = record.to_dict()
        assert data["success"] is False
        assert data["status_code"] == 500
        assert data["error"] == "Server Error"
        assert data["response_time"] == 0.3

    def test_boundary_zero_response_time(self):
        record = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=0.0,
            success=True, status_code=200, response_time=0.0,
        )
        assert record.response_time == 0.0


class TestHealthCheckSummary:
    """测试健康检查汇总"""

    def test_empty_summary(self):
        summary = HealthCheckSummary()
        assert summary.total == 0
        assert summary.success == 0

    def test_to_dict_empty(self):
        summary = HealthCheckSummary()
        data = summary.to_dict()
        assert data["availability"] == 0.0
        assert data["records"] == []

    def test_to_dict_with_records(self):
        record = HealthCheckRecord(
            target_name="t", url="https://x.com", timestamp=1.0,
            success=True, status_code=200, response_time=0.1,
        )
        summary = HealthCheckSummary(total=1, success=1, failure=0, records=[record])
        data = summary.to_dict()
        assert data["availability"] == 1.0
        assert len(data["records"]) == 1


class TestHttpHealthCheckExecutor:
    """测试HTTP健康检查执行器"""

    def test_check_success(self):
        """测试成功检查"""
        target = HealthCheckTarget(name="test", url="https://example.com")
        executor = HttpHealthCheckExecutor()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            record = executor.check(target)
        assert record.success is True
        assert record.status_code == 200
        assert record.error == ""

    def test_check_http_error(self):
        """测试HTTP错误"""
        from urllib import error as url_error
        target = HealthCheckTarget(name="test", url="https://example.com")
        executor = HttpHealthCheckExecutor()
        with patch("urllib.request.urlopen", side_effect=url_error.HTTPError(None, 500, "Error", {}, None)):
            record = executor.check(target)
        assert record.success is False
        assert record.status_code == 500

    def test_check_url_error(self):
        """测试URL错误"""
        from urllib import error as url_error
        target = HealthCheckTarget(name="test", url="https://nonexistent.invalid")
        executor = HttpHealthCheckExecutor()
        with patch("urllib.request.urlopen", side_effect=url_error.URLError("Connection refused")):
            record = executor.check(target)
        assert record.success is False
        assert record.status_code == 0
        assert "URLError" in record.error

    def test_check_generic_exception(self):
        """测试通用异常"""
        target = HealthCheckTarget(name="test", url="https://example.com")
        executor = HttpHealthCheckExecutor()
        with patch("urllib.request.urlopen", side_effect=RuntimeError("Unexpected")):
            record = executor.check(target)
        assert record.success is False
        assert "Exception" in record.error

    def test_check_wrong_status(self):
        """测试状态码不匹配"""
        target = HealthCheckTarget(
            name="test", url="https://example.com", expected_status=204
        )
        executor = HttpHealthCheckExecutor()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            record = executor.check(target)
        assert record.success is False
        assert record.status_code == 200


class TestHealthCheckTaskFactory:
    """测试健康监控任务工厂"""

    def setup_method(self):
        self.mock_executor = MagicMock(spec=HealthCheckExecutor)
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=True, status_code=200, response_time=0.1,
        )
        self.targets = [HealthCheckTarget(name="test", url="https://x.com")]
        self.factory = HealthCheckTaskFactory(
            targets=self.targets, executor=self.mock_executor
        )

    def test_create_tasks_high_gap(self):
        """测试高安全缺口时创建任务"""
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "http_health_check"

    def test_create_tasks_low_gap_no_failures(self):
        """测试低缺口无失败时不创建任务"""
        tasks = self.factory.create_tasks(GapState(safety=0.05), EnvironmentState())
        assert len(tasks) == 0

    def test_create_tasks_low_gap_with_failures(self):
        """测试低缺口但有失败时创建任务"""
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=False, status_code=500, response_time=0.1, error="err",
        )
        self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())[0].execute_fn()
        tasks = self.factory.create_tasks(GapState(safety=0.05), EnvironmentState())
        assert len(tasks) == 1

    def test_execute_all_success(self):
        """测试全部成功"""
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is True
        assert result.data["availability"] == 1.0
        assert result.data["alerts"] == []

    def test_execute_with_failure(self):
        """测试有失败"""
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=False, status_code=500, response_time=0.1, error="err",
        )
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.success is False
        assert result.data["availability"] == 0.0

    def test_alert_on_consecutive_failures(self):
        """测试连续失败触发告警"""
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=False, status_code=0, response_time=0.0, error="conn refused",
        )
        for _ in range(HealthCheckTaskFactory.MAX_FAILURE_STREAK):
            tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            tasks[0].execute_fn()
        streaks = self.factory.get_failure_streaks()
        assert streaks["test"] >= HealthCheckTaskFactory.MAX_FAILURE_STREAK
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert len(result.data["alerts"]) >= 1

    def test_streak_reset_on_success(self):
        """测试成功后重置连续失败计数"""
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=False, status_code=500, response_time=0.1, error="err",
        )
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        tasks[0].execute_fn()
        assert self.factory.get_failure_streaks()["test"] == 1
        self.mock_executor.check.return_value = HealthCheckRecord(
            target_name="test", url="https://x.com", timestamp=1000.0,
            success=True, status_code=200, response_time=0.1,
        )
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        tasks[0].execute_fn()
        assert self.factory.get_failure_streaks()["test"] == 0

    def test_get_targets(self):
        targets = self.factory.get_targets()
        assert len(targets) == 1
        assert targets[0].name == "test"

    def test_add_target(self):
        new_target = HealthCheckTarget(name="new", url="https://new.com")
        self.factory.add_target(new_target)
        assert len(self.factory.get_targets()) == 2

    def test_get_history(self):
        tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        tasks[0].execute_fn()
        history = self.factory.get_history()
        assert len(history) == 1

    def test_history_capped_at_100(self):
        """测试历史记录上限"""
        for _ in range(120):
            tasks = self.factory.create_tasks(GapState(safety=0.5), EnvironmentState())
            tasks[0].execute_fn()
        assert len(self.factory.get_history()) <= 100

    def test_default_targets(self):
        """测试默认目标"""
        factory = HealthCheckTaskFactory()
        targets = factory.get_targets()
        assert len(targets) >= 1
        assert all(isinstance(t, HealthCheckTarget) for t in targets)

    def test_multiple_targets(self):
        """测试多目标监控"""
        targets = [
            HealthCheckTarget(name="a", url="https://a.com"),
            HealthCheckTarget(name="b", url="https://b.com"),
            HealthCheckTarget(name="c", url="https://c.com"),
        ]
        factory = HealthCheckTaskFactory(targets=targets, executor=self.mock_executor)
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["summary"]["total"] == 3

    def test_empty_targets(self):
        """测试空目标列表"""
        factory = HealthCheckTaskFactory(targets=[], executor=self.mock_executor)
        tasks = factory.create_tasks(GapState(safety=0.5), EnvironmentState())
        result = tasks[0].execute_fn()
        assert result.data["summary"]["total"] == 0
        assert result.success is True

"""
系统健康检查与自诊断测试

验证健康检查、自诊断、自动修复的正确性
"""

import pytest
import time

from src.left.action.execution.health import (
    HealthStatus, ComponentHealth, HealthCheck, SelfDiagnostics,
    MemoryHealthCheck, CPUHealthCheck, DiskHealthCheck,
)


class MockHealthCheck(HealthCheck):
    """模拟健康检查"""

    def __init__(self, name: str, status: HealthStatus = HealthStatus.HEALTHY, message: str = "OK"):
        super().__init__(name)
        self._status = status
        self._message = message
        self.check_count = 0

    def _do_check(self) -> tuple:
        self.check_count += 1
        return self._status, self._message, {"count": self.check_count}


class TestComponentHealth:
    """测试组件健康状态"""

    def test_to_dict(self):
        health = ComponentHealth(
            name="test", status=HealthStatus.HEALTHY,
            message="OK", metrics={"cpu": 0.5},
        )
        d = health.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "healthy"
        assert d["metrics"]["cpu"] == 0.5


class TestHealthCheck:
    """测试健康检查基类"""

    def test_check_healthy(self):
        check = MockHealthCheck("comp1", HealthStatus.HEALTHY)
        result = check.check()
        assert result.status == HealthStatus.HEALTHY
        assert result.name == "comp1"
        assert result.response_time_ms >= 0

    def test_check_failed(self):
        check = MockHealthCheck("comp2", HealthStatus.FAILED, "broken")
        result = check.check()
        assert result.status == HealthStatus.FAILED
        assert result.message == "broken"

    def test_check_exception(self):
        class BadCheck(HealthCheck):
            def _do_check(self):
                raise ValueError("boom")

        check = BadCheck("bad")
        result = check.check()
        assert result.status == HealthStatus.FAILED
        assert "boom" in result.message


class TestSelfDiagnostics:
    """测试自诊断系统"""

    def setup_method(self):
        self.diag = SelfDiagnostics(check_interval=3600)  # 长间隔，避免自动触发

    def teardown_method(self):
        self.diag.stop()

    def test_register_check(self):
        check = MockHealthCheck("c1")
        self.diag.register_check(check)
        assert "c1" in self.diag._checks

    def test_run_all_checks(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.register_check(MockHealthCheck("c2", HealthStatus.DEGRADED))

        results = self.diag.run_all_checks()
        assert len(results) == 2
        assert results["c1"].status == HealthStatus.HEALTHY
        assert results["c2"].status == HealthStatus.DEGRADED

    def test_overall_status_healthy(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.run_all_checks()
        assert self.diag.get_overall_status() == HealthStatus.HEALTHY

    def test_overall_status_degraded(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.register_check(MockHealthCheck("c2", HealthStatus.DEGRADED))
        self.diag.run_all_checks()
        assert self.diag.get_overall_status() == HealthStatus.DEGRADED

    def test_overall_status_failed(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.register_check(MockHealthCheck("c2", HealthStatus.FAILED))
        self.diag.run_all_checks()
        assert self.diag.get_overall_status() == HealthStatus.FAILED

    def test_overall_status_unhealthy(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.UNHEALTHY))
        self.diag.run_all_checks()
        assert self.diag.get_overall_status() == HealthStatus.UNHEALTHY

    def test_auto_heal(self):
        healed = [False]

        def healer(health):
            healed[0] = True
            return True

        self.diag.register_check(MockHealthCheck("c1", HealthStatus.DEGRADED))
        self.diag.register_healer("c1", healer)
        self.diag.run_all_checks()

        assert healed[0] is True

    def test_auto_heal_failure(self):
        def healer(health):
            return False

        self.diag.register_check(MockHealthCheck("c1", HealthStatus.DEGRADED))
        self.diag.register_healer("c1", healer)
        # 不应抛出异常
        self.diag.run_all_checks()

    def test_get_report(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.run_all_checks()

        report = self.diag.get_report()
        assert "timestamp" in report
        assert report["overall_status"] == "healthy"
        assert report["healthy_components"] == 1
        assert report["total_components"] == 1
        assert "c1" in report["components"]

    def test_get_component_status(self):
        self.diag.register_check(MockHealthCheck("c1", HealthStatus.HEALTHY))
        self.diag.run_all_checks()

        status = self.diag.get_component_status("c1")
        assert status is not None
        assert status.status == HealthStatus.HEALTHY

    def test_get_component_status_missing(self):
        status = self.diag.get_component_status("missing")
        assert status is None

    def test_check_component(self):
        check = MockHealthCheck("c1")
        self.diag.register_check(check)
        result = self.diag.check_component("c1")
        assert result is not None
        assert result.status == HealthStatus.HEALTHY

    def test_history(self):
        self.diag.register_check(MockHealthCheck("c1"))
        self.diag.run_all_checks()
        self.diag.run_all_checks()

        history = self.diag.get_history(2)
        assert len(history) == 2

    def test_start_stop(self):
        self.diag.start()
        assert self.diag._running is True
        self.diag.stop()
        assert self.diag._running is False


class TestPredefinedChecks:
    """测试预定义健康检查"""

    def test_memory_check(self):
        check = MemoryHealthCheck(warning_threshold=0.99, critical_threshold=0.999)
        result = check.check()
        # 在测试环境中内存通常不会爆满
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert "usage" in result.metrics

    def test_cpu_check(self):
        check = CPUHealthCheck(warning_threshold=0.99, critical_threshold=0.999)
        result = check.check()
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert "usage" in result.metrics

    def test_disk_check(self):
        check = DiskHealthCheck(warning_threshold=0.99, critical_threshold=0.999)
        result = check.check()
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert "usage" in result.metrics

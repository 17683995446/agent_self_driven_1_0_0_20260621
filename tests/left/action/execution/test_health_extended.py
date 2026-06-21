"""
健康检查扩展测试

补充覆盖 SelfDiagnostics、healer、各组件健康检查边界路径
"""

import pytest
from unittest.mock import patch

from src.left.action.execution.health import (
    SelfDiagnostics, DiagnosticsBase, HealthCheckBase,
    HealthCheck, HealthStatus, ComponentHealth,
    MemoryHealthCheck, CPUHealthCheck, DiskHealthCheck,
)


class TestDiagnosticsBase:
    """测试诊断基类"""

    def test_diagnostics_base_abstract(self):
        with pytest.raises(TypeError):
            DiagnosticsBase()


class TestHealthCheckBase:
    """测试健康检查基类"""

    def test_health_check_base_abstract(self):
        with pytest.raises(TypeError):
            HealthCheckBase()


class TestHealthCheckExtended:
    """测试健康检查扩展路径"""

    def test_check_exception(self):
        class BadCheck(HealthCheck):
            def _do_check(self):
                raise ValueError("check error")
        check = BadCheck("bad")
        result = check.check()
        assert result.status == HealthStatus.FAILED
        assert "check error" in result.message


class TestSelfDiagnosticsExtended:
    """测试自诊断扩展路径"""

    def test_register_check(self):
        diag = SelfDiagnostics()
        check = HealthCheck("test")
        diag.register_check(check)
        assert "test" in diag._checks

    def test_register_healer(self):
        diag = SelfDiagnostics()
        def healer(h):
            return True
        diag.register_healer("test", healer)
        assert "test" in diag._healers

    def test_start_stop(self):
        diag = SelfDiagnostics(check_interval=0.1)
        diag.start()
        assert diag._running is True
        diag.stop()
        assert diag._running is False

    def test_run_all_checks_empty(self):
        diag = SelfDiagnostics()
        results = diag.run_all_checks()
        assert results == {}

    def test_run_all_checks_with_healer(self):
        diag = SelfDiagnostics()
        healed = []
        def healer(h):
            healed.append(h.name)
            return True
        diag.register_healer("test", healer)
        class FailCheck(HealthCheck):
            def _do_check(self):
                return HealthStatus.FAILED, "fail", {}
        diag.register_check(FailCheck("test"))
        diag.run_all_checks()
        assert "test" in healed

    def test_run_all_checks_healer_exception(self):
        diag = SelfDiagnostics()
        def bad_healer(h):
            raise ValueError("healer error")
        diag.register_healer("test", bad_healer)
        class FailCheck(HealthCheck):
            def _do_check(self):
                return HealthStatus.FAILED, "fail", {}
        diag.register_check(FailCheck("test"))
        # 不应抛出异常
        diag.run_all_checks()

    def test_check_component_missing(self):
        diag = SelfDiagnostics()
        assert diag.check_component("none") is None

    def test_get_overall_status_empty(self):
        diag = SelfDiagnostics()
        assert diag.get_overall_status() == HealthStatus.HEALTHY

    def test_get_overall_status_failed(self):
        diag = SelfDiagnostics()
        diag._results = {"a": ComponentHealth("a", HealthStatus.FAILED)}
        assert diag.get_overall_status() == HealthStatus.FAILED

    def test_get_overall_status_unhealthy(self):
        diag = SelfDiagnostics()
        diag._results = {"a": ComponentHealth("a", HealthStatus.UNHEALTHY)}
        assert diag.get_overall_status() == HealthStatus.UNHEALTHY

    def test_get_overall_status_degraded(self):
        diag = SelfDiagnostics()
        diag._results = {"a": ComponentHealth("a", HealthStatus.DEGRADED)}
        assert diag.get_overall_status() == HealthStatus.DEGRADED

    def test_get_report(self):
        diag = SelfDiagnostics()
        diag._results = {"a": ComponentHealth("a", HealthStatus.HEALTHY)}
        report = diag.get_report()
        assert "overall_status" in report
        assert report["healthy_components"] == 1

    def test_get_component_status(self):
        diag = SelfDiagnostics()
        diag._results = {"a": ComponentHealth("a", HealthStatus.HEALTHY)}
        assert diag.get_component_status("a") is not None
        assert diag.get_component_status("b") is None

    def test_get_history(self):
        diag = SelfDiagnostics()
        diag._history = [{"t": 1}, {"t": 2}]
        assert len(diag.get_history(1)) == 1


class TestMemoryHealthCheck:
    """测试内存健康检查"""

    def test_check_healthy(self):
        check = MemoryHealthCheck()
        with patch("psutil.virtual_memory", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.HEALTHY

    def test_check_warning(self):
        check = MemoryHealthCheck(warning_threshold=0.3)
        with patch("psutil.virtual_memory", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.DEGRADED

    def test_check_critical(self):
        check = MemoryHealthCheck(critical_threshold=0.3)
        with patch("psutil.virtual_memory", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.FAILED


class TestCPUHealthCheck:
    """测试CPU健康检查"""

    def test_check_healthy(self):
        check = CPUHealthCheck()
        with patch("psutil.cpu_percent", return_value=50.0):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.HEALTHY

    def test_check_warning(self):
        check = CPUHealthCheck(warning_threshold=0.3)
        with patch("psutil.cpu_percent", return_value=50.0):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.DEGRADED

    def test_check_critical(self):
        check = CPUHealthCheck(critical_threshold=0.3)
        with patch("psutil.cpu_percent", return_value=50.0):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.FAILED


class TestDiskHealthCheck:
    """测试磁盘健康检查"""

    def test_check_healthy(self):
        check = DiskHealthCheck()
        with patch("psutil.disk_usage", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.HEALTHY

    def test_check_warning(self):
        check = DiskHealthCheck(warning_threshold=0.3)
        with patch("psutil.disk_usage", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.DEGRADED

    def test_check_critical(self):
        check = DiskHealthCheck(critical_threshold=0.3)
        with patch("psutil.disk_usage", return_value=type("obj", (), {"percent": 50.0})()):
            status, msg, metrics = check._do_check()
            assert status == HealthStatus.FAILED

"""
混沌工程与容错测试

验证故障注入、实验管理、弹性恢复测试
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.support.infra.config.chaos_engineering import (
    ChaosEngineer, FaultInjectorBase, ResilienceTestRunner,
    FaultType, ChaosExperiment, FaultResult,
)


class TestFaultInjectorBase:
    """测试抽象基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            FaultInjectorBase()


class TestChaosEngineerInit:
    """测试初始化"""

    def test_disabled_by_default(self):
        chaos = ChaosEngineer()
        assert chaos.enabled is False

    def test_enabled(self):
        chaos = ChaosEngineer(enabled=True)
        assert chaos.enabled is True


class TestEnableDisable:
    """测试启用禁用"""

    def test_enable_disable(self):
        chaos = ChaosEngineer()
        chaos.enable()
        assert chaos.enabled is True
        chaos.disable()
        assert chaos.enabled is False


class TestAddExperiment:
    """测试添加实验"""

    def test_add_normal(self):
        chaos = ChaosEngineer()
        exp = ChaosExperiment(name="test", fault_type=FaultType.LATENCY, target="module_a")
        chaos.add_experiment(exp)
        assert len(chaos.list_experiments()) == 1

    def test_add_empty_name(self):
        chaos = ChaosEngineer()
        exp = ChaosExperiment(name="", fault_type=FaultType.LATENCY, target="module_a")
        with pytest.raises(ValueError):
            chaos.add_experiment(exp)

    def test_add_invalid_probability_low(self):
        chaos = ChaosEngineer()
        exp = ChaosExperiment(name="test", fault_type=FaultType.LATENCY, target="a", probability=-0.1)
        with pytest.raises(ValueError):
            chaos.add_experiment(exp)

    def test_add_invalid_probability_high(self):
        chaos = ChaosEngineer()
        exp = ChaosExperiment(name="test", fault_type=FaultType.LATENCY, target="a", probability=1.1)
        with pytest.raises(ValueError):
            chaos.add_experiment(exp)


class TestRemoveExperiment:
    """测试移除实验"""

    def test_remove_existing(self):
        chaos = ChaosEngineer()
        exp = ChaosExperiment(name="test", fault_type=FaultType.LATENCY, target="a")
        chaos.add_experiment(exp)
        assert chaos.remove_experiment("test") is True
        assert len(chaos.list_experiments()) == 0

    def test_remove_nonexistent(self):
        chaos = ChaosEngineer()
        assert chaos.remove_experiment("none") is False


class TestShouldInject:
    """测试注入判断"""

    def test_disabled_no_inject(self):
        chaos = ChaosEngineer(enabled=False)
        assert chaos.should_inject("target", 1.0) is False

    def test_enabled_always_inject(self):
        chaos = ChaosEngineer(enabled=True)
        assert chaos.should_inject("target", 1.0) is True

    def test_enabled_never_inject(self):
        chaos = ChaosEngineer(enabled=True)
        assert chaos.should_inject("target", 0.0) is False

    def test_active_fault_no_inject(self):
        chaos = ChaosEngineer(enabled=True)
        chaos._active_faults["target"] = True
        assert chaos.should_inject("target", 1.0) is False


class TestInjectLatency:
    """测试延迟注入"""

    def test_inject_when_enabled(self):
        chaos = ChaosEngineer(enabled=True)
        result = chaos.inject_latency("module", 10.0)
        assert result.injected is True
        assert result.fault_type == "LATENCY"
        assert result.duration_ms >= 10.0

    def test_no_inject_when_disabled(self):
        chaos = ChaosEngineer(enabled=False)
        result = chaos.inject_latency("module", 10.0)
        assert result.injected is False


class TestInjectException:
    """测试异常注入"""

    def test_inject_when_enabled(self):
        chaos = ChaosEngineer(enabled=True)
        result = chaos.inject_exception("module", ValueError("test"))
        assert result.injected is True
        assert result.error == "test"

    def test_no_inject_when_disabled(self):
        chaos = ChaosEngineer(enabled=False)
        result = chaos.inject_exception("module", ValueError("test"))
        assert result.injected is False


class TestWrapWithFault:
    """测试函数包装"""

    def test_wrap_latency(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.LATENCY, probability=1.0)
        result = wrapped()
        assert result == 42

    def test_wrap_exception(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.EXCEPTION, probability=1.0)
        with pytest.raises(RuntimeError):
            wrapped()

    def test_wrap_no_inject(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.EXCEPTION, probability=0.0)
        assert wrapped() == 42


class TestRunExperiment:
    """测试运行实验"""

    def test_run_latency_experiment(self):
        chaos = ChaosEngineer(enabled=True)
        exp = ChaosExperiment(
            name="latency_test",
            fault_type=FaultType.LATENCY,
            target="module",
            probability=1.0,
            duration=0.2,
        )
        results = chaos.run_experiment(exp)
        assert len(results) >= 1
        assert all(r.fault_type == "LATENCY" for r in results)

    def test_run_exception_experiment(self):
        chaos = ChaosEngineer(enabled=True)
        exp = ChaosExperiment(
            name="exception_test",
            fault_type=FaultType.EXCEPTION,
            target="module",
            probability=1.0,
            duration=0.2,
        )
        results = chaos.run_experiment(exp)
        assert len(results) >= 1
        assert all(r.fault_type == "EXCEPTION" for r in results)

    def test_run_when_disabled(self):
        chaos = ChaosEngineer(enabled=False)
        exp = ChaosExperiment(
            name="test",
            fault_type=FaultType.LATENCY,
            target="module",
            duration=0.2,
        )
        results = chaos.run_experiment(exp)
        assert len(results) == 0


class TestGetResults:
    """测试结果获取"""

    def test_get_results(self):
        chaos = ChaosEngineer(enabled=True)
        chaos.inject_latency("a", 1.0)
        chaos.inject_exception("b", ValueError("err"))
        results = chaos.get_results()
        assert len(results) == 2


class TestGetStats:
    """测试统计信息"""

    def test_stats(self):
        chaos = ChaosEngineer(enabled=True)
        chaos.inject_latency("a", 1.0)
        stats = chaos.get_stats()
        assert stats["enabled"] is True
        assert stats["total_injections"] == 1
        assert stats["successful_injections"] == 1
        assert stats["by_type"]["LATENCY"] == 1

    def test_stats_empty(self):
        chaos = ChaosEngineer()
        stats = chaos.get_stats()
        assert stats["total_injections"] == 0


class TestReset:
    """测试重置"""

    def test_reset(self):
        chaos = ChaosEngineer(enabled=True)
        chaos.inject_latency("a", 1.0)
        chaos.reset()
        assert chaos.get_results() == []
        assert chaos._active_faults == {}


class TestResilienceTestRunner:
    """测试弹性测试运行器"""

    def test_recovery_success(self):
        chaos = ChaosEngineer()
        runner = ResilienceTestRunner(chaos)
        def fn():
            return "stable_value"

        result = runner.test_recovery("target", fn, FaultType.LATENCY, duration=0.1)
        assert result["recovered"] is True
        assert result["fault_injections"] >= 0

    def test_recovery_with_exception(self):
        chaos = ChaosEngineer()
        runner = ResilienceTestRunner(chaos)
        def fn():
            return "stable"

        result = runner.test_recovery("target", fn, FaultType.EXCEPTION, duration=0.1)
        assert result["recovered"] is True

    def test_get_test_results(self):
        chaos = ChaosEngineer()
        runner = ResilienceTestRunner(chaos)
        runner.test_recovery("a", lambda: 1, FaultType.LATENCY, duration=0.1)
        results = runner.get_test_results()
        assert len(results) == 1


class TestResourceFaults:
    """测试资源故障模拟"""

    def test_cpu_spike(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.CPU_SPIKE, probability=1.0, intensity=0.1)
        result = wrapped()
        assert result == 42
        stats = chaos.get_stats()
        assert stats["by_type"]["CPU_SPIKE"] == 1

    def test_memory_pressure(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.MEMORY_PRESSURE, probability=1.0, intensity=0.1)
        result = wrapped()
        assert result == 42
        stats = chaos.get_stats()
        assert stats["by_type"]["MEMORY_PRESSURE"] == 1

    def test_network_partition(self):
        chaos = ChaosEngineer(enabled=True)
        fn = lambda: 42
        wrapped = chaos.wrap_with_fault("target", fn, FaultType.NETWORK_PARTITION, probability=1.0)
        result = wrapped()
        assert result == 42
        stats = chaos.get_stats()
        assert stats["by_type"]["NETWORK_PARTITION"] == 1

    def test_cpu_experiment_run(self):
        chaos = ChaosEngineer(enabled=True)
        exp = ChaosExperiment(
            name="cpu_test",
            fault_type=FaultType.CPU_SPIKE,
            target="module",
            probability=1.0,
            intensity=0.1,
            duration=0.1,
        )
        results = chaos.run_experiment(exp)
        assert len(results) >= 1
        assert all(r.fault_type == "CPU_SPIKE" for r in results)

    def test_memory_experiment_run(self):
        chaos = ChaosEngineer(enabled=True)
        exp = ChaosExperiment(
            name="mem_test",
            fault_type=FaultType.MEMORY_PRESSURE,
            target="module",
            probability=1.0,
            intensity=0.1,
            duration=0.1,
        )
        results = chaos.run_experiment(exp)
        assert len(results) >= 1
        assert all(r.fault_type == "MEMORY_PRESSURE" for r in results)

    def test_network_experiment_run(self):
        chaos = ChaosEngineer(enabled=True)
        exp = ChaosExperiment(
            name="net_test",
            fault_type=FaultType.NETWORK_PARTITION,
            target="module",
            probability=1.0,
            duration=0.1,
        )
        results = chaos.run_experiment(exp)
        assert len(results) >= 1
        assert all(r.fault_type == "NETWORK_PARTITION" for r in results)

    def test_boundary_zero_intensity_cpu(self):
        chaos = ChaosEngineer(enabled=True)
        result = chaos._simulate_cpu_spike("t", 0.0)
        assert result.injected is True
        assert result.duration_ms < 50.0

    def test_boundary_zero_intensity_memory(self):
        chaos = ChaosEngineer(enabled=True)
        result = chaos._simulate_memory_pressure("t", 0.0)
        assert result.injected is True

    def test_invalid_negative_intensity_memory(self):
        chaos = ChaosEngineer(enabled=True)
        result = chaos._simulate_memory_pressure("t", -1.0)
        assert result.injected is True


class TestFaultResult:
    """测试故障结果"""

    def test_defaults(self):
        result = FaultResult(fault_type="LATENCY", target="a", injected=True)
        assert result.error == ""
        assert result.duration_ms == 0.0

"""
安全护栏扩展测试

补充覆盖 check_resource_usage、update_usage、ExplorationStopLoss、CircuitBreaker 等路径
"""

import time

import pytest

from src.platform.lifecycle.memory.guardrail import (
    SafetyGuardrail, GuardrailBase, ExplorationStopLoss,
    CircuitBreaker, CircuitState,
)
from src.platform.support.models.base.state import ResourceUsage


class TestCircuitBreaker:
    """测试熔断器"""

    def test_initial_state(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_open_after_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_close_after_successes(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopen_on_failure(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_record_success_in_closed(self):
        cb = CircuitBreaker("test")
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0


class TestGuardrailCircuitBreaker:
    """测试安全护栏熔断器集成"""

    def test_default_breakers_exist(self):
        guardrail = SafetyGuardrail()
        assert "exploration" in guardrail.circuit_breakers
        assert "task_execution" in guardrail.circuit_breakers
        assert "prediction" in guardrail.circuit_breakers

    def test_get_circuit_breaker_new(self):
        guardrail = SafetyGuardrail()
        cb = guardrail.get_circuit_breaker("custom")
        assert cb.name == "custom"

    def test_record_circuit_success(self):
        guardrail = SafetyGuardrail()
        guardrail.record_circuit_result("exploration", True)
        assert guardrail.circuit_breakers["exploration"].failure_count == 0

    def test_record_circuit_failure(self):
        guardrail = SafetyGuardrail()
        for _ in range(5):
            guardrail.record_circuit_result("exploration", False)
        assert guardrail.circuit_breakers["exploration"].state == CircuitState.OPEN

    def test_check_circuit_closed(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_circuit("exploration")
        assert result.allowed is True

    def test_check_circuit_open(self):
        guardrail = SafetyGuardrail()
        for _ in range(5):
            guardrail.record_circuit_result("exploration", False)
        result = guardrail.check_circuit("exploration")
        assert result.allowed is False
        assert "open" in result.reason

    def test_get_circuit_stats(self):
        guardrail = SafetyGuardrail()
        stats = guardrail.get_circuit_stats()
        assert "exploration" in stats
        assert "state" in stats["exploration"]


class TestGuardrailResourceUsage:
    """测试资源使用检查"""

    def test_all_within_limits(self):
        guardrail = SafetyGuardrail(max_cpu=0.5, max_memory=0.5, max_disk=0.9)
        usage = ResourceUsage(cpu=0.1, memory=0.1, disk=0.1)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is True

    def test_cpu_exceeded(self):
        guardrail = SafetyGuardrail(max_cpu=0.1)
        usage = ResourceUsage(cpu=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is False

    def test_memory_exceeded(self):
        guardrail = SafetyGuardrail(max_memory=0.1)
        usage = ResourceUsage(memory=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is False

    def test_disk_exceeded(self):
        guardrail = SafetyGuardrail(max_disk=0.1)
        usage = ResourceUsage(disk=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is False

    def test_multiple_violations(self):
        guardrail = SafetyGuardrail(max_cpu=0.1, max_memory=0.1)
        usage = ResourceUsage(cpu=0.5, memory=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is False
        assert "CPU" in result.reason


class TestGuardrailUpdateUsage:
    """测试更新资源使用记录"""

    def test_update_cpu(self):
        guardrail = SafetyGuardrail()
        guardrail.update_usage(cpu=0.5)
        assert guardrail.current_usage.cpu == 0.5

    def test_update_memory(self):
        guardrail = SafetyGuardrail()
        guardrail.update_usage(memory=0.3)
        assert guardrail.current_usage.memory == 0.3

    def test_update_disk(self):
        guardrail = SafetyGuardrail()
        guardrail.update_usage(disk=0.7)
        assert guardrail.current_usage.disk == 0.7

    def test_update_none(self):
        guardrail = SafetyGuardrail()
        guardrail.update_usage()
        assert guardrail.current_usage.cpu == 0.0


class TestEnforceResourceLimits:
    """测试强制执行"""

    def test_no_violation(self):
        guardrail = SafetyGuardrail()
        usage = ResourceUsage(cpu=0.1, memory=0.1)
        action = guardrail.enforce_resource_limits(usage)
        assert action.action == "NONE"

    def test_cpu_enforce(self):
        guardrail = SafetyGuardrail(max_cpu=0.1)
        usage = ResourceUsage(cpu=0.5)
        action = guardrail.enforce_resource_limits(usage)
        assert action.action == "THROTTLE"

    def test_memory_enforce(self):
        guardrail = SafetyGuardrail(max_memory=0.1)
        usage = ResourceUsage(memory=0.5)
        action = guardrail.enforce_resource_limits(usage)
        assert action.action == "TERMINATE"

    def test_disk_enforce(self):
        guardrail = SafetyGuardrail(max_disk=0.1)
        usage = ResourceUsage(disk=0.5)
        action = guardrail.enforce_resource_limits(usage)
        assert action.action == "BLOCK"


class TestExplorationStopLoss:
    """测试探索止损"""

    def test_record_success(self):
        esl = ExplorationStopLoss()
        esl.record_result("type_a", True)
        assert esl.is_allowed("type_a") is True

    def test_record_failure_under_limit(self):
        esl = ExplorationStopLoss()
        for _ in range(3):
            esl.record_result("type_a", False)
        assert esl.is_allowed("type_a") is True

    def test_record_failure_over_limit(self):
        esl = ExplorationStopLoss()
        for _ in range(5):
            esl.record_result("type_a", False)
        assert esl.is_allowed("type_a") is False

    def test_unfreeze_after_success(self):
        esl = ExplorationStopLoss()
        for _ in range(5):
            esl.record_result("type_a", False)
        assert esl.is_allowed("type_a") is False
        esl.record_result("type_a", True)
        assert esl.is_allowed("type_a") is True

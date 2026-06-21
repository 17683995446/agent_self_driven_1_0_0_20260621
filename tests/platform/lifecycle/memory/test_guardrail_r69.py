"""
安全护栏R69完善测试

验证审计日志、速率限制、复合策略
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import time

import pytest

from src.platform.lifecycle.memory.guardrail import (
    SafetyGuardrail, GuardrailBase, GuardrailAuditLog,
    GuardrailAuditEntry, RateLimiter, CompositeGuardrail,
    GuardrailResult,
)
from src.platform.support.models.base.state import ResourceUsage


class TestGuardrailAuditLog:
    """测试护栏审计日志"""

    def test_record_single_entry(self):
        log = GuardrailAuditLog()
        result = GuardrailResult(allowed=True, reason="ok", severity="OK")
        log.record("read_file", result)
        assert len(log.entries) == 1
        assert log.entries[0].operation == "read_file"

    def test_record_blocked_entry(self):
        log = GuardrailAuditLog()
        result = GuardrailResult(allowed=False, reason="forbidden", severity="CRITICAL")
        log.record("rm -rf /", result)
        assert log.entries[0].allowed is False
        assert log.entries[0].severity == "CRITICAL"

    def test_max_entries_trim(self):
        log = GuardrailAuditLog(max_entries=3)
        for i in range(5):
            log.record(f"op_{i}", GuardrailResult())
        assert len(log.entries) == 3
        assert log.entries[0].operation == "op_2"

    def test_query_allowed_only(self):
        log = GuardrailAuditLog()
        log.record("safe", GuardrailResult(allowed=True))
        log.record("unsafe", GuardrailResult(allowed=False))
        results = log.query(allowed_only=True)
        assert len(results) == 1
        assert results[0].operation == "safe"

    def test_query_by_severity(self):
        log = GuardrailAuditLog()
        log.record("a", GuardrailResult(severity="HIGH"))
        log.record("b", GuardrailResult(severity="LOW"))
        results = log.query(severity="HIGH")
        assert len(results) == 1
        assert results[0].operation == "a"

    def test_get_stats(self):
        log = GuardrailAuditLog()
        log.record("a", GuardrailResult(allowed=True))
        log.record("b", GuardrailResult(allowed=False))
        stats = log.get_stats()
        assert stats["total"] == 2
        assert stats["blocked"] == 1

    def test_empty_log_stats(self):
        log = GuardrailAuditLog()
        stats = log.get_stats()
        assert stats["total"] == 0
        assert stats["blocked"] == 0


class TestRateLimiter:
    """测试速率限制器"""

    def test_allow_within_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=10.0)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True

    def test_block_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=10.0)
        limiter.allow()
        limiter.allow()
        assert limiter.allow() is False

    def test_window_reset(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.05)
        limiter.allow()
        assert limiter.allow() is False
        time.sleep(0.06)
        assert limiter.allow() is True

    def test_get_current_rate(self):
        limiter = RateLimiter(max_requests=5, window_seconds=10.0)
        limiter.allow()
        limiter.allow()
        assert limiter.get_current_rate() == 2

    def test_boundary_exact_limit(self):
        limiter = RateLimiter(max_requests=0, window_seconds=10.0)
        assert limiter.allow() is False

    def test_rate_limiter_empty_window(self):
        limiter = RateLimiter(max_requests=5, window_seconds=10.0)
        assert limiter.get_current_rate() == 0


class TestCompositeGuardrail:
    """测试复合护栏策略"""

    def test_all_pass(self):
        g1 = SafetyGuardrail()
        g2 = SafetyGuardrail()
        composite = CompositeGuardrail([g1, g2])
        result = composite.check_operation("safe_op")
        assert result.allowed is True

    def test_first_blocks(self):
        g1 = SafetyGuardrail()
        g2 = SafetyGuardrail()
        composite = CompositeGuardrail([g1, g2])
        result = composite.check_operation("rm -rf /")
        assert result.allowed is False

    def test_empty_composite_passes(self):
        composite = CompositeGuardrail([])
        result = composite.check_operation("anything")
        assert result.allowed is True

    def test_composite_is_abstract_subclass(self):
        assert issubclass(CompositeGuardrail, GuardrailBase)

    def test_composite_multiple_guardrails(self):
        g1 = SafetyGuardrail()
        g2 = SafetyGuardrail()
        g3 = SafetyGuardrail()
        composite = CompositeGuardrail([g1, g2, g3])
        result = composite.check_operation("read_file")
        assert result.allowed is True

    def test_composite_blocks_on_second(self):
        class BlockingGuardrail(GuardrailBase):
            def check_operation(self, operation: str) -> GuardrailResult:
                return GuardrailResult(allowed=False, reason="always block")

        composite = CompositeGuardrail([SafetyGuardrail(), BlockingGuardrail()])
        result = composite.check_operation("safe_op")
        assert result.allowed is False
        assert result.reason == "always block"


class TestSafetyGuardrailR69:
    """测试安全护栏R69补充用例"""

    def test_forbidden_chmod(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_operation("chmod -R 777 /")
        assert result.allowed is False

    def test_forbidden_mkfs(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_operation("mkfs.ext4 /dev/sda")
        assert result.allowed is False

    def test_forbidden_dd(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_operation("dd if=/dev/zero of=/dev/sda")
        assert result.allowed is False

    def test_boundary_cpu_exact_limit(self):
        guardrail = SafetyGuardrail(max_cpu=0.5)
        usage = ResourceUsage(cpu=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is True

    def test_boundary_memory_exact_limit(self):
        guardrail = SafetyGuardrail(max_memory=0.5)
        usage = ResourceUsage(memory=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is True

    def test_boundary_disk_exact_limit(self):
        guardrail = SafetyGuardrail(max_disk=0.5)
        usage = ResourceUsage(disk=0.5)
        result = guardrail.check_resource_usage(usage)
        assert result.allowed is True

    def test_violation_count_increment(self):
        guardrail = SafetyGuardrail(max_cpu=0.1)
        usage = ResourceUsage(cpu=0.5)
        assert guardrail.violation_count == 0
        guardrail.check_resource_usage(usage)
        assert guardrail.violation_count == 1
        guardrail.check_resource_usage(usage)
        assert guardrail.violation_count == 2

    def test_enforce_cpu_returns_target(self):
        guardrail = SafetyGuardrail(max_cpu=0.2)
        usage = ResourceUsage(cpu=0.5)
        action = guardrail.enforce_resource_limits(usage)
        assert action.action == "THROTTLE"
        assert action.target_cpu == 0.2

    def test_circuit_stats_structure(self):
        guardrail = SafetyGuardrail()
        stats = guardrail.get_circuit_stats()
        assert "exploration" in stats
        assert "state" in stats["exploration"]
        assert "failure_count" in stats["exploration"]

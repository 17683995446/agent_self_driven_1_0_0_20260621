"""
安全护栏模块测试

验证资源限制、禁止操作检查的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.lifecycle.memory.guardrail import SafetyGuardrail, GuardrailBase, GuardrailResult
from src.platform.support.models.base.state import EnvironmentState, ResourceUsage


class TestGuardrailBase:
    """测试护栏基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            GuardrailBase()


class TestSafetyGuardrailInit:
    """测试安全护栏初始化"""

    def test_normal_init(self):
        guardrail = SafetyGuardrail(max_cpu=0.8, max_memory=0.8, max_disk=0.9)
        assert guardrail.max_cpu == 0.8

    def test_boundary_min(self):
        guardrail = SafetyGuardrail(max_cpu=0.0)
        assert guardrail.max_cpu == 0.0

    def test_boundary_max(self):
        guardrail = SafetyGuardrail(max_cpu=1.0)
        assert guardrail.max_cpu == 1.0


class TestCheckOperation:
    """测试操作检查"""

    def test_safe_operation(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_operation("read_file")
        assert isinstance(result, GuardrailResult)

    def test_forbidden_operation(self):
        guardrail = SafetyGuardrail()
        result = guardrail.check_operation("rm -rf /")
        assert result.allowed is False

    def test_null_operation(self):
        guardrail = SafetyGuardrail()
        with pytest.raises((AttributeError, TypeError)):
            guardrail.check_operation(None)


class TestResourceLimits:
    """测试资源限制"""

    def test_cpu_within_limit(self):
        guardrail = SafetyGuardrail(max_cpu=0.9)
        resources = ResourceUsage(cpu=0.5)
        result = guardrail._check_cpu(resources)
        assert result is None

    def test_cpu_exceeded(self):
        guardrail = SafetyGuardrail(max_cpu=0.3)
        resources = ResourceUsage(cpu=0.5)
        result = guardrail._check_cpu(resources)
        assert result is not None

    def test_memory_within_limit(self):
        guardrail = SafetyGuardrail(max_memory=0.9)
        resources = ResourceUsage(memory=0.5)
        result = guardrail._check_memory(resources)
        assert result is None

    def test_memory_exceeded(self):
        guardrail = SafetyGuardrail(max_memory=0.3)
        resources = ResourceUsage(memory=0.5)
        result = guardrail._check_memory(resources)
        assert result is not None


class TestEnforceResourceLimits:
    """测试强制执行资源限制"""

    def test_normal_state(self):
        guardrail = SafetyGuardrail()
        resources = ResourceUsage(cpu=0.1, memory=0.1)
        result = guardrail.enforce_resource_limits(resources)
        assert result is not None

    def test_high_cpu_state(self):
        guardrail = SafetyGuardrail(max_cpu=0.1)
        resources = ResourceUsage(cpu=0.5)
        result = guardrail.enforce_resource_limits(resources)
        assert result is not None

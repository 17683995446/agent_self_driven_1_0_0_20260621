"""
预测误差分解测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.error_decomposition import (
    PredictionErrorDecomposer, ErrorDecomposition
)
from src.platform.support.models.base.state import EnvironmentState, SystemState


class TestErrorDecompositionNormal:
    """正常值测试"""

    def test_decompose_identical(self):
        decomposer = PredictionErrorDecomposer()
        state = EnvironmentState(system=SystemState(cpu_overall=0.5, memory_usage=0.3))
        result = decomposer.decompose(state, state)
        assert result.total_error == 0.0
        assert result.noise_error == 0.0
        assert result.component_errors["cpu"] == 0.0

    def test_decompose_different(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState(system=SystemState(cpu_overall=0.5, memory_usage=0.3))
        actual = EnvironmentState(system=SystemState(cpu_overall=0.7, memory_usage=0.4))
        result = decomposer.decompose(pred, actual)
        assert result.total_error > 0.0
        assert result.component_errors["cpu"] == pytest.approx(0.2, abs=1e-6)

    def test_add_to_history(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState(system=SystemState(cpu_overall=0.5))
        actual = EnvironmentState(system=SystemState(cpu_overall=0.6))
        decomposer.add(pred, actual)
        assert len(decomposer.history) == 1

    def test_bias_with_history(self):
        decomposer = PredictionErrorDecomposer()
        for i in range(3):
            pred = EnvironmentState(system=SystemState(cpu_overall=0.5))
            actual = EnvironmentState(system=SystemState(cpu_overall=0.6))
            decomposer.add(pred, actual)
        result = decomposer.decompose(pred, actual)
        assert result.bias_error > 0.0


class TestErrorDecompositionBoundary:
    """边界极值测试"""

    def test_zero_state(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState()
        actual = EnvironmentState()
        result = decomposer.decompose(pred, actual)
        assert result.total_error == 0.0

    def test_max_difference(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState(system=SystemState(cpu_overall=0.0))
        actual = EnvironmentState(system=SystemState(cpu_overall=1.0))
        result = decomposer.decompose(pred, actual)
        assert result.total_error > 0.0
        assert result.component_errors["cpu"] == 1.0


class TestErrorDecompositionEmpty:
    """空入参测试"""

    def test_empty_history(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState(system=SystemState(cpu_overall=0.5))
        actual = EnvironmentState(system=SystemState(cpu_overall=0.6))
        result = decomposer.decompose(pred, actual)
        assert result.bias_error == 0.0
        assert result.variance_error == 0.0

    def test_clear_history(self):
        decomposer = PredictionErrorDecomposer()
        decomposer.add(EnvironmentState(), EnvironmentState())
        decomposer.clear()
        assert len(decomposer.history) == 0


class TestErrorDecompositionInvalid:
    """非法格式测试"""

    def test_noise_non_negative(self):
        decomposer = PredictionErrorDecomposer()
        pred = EnvironmentState(system=SystemState(cpu_overall=0.5))
        actual = EnvironmentState(system=SystemState(cpu_overall=0.6))
        result = decomposer.decompose(pred, actual)
        assert result.noise_error >= 0.0

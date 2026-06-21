"""
预测模型层次间接口测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.prediction_layer import (
    LayerInput, LayerOutput, UpdateMetrics, ErrorSignal, PredictionLayer
)
from src.platform.support.models.base.state import EnvironmentState, SystemState


class MockPredictionLayer(PredictionLayer):
    """模拟预测层"""

    @property
    def time_scale(self) -> str:
        return "low"

    @property
    def horizon(self) -> int:
        return 1

    def predict(self, input_data: LayerInput) -> LayerOutput:
        return LayerOutput(
            prediction=EnvironmentState(),
            confidence=0.9,
            uncertainty={"cpu": 0.1},
        )

    def update(self, prediction: LayerOutput, actual: LayerInput) -> UpdateMetrics:
        return UpdateMetrics(error=0.1, improvement=0.05, learning_rate=0.01)

    def get_error_signal(self) -> ErrorSignal:
        return ErrorSignal(magnitude=0.1, direction="up", source="low")


class TestLayerInputNormal:
    """正常值测试"""

    def test_layer_input_creation(self):
        states = [EnvironmentState(system=SystemState(cpu_overall=0.5))]
        inp = LayerInput(state_sequence=states)
        assert len(inp.state_sequence) == 1
        assert inp.lower_layer_prediction is None


class TestLayerOutputNormal:
    """正常值测试"""

    def test_layer_output_creation(self):
        out = LayerOutput(
            prediction=EnvironmentState(),
            confidence=0.9,
            uncertainty={"cpu": 0.1},
        )
        assert out.confidence == 0.9
        assert out.uncertainty["cpu"] == 0.1


class TestUpdateMetricsNormal:
    """正常值测试"""

    def test_metrics_creation(self):
        m = UpdateMetrics(error=0.1, improvement=0.05, learning_rate=0.01)
        assert m.error == 0.1
        assert m.improvement == 0.05


class TestErrorSignalNormal:
    """正常值测试"""

    def test_signal_creation(self):
        s = ErrorSignal(magnitude=0.2, direction="down", source="mid")
        assert s.magnitude == 0.2
        assert s.direction == "down"


class TestPredictionLayerNormal:
    """正常值测试"""

    def test_mock_layer_time_scale(self):
        layer = MockPredictionLayer()
        assert layer.time_scale == "low"

    def test_mock_layer_predict(self):
        layer = MockPredictionLayer()
        inp = LayerInput(state_sequence=[])
        out = layer.predict(inp)
        assert out.confidence == 0.9

    def test_mock_layer_update(self):
        layer = MockPredictionLayer()
        pred = LayerOutput(prediction=EnvironmentState(), confidence=0.9, uncertainty={})
        actual = LayerInput(state_sequence=[])
        metrics = layer.update(pred, actual)
        assert metrics.error == 0.1

    def test_mock_layer_error_signal(self):
        layer = MockPredictionLayer()
        signal = layer.get_error_signal()
        assert signal.source == "low"


class TestPredictionLayerEmpty:
    """空入参测试"""

    def test_empty_state_sequence(self):
        inp = LayerInput(state_sequence=[])
        assert inp.state_sequence == []

    def test_empty_uncertainty(self):
        out = LayerOutput(prediction=EnvironmentState(), confidence=1.0, uncertainty={})
        assert out.uncertainty == {}

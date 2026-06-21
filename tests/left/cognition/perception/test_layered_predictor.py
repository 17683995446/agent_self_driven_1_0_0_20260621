"""
多层预测模型测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.layered_predictor import (
    LowLevelLayerPredictor, MidLevelLayerPredictor, HighLevelLayerPredictor
)
from src.left.cognition.perception.prediction_layer import LayerInput, LayerOutput
from src.platform.support.models.base.state import EnvironmentState, SystemState


def make_states(cpu_values: list) -> list:
    """辅助函数：创建状态序列"""
    return [
        EnvironmentState(system=SystemState(cpu_overall=v, memory_usage=v))
        for v in cpu_values
    ]


class TestLowLevelPredictorNormal:
    """正常值测试"""

    def test_time_scale(self):
        pred = LowLevelLayerPredictor()
        assert pred.time_scale == "low"

    def test_predict_with_trend(self):
        pred = LowLevelLayerPredictor()
        states = make_states([0.3, 0.4])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert isinstance(out, LayerOutput)
        assert out.confidence == 0.7
        assert out.prediction.system.cpu_overall > 0.4

    def test_update(self):
        pred = LowLevelLayerPredictor()
        pred_out = LayerOutput(prediction=EnvironmentState(system=SystemState(cpu_overall=0.5)), confidence=0.7, uncertainty={})
        actual = LayerInput(state_sequence=[EnvironmentState(system=SystemState(cpu_overall=0.6))])
        metrics = pred.update(pred_out, actual)
        assert metrics.error == pytest.approx(0.1, abs=1e-6)

    def test_error_signal(self):
        pred = LowLevelLayerPredictor()
        signal = pred.get_error_signal()
        assert signal.source == "low"


class TestLowLevelPredictorEmpty:
    """空入参测试"""

    def test_predict_empty_sequence(self):
        pred = LowLevelLayerPredictor()
        inp = LayerInput(state_sequence=[])
        out = pred.predict(inp)
        assert out.confidence == 0.5

    def test_predict_single_state(self):
        pred = LowLevelLayerPredictor()
        states = make_states([0.5])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall == 0.5


class TestMidLevelPredictorNormal:
    """正常值测试"""

    def test_time_scale(self):
        pred = MidLevelLayerPredictor()
        assert pred.time_scale == "mid"

    def test_predict_average(self):
        pred = MidLevelLayerPredictor()
        states = make_states([0.2, 0.4, 0.6])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall == pytest.approx(0.4, abs=1e-6)

    def test_horizon(self):
        pred = MidLevelLayerPredictor()
        assert pred.horizon == 5


class TestHighLevelPredictorNormal:
    """正常值测试"""

    def test_time_scale(self):
        pred = HighLevelLayerPredictor()
        assert pred.time_scale == "high"

    def test_predict_long_term_avg(self):
        pred = HighLevelLayerPredictor()
        states = make_states([0.1] * 50 + [0.9] * 50)
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall == pytest.approx(0.5, abs=1e-6)

    def test_horizon(self):
        pred = HighLevelLayerPredictor()
        assert pred.horizon == 24


class TestLayeredPredictorBoundary:
    """边界极值测试"""

    def test_low_level_clamps_high(self):
        pred = LowLevelLayerPredictor()
        states = make_states([0.9, 1.0])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall <= 1.0

    def test_low_level_clamps_low(self):
        pred = LowLevelLayerPredictor()
        states = make_states([0.1, 0.0])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall >= 0.0

    def test_mid_level_window_larger_than_data(self):
        pred = MidLevelLayerPredictor(window_size=100)
        states = make_states([0.2, 0.4])
        inp = LayerInput(state_sequence=states)
        out = pred.predict(inp)
        assert out.prediction.system.cpu_overall == pytest.approx(0.3, abs=1e-6)

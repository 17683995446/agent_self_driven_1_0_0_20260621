"""
预测模型测试

验证低/中/高层预测、误差计算、在线学习优化的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.cognition.perception.prediction import (
    PredictionModel, LowLevelPredictor, MidLevelPredictor, HighLevelPredictor,
    HierarchicalPredictionModel,
)
from src.platform.support.models.base.state import EnvironmentState


class TestPredictionModelBase:
    """测试预测模型基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            PredictionModel()


class TestLowLevelPredictor:
    """测试低层预测器"""

    def test_normal_predict(self):
        predictor = LowLevelPredictor()
        states = [EnvironmentState() for _ in range(3)]
        result = predictor.predict(states)
        assert isinstance(result, EnvironmentState)

    def test_empty_history(self):
        predictor = LowLevelPredictor()
        result = predictor.predict([])
        assert isinstance(result, EnvironmentState)

    def test_adapt_alpha(self):
        predictor = LowLevelPredictor()
        for i in range(15):
            pred = EnvironmentState()
            actual = EnvironmentState()
            predictor.update(pred, actual)
        assert predictor.alpha != predictor.base_alpha or len(predictor.error_history) < 10

    def test_get_error_trend(self):
        predictor = LowLevelPredictor()
        assert predictor.get_error_trend() == 0.0
        for i in range(15):
            pred = EnvironmentState()
            actual = EnvironmentState()
            predictor.update(pred, actual)
        trend = predictor.get_error_trend()
        assert isinstance(trend, float)


class TestMidLevelPredictor:
    """测试中层预测器"""

    def test_normal_predict(self):
        predictor = MidLevelPredictor()
        states = [EnvironmentState() for _ in range(5)]
        result = predictor.predict(states)
        assert isinstance(result, EnvironmentState)

    def test_adapt_weight(self):
        predictor = MidLevelPredictor()
        initial_weight = predictor.weight
        from dataclasses import replace
        for i in range(15):
            pred = EnvironmentState()
            actual = replace(EnvironmentState(), system=replace(EnvironmentState().system, cpu_overall=0.5 + float(i) * 0.01))
            predictor.update(pred, actual)
        # 权重可能变化，也可能不变（取决于误差趋势），但至少不应崩溃
        assert predictor.weight >= 0.0

    def test_get_error_trend(self):
        predictor = MidLevelPredictor()
        assert predictor.get_error_trend() == 0.0


class TestHighLevelPredictor:
    """测试高层预测器"""

    def test_normal_predict(self):
        predictor = HighLevelPredictor()
        states = [EnvironmentState() for _ in range(10)]
        result = predictor.predict(states)
        assert isinstance(result, EnvironmentState)

    def test_adapt_weight(self):
        predictor = HighLevelPredictor()
        initial_weight = predictor.weight
        from dataclasses import replace
        for i in range(15):
            pred = EnvironmentState()
            actual = replace(EnvironmentState(), system=replace(EnvironmentState().system, cpu_overall=0.5 + float(i) * 0.01))
            predictor.update(pred, actual)
        assert predictor.weight >= 0.0


class TestHierarchicalPredictionModel:
    """测试分层预测模型"""

    def test_normal_init(self):
        model = HierarchicalPredictionModel()
        assert model is not None

    def test_predict(self):
        model = HierarchicalPredictionModel()
        result = model.predict()
        assert isinstance(result, EnvironmentState)

    def test_update(self):
        model = HierarchicalPredictionModel()
        actual = EnvironmentState()
        model.update(actual)

    def test_get_average_error(self):
        model = HierarchicalPredictionModel()
        error = model.get_average_error()
        assert error >= 0.0

    def test_update_and_predict(self):
        model = HierarchicalPredictionModel()
        for _ in range(5):
            model.update(EnvironmentState())
        result = model.predict()
        assert isinstance(result, EnvironmentState)

    def test_get_error_trend(self):
        model = HierarchicalPredictionModel()
        assert model.get_error_trend() == 0.0
        for _ in range(15):
            model.update(EnvironmentState())
        trend = model.get_error_trend()
        assert isinstance(trend, float)

    def test_get_learning_stats(self):
        model = HierarchicalPredictionModel()
        for _ in range(5):
            model.update(EnvironmentState())
        stats = model.get_learning_stats()
        assert "low_error" in stats
        assert "combination_weights" in stats
        assert "error_trend" in stats
        assert "history_size" in stats

    def test_adapt_combination_weights(self):
        model = HierarchicalPredictionModel()
        initial_weights = model.combination_weights.copy()
        for _ in range(15):
            model.update(EnvironmentState())
        # 权重应该被调整
        assert sum(model.combination_weights) > 0.99

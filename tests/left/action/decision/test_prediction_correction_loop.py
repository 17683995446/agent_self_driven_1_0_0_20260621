"""
预测-修正闭环控制器测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
from unittest.mock import MagicMock

from src.left.action.decision.prediction_correction_loop import (
    TaskCategory,
    PredictionError,
    ErrorTrend,
    ErrorPredictor,
    MovingAveragePredictor,
    LinearTrendPredictor,
    TrendDetector,
    PredictionCorrectionLoop,
)
from src.platform.support.models.base.state import EnvironmentState, DriveWeights


class TestPredictionError:
    """测试预测误差"""

    def test_normal_creation(self):
        err = PredictionError(
            timestamp=1.0, predicted=0.5, actual=0.6,
            error=0.1, relative_error=0.1667,
        )
        assert err.error == 0.1

    def test_to_dict(self):
        err = PredictionError(
            timestamp=1.0, predicted=0.5, actual=0.6,
            error=0.1, relative_error=0.1667,
        )
        data = err.to_dict()
        assert data["predicted"] == 0.5
        assert data["actual"] == 0.6


class TestErrorTrend:
    """测试误差趋势"""

    def test_normal_creation(self):
        trend = ErrorTrend("rising", 0.1, 0.8)
        assert trend.direction == "rising"

    def test_to_dict(self):
        trend = ErrorTrend("falling", -0.05, 0.6)
        data = trend.to_dict()
        assert data["direction"] == "falling"
        assert data["confidence"] == 0.6


class TestMovingAveragePredictor:
    """测试移动平均预测器"""

    def test_predict_empty(self):
        predictor = MovingAveragePredictor(window=3)
        assert predictor.predict_next([]) == 0.0

    def test_predict_single(self):
        predictor = MovingAveragePredictor(window=3)
        assert predictor.predict_next([0.5]) == 0.5

    def test_predict_multiple(self):
        predictor = MovingAveragePredictor(window=3)
        result = predictor.predict_next([0.1, 0.2, 0.3])
        assert result == pytest.approx(0.2)

    def test_predict_window_limit(self):
        predictor = MovingAveragePredictor(window=2)
        result = predictor.predict_next([0.1, 0.2, 0.3, 0.4])
        assert result == pytest.approx(0.35)

    def test_predict_boundary_all_zeros(self):
        predictor = MovingAveragePredictor()
        assert predictor.predict_next([0.0, 0.0, 0.0]) == 0.0


class TestLinearTrendPredictor:
    """测试线性趋势预测器"""

    def test_predict_empty(self):
        predictor = LinearTrendPredictor()
        assert predictor.predict_next([]) == 0.0

    def test_predict_single(self):
        predictor = LinearTrendPredictor()
        assert predictor.predict_next([0.5]) == 0.5

    def test_predict_increasing(self):
        predictor = LinearTrendPredictor()
        result = predictor.predict_next([0.1, 0.2, 0.3, 0.4])
        assert result > 0.4

    def test_predict_decreasing(self):
        predictor = LinearTrendPredictor()
        result = predictor.predict_next([0.4, 0.3, 0.2, 0.1])
        assert result < 0.1

    def test_predict_constant(self):
        predictor = LinearTrendPredictor()
        result = predictor.predict_next([0.5, 0.5, 0.5, 0.5])
        assert result == pytest.approx(0.5)


class TestTrendDetector:
    """测试趋势检测器"""

    def setup_method(self):
        self.detector = TrendDetector()

    def test_insufficient_samples(self):
        trend = self.detector.detect([0.1, 0.2])
        assert trend.direction == "stable"
        assert trend.confidence == 0.0

    def test_rising_trend(self):
        trend = self.detector.detect([0.01, 0.02, 0.10, 0.20])
        assert trend.direction == "rising"

    def test_falling_trend(self):
        trend = self.detector.detect([0.20, 0.10, 0.02, 0.01])
        assert trend.direction == "falling"

    def test_stable_trend(self):
        trend = self.detector.detect([0.05, 0.05, 0.05, 0.05])
        assert trend.direction == "stable"

    def test_empty_history(self):
        trend = self.detector.detect([])
        assert trend.direction == "stable"

    def test_confidence_grows_with_history(self):
        short = self.detector.detect([0.01, 0.02, 0.10, 0.20])
        long = self.detector.detect([0.01] * 5 + [0.02, 0.10, 0.20])
        assert long.confidence >= short.confidence

    def test_zero_older_avg_rising(self):
        trend = self.detector.detect([0.0, 0.0, 0.1, 0.2])
        assert trend.direction == "rising"

    def test_zero_older_avg_stable(self):
        trend = self.detector.detect([0.0, 0.0, 0.0, 0.0])
        assert trend.direction == "stable"


class TestPredictionCorrectionLoop:
    """测试预测-修正闭环控制器"""

    def setup_method(self):
        self.loop = PredictionCorrectionLoop()

    def test_predict_empty(self):
        """测试无历史时预测"""
        state = EnvironmentState()
        result = self.loop.predict(state)
        assert result == 0.0

    def test_correct_single(self):
        """测试单次修正"""
        error = self.loop.correct(predicted=0.5, actual=0.6)
        assert error.error == pytest.approx(0.1)
        assert error.relative_error > 0

    def test_correct_zero_actual(self):
        """测试实际值为零的边界"""
        error = self.loop.correct(predicted=0.5, actual=0.0)
        assert error.relative_error > 0

    def test_correct_perfect_prediction(self):
        """测试完美预测"""
        error = self.loop.correct(predicted=0.5, actual=0.5)
        assert error.error == 0.0
        assert error.relative_error == 0.0

    def test_task_weights_no_history(self):
        """测试无历史时权重"""
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.SAFETY] > 0
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_task_weights_high_error(self):
        """测试高误差时安全优先"""
        self.loop.correct(predicted=0.0, actual=1.0)
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.SAFETY] >= 0.6

    def test_task_weights_low_error(self):
        """测试低误差时探索优先"""
        self.loop.correct(predicted=0.5, actual=0.51)
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.EXPLORATION] >= 0.3

    def test_task_weights_normal_error(self):
        """测试正常误差时平衡"""
        self.loop.correct(predicted=0.5, actual=0.6)
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.SAFETY] > 0
        assert weights[TaskCategory.GAIN] > 0

    def test_high_error_rising_trend(self):
        """测试高误差+上升趋势"""
        # 用递增的实际值，预测器跟不上，误差递增
        for actual in [0.1, 0.2, 0.4, 0.7, 0.9]:
            pred = self.loop.predict(EnvironmentState())
            self.loop.correct(predicted=pred, actual=actual)
        weights = self.loop.get_task_weights()
        # 高误差时安全优先
        assert weights[TaskCategory.SAFETY] >= 0.6

    def test_low_error_falling_trend(self):
        """测试低误差+下降趋势"""
        for actual in [0.5, 0.5, 0.5, 0.5, 0.49, 0.48]:
            self.loop.correct(predicted=0.5, actual=actual)
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.EXPLORATION] >= 0.4

    def test_drive_weights_normalized(self):
        """测试驱力权重归一化"""
        self.loop.correct(predicted=0.0, actual=1.0)
        dw = self.loop.get_drive_weights()
        assert dw.safe + dw.gain + dw.eff == pytest.approx(1.0)

    def test_drive_weights_no_history(self):
        """测试无历史时驱力权重"""
        dw = self.loop.get_drive_weights()
        assert dw.safe + dw.gain + dw.eff == pytest.approx(1.0)

    def test_error_summary_empty(self):
        """测试空误差汇总"""
        summary = self.loop.get_error_summary()
        assert summary["count"] == 0

    def test_error_summary_with_data(self):
        """测试有数据时汇总"""
        self.loop.correct(predicted=0.5, actual=0.6)
        self.loop.correct(predicted=0.5, actual=0.7)
        summary = self.loop.get_error_summary()
        assert summary["count"] == 2
        assert "current_error" in summary
        assert "trend" in summary

    def test_get_last_error(self):
        """测试获取最近误差"""
        assert self.loop.get_last_error() is None
        self.loop.correct(predicted=0.5, actual=0.6)
        last = self.loop.get_last_error()
        assert last is not None
        assert last.actual == 0.6

    def test_get_last_trend(self):
        """测试获取最近趋势"""
        trend = self.loop.get_last_trend()
        assert trend.direction == "stable"

    def test_history_limit(self):
        """测试历史上限"""
        for i in range(60):
            self.loop.correct(predicted=0.0, actual=float(i) / 100)
        summary = self.loop.get_error_summary()
        assert summary["count"] <= 50

    def test_reset(self):
        """测试重置"""
        self.loop.correct(predicted=0.5, actual=0.6)
        self.loop.reset()
        assert self.loop.get_last_error() is None
        assert self.loop.get_error_summary()["count"] == 0

    def test_predict_after_corrections(self):
        """测试修正后预测更新"""
        for actual in [0.1, 0.2, 0.3]:
            self.loop.correct(predicted=0.0, actual=actual)
        state = EnvironmentState()
        prediction = self.loop.predict(state)
        assert prediction > 0

    def test_custom_predictor(self):
        """测试自定义预测器"""
        mock_predictor = MagicMock(spec=ErrorPredictor)
        mock_predictor.predict_next.return_value = 0.42
        loop = PredictionCorrectionLoop(predictor=mock_predictor)
        result = loop.predict(EnvironmentState())
        assert result == 0.42

    def test_weights_sum_to_one(self):
        """测试权重和为1"""
        for actual in [0.1, 0.3, 0.5, 0.7, 0.9]:
            self.loop.correct(predicted=0.0, actual=actual)
        weights = self.loop.get_task_weights()
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_normal_rising_trend(self):
        """测试正常误差+上升趋势"""
        for actual in [0.5, 0.5, 0.5, 0.6, 0.7]:
            self.loop.correct(predicted=0.5, actual=actual)
        weights = self.loop.get_task_weights()
        assert weights[TaskCategory.SAFETY] >= 0.3

    def test_normal_falling_trend(self):
        """测试正常误差+下降趋势"""
        # 误差从高到低下降，但保持在正常区间
        for actual in [0.9, 0.8, 0.7, 0.55, 0.45]:
            pred = self.loop.predict(EnvironmentState())
            self.loop.correct(predicted=pred, actual=actual)
        weights = self.loop.get_task_weights()
        # 下降趋势时收益优先
        assert weights[TaskCategory.GAIN] > 0

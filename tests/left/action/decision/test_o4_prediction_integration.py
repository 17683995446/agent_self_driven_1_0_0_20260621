"""
O4：预测修正闭环接入测试

验证DecisionEngine正确接入PredictionCorrectionLoop：
1. 未注入时向后兼容
2. 预测-修正-调整闭环
3. 误差上升→探索下降，误差下降→探索上升
4. 驱力权重获取
5. 误差回填
6. 异常处理
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from src.left.action.decision.decision import DecisionEngine
from src.left.action.decision.prediction_correction_loop import (
    PredictionCorrectionLoop,
    TaskCategory,
)
from src.platform.support.models.base.state import (
    EnvironmentState, SystemState, LogState, FileState, SelfState,
    GapState, DriveWeights,
)
from src.platform.support.models.base.task import Task, TaskResult, TaskPool


class TestO4BackwardCompatibility:
    """测试未注入PredictionCorrectionLoop时的向后兼容"""

    def test_no_loop_predict_returns_zero(self):
        """未注入时predict_next_error返回0"""
        engine = DecisionEngine()
        state = EnvironmentState()
        assert engine.predict_next_error(state) == 0.0

    def test_no_loop_correct_is_noop(self):
        """未注入时correct_prediction不报错"""
        engine = DecisionEngine()
        engine.correct_prediction(0.5, 0.6)
        # 无异常即通过

    def test_no_loop_adjust_is_noop(self):
        """未注入时adjust_exploration_by_error不报错"""
        engine = DecisionEngine()
        original = engine.current_exploration_ratio
        engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio == original

    def test_no_loop_get_weights_returns_none(self):
        """未注入时get_prediction_drive_weights返回None"""
        engine = DecisionEngine()
        assert engine.get_prediction_drive_weights() is None

    def test_no_loop_get_error_returns_zero(self):
        """未注入时get_current_prediction_error返回0"""
        engine = DecisionEngine()
        assert engine.get_current_prediction_error() == 0.0


class TestO4ComputeStateError:
    """测试状态误差计算"""

    def test_empty_state_error(self):
        """空状态误差为0"""
        engine = DecisionEngine()
        state = EnvironmentState()
        error = engine.compute_state_error(state)
        assert error == 0.0

    def test_high_load_state_high_error(self):
        """高负载状态误差高"""
        engine = DecisionEngine()
        state = EnvironmentState(
            system=SystemState(
                cpu_overall=0.9, memory_usage=0.9, memory_pressure=0.9,
                disk_usage=0.9, io_wait=0.9, network_rate=0.9,
                process_count=0.9, zombie_ratio=0.9,
            ),
        )
        error = engine.compute_state_error(state)
        assert 0.5 < error <= 1.0

    def test_low_load_state_low_error(self):
        """低负载状态误差低"""
        engine = DecisionEngine()
        state = EnvironmentState(
            system=SystemState(
                cpu_overall=0.01, memory_usage=0.01, memory_pressure=0.01,
                disk_usage=0.01, io_wait=0.01, network_rate=0.01,
                process_count=0.01, zombie_ratio=0.01,
            ),
        )
        error = engine.compute_state_error(state)
        assert 0.0 <= error < 0.1

    def test_error_in_range(self):
        """误差始终在[0, 1]范围内"""
        engine = DecisionEngine()
        state = EnvironmentState(
            system=SystemState(cpu_overall=1.0, memory_usage=1.0),
            logs=LogState(error_rate=1.0, warning_rate=1.0),
        )
        error = engine.compute_state_error(state)
        assert 0.0 <= error <= 1.0


class TestO4PredictCorrect:
    """测试预测-修正闭环"""

    def test_predict_calls_loop(self):
        """predict_next_error调用loop.predict"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.predict.return_value = 0.42
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        state = EnvironmentState()
        result = engine.predict_next_error(state)
        assert result == 0.42
        mock_loop.predict.assert_called_once_with(state)

    def test_correct_calls_loop(self):
        """correct_prediction调用loop.correct"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        engine.correct_prediction(0.5, 0.6, timestamp=123.0)
        mock_loop.correct.assert_called_once_with(0.5, 0.6, 123.0)

    def test_correct_default_timestamp(self):
        """correct_prediction默认时间戳为0"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        engine.correct_prediction(0.5, 0.6)
        mock_loop.correct.assert_called_once_with(0.5, 0.6, 0.0)

    def test_predict_exception_handled(self):
        """predict异常被捕获"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.predict.side_effect = RuntimeError("boom")
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        result = engine.predict_next_error(EnvironmentState())
        assert result == 0.0

    def test_correct_exception_handled(self):
        """correct异常被捕获"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.correct.side_effect = RuntimeError("boom")
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        engine.correct_prediction(0.5, 0.6)  # 不应抛异常


class TestO4ExplorationAdjustment:
    """测试误差趋势驱动探索比例调整"""

    def test_rising_error_decreases_exploration(self):
        """误差上升→探索比例下降"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_trend.return_value = ErrorTrend("rising", 0.1, 0.8)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.3,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        original = engine.current_exploration_ratio
        engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio < original

    def test_falling_error_increases_exploration(self):
        """误差下降→探索比例上升"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_trend.return_value = ErrorTrend("falling", 0.1, 0.8)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.2,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        original = engine.current_exploration_ratio
        engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio > original

    def test_stable_error_no_change(self):
        """误差稳定→探索比例不变"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_trend.return_value = ErrorTrend("stable", 0.0, 0.0)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.3,
        )
        original = engine.current_exploration_ratio
        engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio == pytest.approx(original)

    def test_exploration_respects_max_bound(self):
        """探索比例不超过最大值"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_trend.return_value = ErrorTrend("falling", 0.5, 1.0)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.45,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        for _ in range(20):
            engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio <= engine.max_exploration_ratio

    def test_exploration_respects_min_bound(self):
        """探索比例不低于最小值"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_trend.return_value = ErrorTrend("rising", 0.5, 1.0)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.15,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        for _ in range(20):
            engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio >= engine.min_exploration_ratio


class TestO4DriveWeights:
    """测试预测驱力权重"""

    def test_get_weights_returns_drive_weights(self):
        """get_prediction_drive_weights返回DriveWeights"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        weights = engine.get_prediction_drive_weights()
        assert weights is not None
        assert isinstance(weights, DriveWeights)
        assert weights.safe + weights.gain + weights.eff == pytest.approx(1.0)

    def test_high_error_safety_priority(self):
        """高误差时安全驱力权重最高"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        # 制造高误差
        engine.correct_prediction(0.0, 1.0)
        weights = engine.get_prediction_drive_weights()
        assert weights.safe >= weights.gain
        assert weights.safe >= weights.eff

    def test_low_error_gain_or_exploration_priority(self):
        """低误差时收益或探索权重较高"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        # 制造低误差
        engine.correct_prediction(0.5, 0.51)
        weights = engine.get_prediction_drive_weights()
        assert weights.gain + weights.eff > weights.safe

    def test_get_weights_exception_returns_none(self):
        """get_weights异常返回None"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_drive_weights.side_effect = RuntimeError("boom")
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        assert engine.get_prediction_drive_weights() is None


class TestO4CurrentError:
    """测试当前误差获取"""

    def test_no_history_returns_zero(self):
        """无历史时返回0"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        assert engine.get_current_prediction_error() == 0.0

    def test_after_correct_returns_error(self):
        """修正后返回相对误差"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        engine.correct_prediction(0.5, 0.6)
        error = engine.get_current_prediction_error()
        assert error > 0.0

    def test_exception_returns_zero(self):
        """异常时返回0"""
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.get_last_error.side_effect = RuntimeError("boom")
        engine = DecisionEngine(prediction_correction_loop=mock_loop)
        assert engine.get_current_prediction_error() == 0.0


class TestO4FullCycle:
    """测试完整预测-修正-调整-回填闭环"""

    def test_full_cycle_rising_error(self):
        """完整闭环：误差上升时探索下降"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.predict.return_value = 0.5
        mock_loop.get_last_trend.return_value = ErrorTrend("rising", 0.2, 0.9)
        mock_loop.get_last_error.return_value = MagicMock(relative_error=0.4)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.3,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        original_ratio = engine.current_exploration_ratio
        # 模拟多轮主循环
        for load in [0.1, 0.3, 0.5, 0.7, 0.9]:
            state = EnvironmentState(
                system=SystemState(cpu_overall=load, memory_usage=load),
            )
            predicted = engine.predict_next_error(state)
            actual = engine.compute_state_error(state)
            engine.correct_prediction(predicted, actual, state.timestamp)
            engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio < original_ratio

    def test_full_cycle_falling_error(self):
        """完整闭环：误差下降时探索上升"""
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        mock_loop = MagicMock(spec=PredictionCorrectionLoop)
        mock_loop.predict.return_value = 0.5
        mock_loop.get_last_trend.return_value = ErrorTrend("falling", 0.2, 0.9)
        mock_loop.get_last_error.return_value = MagicMock(relative_error=0.1)
        engine = DecisionEngine(
            prediction_correction_loop=mock_loop,
            base_exploration_ratio=0.2,
            min_exploration_ratio=0.1,
            max_exploration_ratio=0.5,
        )
        original_ratio = engine.current_exploration_ratio
        # 模拟多轮主循环，状态负载递减
        for load in [0.9, 0.7, 0.5, 0.3, 0.1]:
            state = EnvironmentState(
                system=SystemState(cpu_overall=load, memory_usage=load),
            )
            predicted = engine.predict_next_error(state)
            actual = engine.compute_state_error(state)
            engine.correct_prediction(predicted, actual, state.timestamp)
            engine.adjust_exploration_by_error()
        assert engine.current_exploration_ratio > original_ratio

    def test_error_feedback_to_perception(self):
        """误差回填到感知层"""
        loop = PredictionCorrectionLoop()
        engine = DecisionEngine(prediction_correction_loop=loop)
        from src.left.cognition.perception.perception import EnvironmentPerceptionModule
        perception = EnvironmentPerceptionModule()
        # 初始误差为0
        assert perception.get_current_state().self.prediction_error == 0.0
        # 执行预测修正
        engine.correct_prediction(0.0, 1.0)
        error = engine.get_current_prediction_error()
        perception.set_prediction_error(error)
        # 验证回填
        state = perception.get_current_state()
        assert state.self.prediction_error == pytest.approx(error)

    def test_error_feedback_clamped(self):
        """误差回填值被钳制到[0, 1]"""
        from src.left.cognition.perception.perception import EnvironmentPerceptionModule
        perception = EnvironmentPerceptionModule()
        perception.set_prediction_error(1.5)
        state = perception.get_current_state()
        assert state.self.prediction_error == 1.0
        perception.set_prediction_error(-0.5)
        state = perception.get_current_state()
        assert state.self.prediction_error == 0.0


class TestO4TrendToValue:
    """测试趋势转数值"""

    def test_rising_trend_positive(self):
        """上升趋势转为正值"""
        engine = DecisionEngine()
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        trend = ErrorTrend("rising", 0.1, 0.8)
        assert engine._trend_to_value(trend) == 0.1

    def test_falling_trend_negative(self):
        """下降趋势转为负值"""
        engine = DecisionEngine()
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        trend = ErrorTrend("falling", 0.1, 0.8)
        assert engine._trend_to_value(trend) == -0.1

    def test_stable_trend_zero(self):
        """稳定趋势转为0"""
        engine = DecisionEngine()
        from src.left.action.decision.prediction_correction_loop import ErrorTrend
        trend = ErrorTrend("stable", 0.0, 0.0)
        assert engine._trend_to_value(trend) == 0.0

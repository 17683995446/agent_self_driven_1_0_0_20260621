"""
多层预测模型实现

第一性原理：不同时间尺度需要不同模型，组合预测优于单一预测
类比：生物大脑的分层时间尺度——小脑（毫秒）、皮层（秒）、海马体（分钟）
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState
from .prediction_layer import PredictionLayer, LayerInput, LayerOutput, UpdateMetrics, ErrorSignal


class LowLevelLayerPredictor(PredictionLayer):
    """底层高频预测器（1-10秒）"""

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha
        self._last_prediction: Optional[EnvironmentState] = None
        self._errors: List[float] = []

    @property
    def time_scale(self) -> str:
        return "low"

    @property
    def horizon(self) -> int:
        return 1

    def predict(self, input_data: LayerInput) -> LayerOutput:
        states = input_data.state_sequence
        if len(states) < 2:
            return self._fallback_output(states)
        pred = self._predict_pipeline(states)
        return LayerOutput(
            prediction=pred,
            confidence=0.7,
            uncertainty={"cpu": 0.1, "memory": 0.1},
        )

    def _predict_pipeline(self, states: List[EnvironmentState]) -> EnvironmentState:
        """预测流水线"""
        pred = self._trend_extrapolate(states)
        pred = self._smooth_prediction(pred)
        self._last_prediction = pred
        return pred

    def _fallback_output(self, states: List[EnvironmentState]) -> LayerOutput:
        last = states[-1] if states else EnvironmentState()
        return LayerOutput(prediction=last, confidence=0.5, uncertainty={"all": 0.5})

    def _trend_extrapolate(self, states: List[EnvironmentState]) -> EnvironmentState:
        from dataclasses import replace
        prev, last = states[-2], states[-1]
        cpu_trend, mem_trend = self._compute_trends(prev, last)
        return self._build_extrapolated_state(last, cpu_trend, mem_trend)

    def _compute_trends(self, prev: EnvironmentState, last: EnvironmentState) -> Tuple[float, float]:
        """计算CPU和内存趋势"""
        cpu_trend = last.system.cpu_overall - prev.system.cpu_overall
        mem_trend = last.system.memory_usage - prev.system.memory_usage
        return cpu_trend, mem_trend

    def _build_extrapolated_state(self, last: EnvironmentState, cpu_trend: float, mem_trend: float) -> EnvironmentState:
        """构建外推状态"""
        from dataclasses import replace
        new_cpu = max(0.0, min(1.0, last.system.cpu_overall + cpu_trend))
        new_mem = max(0.0, min(1.0, last.system.memory_usage + mem_trend))
        new_system = replace(last.system, cpu_overall=new_cpu, memory_usage=new_mem)
        return replace(last, timestamp=time.time(), system=new_system)

    def _smooth_prediction(self, pred: EnvironmentState) -> EnvironmentState:
        if self._last_prediction is None:
            return pred
        from dataclasses import replace
        smooth_cpu = self.alpha * pred.system.cpu_overall + (1 - self.alpha) * self._last_prediction.system.cpu_overall
        smooth_mem = self.alpha * pred.system.memory_usage + (1 - self.alpha) * self._last_prediction.system.memory_usage
        new_system = replace(pred.system, cpu_overall=smooth_cpu, memory_usage=smooth_mem)
        return replace(pred, system=new_system)

    def update(self, prediction: LayerOutput, actual: LayerInput) -> UpdateMetrics:
        pred_state = prediction.prediction
        actual_state = actual.state_sequence[-1] if actual.state_sequence else EnvironmentState()
        error = abs(pred_state.system.cpu_overall - actual_state.system.cpu_overall)
        self._errors.append(error)
        return UpdateMetrics(error=error, improvement=0.0, learning_rate=self.alpha)

    def get_error_signal(self) -> ErrorSignal:
        recent_error = self._errors[-1] if self._errors else 0.0
        return ErrorSignal(magnitude=recent_error, direction="up" if recent_error > 0.1 else "stable", source="low")


class MidLevelLayerPredictor(PredictionLayer):
    """中层趋势预测器（1-30分钟）"""

    def __init__(self, window_size: int = 10) -> None:
        self.window_size = window_size
        self._errors: List[float] = []

    @property
    def time_scale(self) -> str:
        return "mid"

    @property
    def horizon(self) -> int:
        return 5

    def predict(self, input_data: LayerInput) -> LayerOutput:
        states = input_data.state_sequence
        if not states:
            return self._empty_output()
        pred = self._moving_average_predict(states)
        return LayerOutput(prediction=pred, confidence=0.6, uncertainty={"cpu": 0.15, "memory": 0.15})

    def _empty_output(self) -> LayerOutput:
        """空状态输出"""
        return LayerOutput(prediction=EnvironmentState(), confidence=0.5, uncertainty={"all": 0.5})

    def _moving_average_predict(self, states: List[EnvironmentState]) -> EnvironmentState:
        """移动平均预测"""
        recent = states[-self.window_size:]
        avg_cpu = sum(s.system.cpu_overall for s in recent) / len(recent)
        avg_mem = sum(s.system.memory_usage for s in recent) / len(recent)
        from dataclasses import replace
        new_system = replace(states[-1].system, cpu_overall=avg_cpu, memory_usage=avg_mem)
        return replace(states[-1], timestamp=time.time(), system=new_system)

    def update(self, prediction: LayerOutput, actual: LayerInput) -> UpdateMetrics:
        pred_state = prediction.prediction
        actual_state = actual.state_sequence[-1] if actual.state_sequence else EnvironmentState()
        error = abs(pred_state.system.cpu_overall - actual_state.system.cpu_overall)
        self._errors.append(error)
        return UpdateMetrics(error=error, improvement=0.0, learning_rate=0.1)

    def get_error_signal(self) -> ErrorSignal:
        recent_error = self._errors[-1] if self._errors else 0.0
        return ErrorSignal(magnitude=recent_error, direction="up" if recent_error > 0.1 else "stable", source="mid")


class HighLevelLayerPredictor(PredictionLayer):
    """高层抽象预测器（1-24小时）"""

    def __init__(self) -> None:
        self._errors: List[float] = []
        self._long_term_avg = 0.5

    @property
    def time_scale(self) -> str:
        return "high"

    @property
    def horizon(self) -> int:
        return 24

    def predict(self, input_data: LayerInput) -> LayerOutput:
        states = input_data.state_sequence
        if not states:
            return self._empty_output()
        pred = self._long_term_predict(states)
        return LayerOutput(prediction=pred, confidence=0.5, uncertainty={"cpu": 0.2, "memory": 0.2})

    def _long_term_predict(self, states: List[EnvironmentState]) -> EnvironmentState:
        """长期平均预测"""
        recent = states[-100:] if len(states) > 100 else states
        self._long_term_avg = sum(s.system.cpu_overall for s in recent) / len(recent)
        from dataclasses import replace
        new_system = replace(states[-1].system, cpu_overall=self._long_term_avg, memory_usage=self._long_term_avg)
        return replace(states[-1], timestamp=time.time(), system=new_system)

    def update(self, prediction: LayerOutput, actual: LayerInput) -> UpdateMetrics:
        pred_state = prediction.prediction
        actual_state = actual.state_sequence[-1] if actual.state_sequence else EnvironmentState()
        error = abs(pred_state.system.cpu_overall - actual_state.system.cpu_overall)
        self._errors.append(error)
        return UpdateMetrics(error=error, improvement=0.0, learning_rate=0.05)

    def get_error_signal(self) -> ErrorSignal:
        recent_error = self._errors[-1] if self._errors else 0.0
        return ErrorSignal(magnitude=recent_error, direction="up" if recent_error > 0.1 else "stable", source="high")

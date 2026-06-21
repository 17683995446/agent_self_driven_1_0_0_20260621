"""
预测-修正闭环控制器

第一性原理：智能 = 预测 + 修正 + 误差驱动进化
- 预测：基于历史状态预测下一状态
- 修正：比较预测与实际，计算误差
- 驱动：误差影响任务选择，闭合控制回路

类比：生物的"小脑"——持续预测运动结果，根据误差修正动作

核心机制：
1. 误差高 → 增加监控类任务频率（安全优先）
2. 误差低 → 增加探索类任务频率（收益优先）
3. 误差趋势上升 → 优先安全任务
4. 误差趋势下降 → 优先收益任务
"""

import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import (
    EnvironmentState, GapState, DriveWeights, DriveType,
)


logger = logging.getLogger(__name__)


class TaskCategory(Enum):
    """任务类别"""
    SAFETY = "safety"
    GAIN = "gain"
    EFFICIENCY = "efficiency"
    EXPLORATION = "exploration"


@dataclass
class PredictionError:
    """预测误差"""
    timestamp: float
    predicted: float
    actual: float
    error: float
    relative_error: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "predicted": round(self.predicted, 6),
            "actual": round(self.actual, 6),
            "error": round(self.error, 6),
            "relative_error": round(self.relative_error, 6),
        }


@dataclass
class ErrorTrend:
    """误差趋势"""
    direction: str  # "rising", "falling", "stable"
    magnitude: float
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "magnitude": round(self.magnitude, 6),
            "confidence": round(self.confidence, 4),
        }


class ErrorPredictor(ABC):
    """误差预测器抽象基类"""

    @abstractmethod
    def predict_next(self, history: List[float]) -> float:
        """预测下一个值"""
        pass


class MovingAveragePredictor(ErrorPredictor):
    """移动平均预测器"""

    def __init__(self, window: int = 5) -> None:
        self._window = window

    def predict_next(self, history: List[float]) -> float:
        """预测下一个值"""
        if not history:
            return 0.0
        recent = history[-self._window:]
        return sum(recent) / len(recent)


class LinearTrendPredictor(ErrorPredictor):
    """线性趋势预测器"""

    def __init__(self, window: int = 5) -> None:
        self._window = window

    def predict_next(self, history: List[float]) -> float:
        """预测下一个值"""
        if not history:
            return 0.0
        if len(history) < 2:
            return history[-1]
        recent = history[-self._window:]
        return self._linear_extrapolate(recent)

    def _linear_extrapolate(self, values: List[float]) -> float:
        """线性外推"""
        n = len(values)
        if n < 2:
            return values[0]
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if abs(denominator) < 1e-10:
            return y_mean
        slope = numerator / denominator
        return y_mean + slope * (n - 1 - x_mean + 1)


class TrendDetector:
    """趋势检测器"""

    RISING_THRESHOLD: float = 1.5
    FALLING_THRESHOLD: float = 0.5
    MIN_SAMPLES: int = 3

    def detect(self, history: List[float]) -> ErrorTrend:
        """检测趋势"""
        if len(history) < self.MIN_SAMPLES:
            return ErrorTrend("stable", 0.0, 0.0)
        return self._compute_trend(history)

    def _compute_trend(self, history: List[float]) -> ErrorTrend:
        """计算趋势"""
        recent = history[-self.MIN_SAMPLES:]
        recent_avg = sum(recent[-2:]) / 2.0
        older_avg = sum(recent[:-2]) / max(len(recent) - 2, 1)
        magnitude = recent_avg - older_avg
        confidence = min(len(history) / 10.0, 1.0)
        direction = self._classify_direction(recent_avg, older_avg)
        return ErrorTrend(direction, magnitude, confidence)

    def _classify_direction(self, recent: float, older: float) -> str:
        """分类趋势方向"""
        if older < 1e-10:
            return "stable" if recent < 1e-10 else "rising"
        ratio = recent / older
        if ratio > self.RISING_THRESHOLD:
            return "rising"
        if ratio < self.FALLING_THRESHOLD:
            return "falling"
        return "stable"


class PredictionCorrectionLoop:
    """
    预测-修正闭环控制器

    第一性原理：误差驱动任务选择，闭合控制回路
    - 记录历史预测误差
    - 检测误差趋势
    - 根据误差和趋势调整任务类别权重
    - 驱动系统从"空转"变为"误差响应"
    """

    HISTORY_LIMIT: int = 50
    HIGH_ERROR_THRESHOLD: float = 0.3
    LOW_ERROR_THRESHOLD: float = 0.05

    def __init__(
        self,
        predictor: Optional[ErrorPredictor] = None,
        trend_detector: Optional[TrendDetector] = None,
    ) -> None:
        self._predictor = predictor or MovingAveragePredictor()
        self._trend_detector = trend_detector or TrendDetector()
        self._error_history: List[PredictionError] = []
        self._raw_history: List[float] = []
        self._last_trend: ErrorTrend = ErrorTrend("stable", 0.0, 0.0)
        self._last_prediction: float = 0.0

    def predict(self, state: EnvironmentState) -> float:
        """预测下一时刻的预测误差"""
        self._last_prediction = self._predictor.predict_next(self._raw_history)
        return self._last_prediction

    def correct(
        self,
        predicted: float,
        actual: float,
        timestamp: float = 0.0,
    ) -> PredictionError:
        """修正：计算预测误差"""
        error = actual - predicted
        rel_error = abs(error) / max(abs(actual), 1e-10)
        pred_error = PredictionError(
            timestamp=timestamp,
            predicted=predicted,
            actual=actual,
            error=error,
            relative_error=rel_error,
        )
        self._record_error(pred_error)
        return pred_error

    def _record_error(self, pred_error: PredictionError) -> None:
        """记录误差"""
        self._error_history.append(pred_error)
        if len(self._error_history) > self.HISTORY_LIMIT:
            self._error_history = self._error_history[-self.HISTORY_LIMIT:]
        self._raw_history.append(pred_error.relative_error)
        if len(self._raw_history) > self.HISTORY_LIMIT:
            self._raw_history = self._raw_history[-self.HISTORY_LIMIT:]
        self._last_trend = self._trend_detector.detect(self._raw_history)

    def get_task_weights(self) -> Dict[TaskCategory, float]:
        """根据误差和趋势获取任务类别权重"""
        current_error = self._current_error()
        trend = self._last_trend
        if current_error > self.HIGH_ERROR_THRESHOLD:
            return self._high_error_weights(trend)
        if current_error < self.LOW_ERROR_THRESHOLD:
            return self._low_error_weights(trend)
        return self._normal_weights(trend)

    def _current_error(self) -> float:
        """获取当前误差"""
        if not self._error_history:
            return 0.0
        return self._error_history[-1].relative_error

    def _high_error_weights(self, trend: ErrorTrend) -> Dict[TaskCategory, float]:
        """高误差权重——安全优先"""
        base = {TaskCategory.SAFETY: 0.6, TaskCategory.GAIN: 0.1,
                TaskCategory.EFFICIENCY: 0.2, TaskCategory.EXPLORATION: 0.1}
        if trend.direction == "rising":
            base[TaskCategory.SAFETY] = 0.7
            base[TaskCategory.EXPLORATION] = 0.0
        return base

    def _low_error_weights(self, trend: ErrorTrend) -> Dict[TaskCategory, float]:
        """低误差权重——探索优先"""
        base = {TaskCategory.SAFETY: 0.1, TaskCategory.GAIN: 0.3,
                TaskCategory.EFFICIENCY: 0.2, TaskCategory.EXPLORATION: 0.4}
        if trend.direction == "falling":
            base[TaskCategory.EXPLORATION] = 0.5
            base[TaskCategory.GAIN] = 0.2
        return base

    def _normal_weights(self, trend: ErrorTrend) -> Dict[TaskCategory, float]:
        """正常误差权重——平衡"""
        base = {TaskCategory.SAFETY: 0.3, TaskCategory.GAIN: 0.3,
                TaskCategory.EFFICIENCY: 0.2, TaskCategory.EXPLORATION: 0.2}
        if trend.direction == "rising":
            base[TaskCategory.SAFETY] = 0.4
            base[TaskCategory.EXPLORATION] = 0.1
        elif trend.direction == "falling":
            base[TaskCategory.GAIN] = 0.4
            base[TaskCategory.SAFETY] = 0.2
        return base

    def get_drive_weights(self) -> DriveWeights:
        """获取驱力权重（用于DecisionEngine）"""
        weights = self.get_task_weights()
        safe = weights[TaskCategory.SAFETY]
        gain = weights[TaskCategory.GAIN]
        eff = weights[TaskCategory.EFFICIENCY] + weights[TaskCategory.EXPLORATION]
        return self._normalize_drive_weights(safe, gain, eff)

    def _normalize_drive_weights(
        self, safe: float, gain: float, eff: float,
    ) -> DriveWeights:
        """归一化驱力权重"""
        total = safe + gain + eff
        if total < 1e-10:
            return DriveWeights(0.4, 0.4, 0.2)
        return DriveWeights(
            safe=round(safe / total, 4),
            gain=round(gain / total, 4),
            eff=round(eff / total, 4),
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """获取误差汇总"""
        if not self._error_history:
            return {"count": 0, "avg_error": 0.0, "trend": "stable"}
        errors = [e.relative_error for e in self._error_history]
        return {
            "count": len(errors),
            "current_error": round(errors[-1], 6),
            "avg_error": round(sum(errors) / len(errors), 6),
            "max_error": round(max(errors), 6),
            "min_error": round(min(errors), 6),
            "trend": self._last_trend.to_dict(),
            "last_prediction": round(self._last_prediction, 6),
        }

    def get_last_error(self) -> Optional[PredictionError]:
        """获取最近一次误差"""
        if not self._error_history:
            return None
        return self._error_history[-1]

    def get_last_trend(self) -> ErrorTrend:
        """获取最近趋势"""
        return self._last_trend

    def reset(self) -> None:
        """重置历史"""
        self._error_history.clear()
        self._raw_history.clear()
        self._last_trend = ErrorTrend("stable", 0.0, 0.0)
        self._last_prediction = 0.0

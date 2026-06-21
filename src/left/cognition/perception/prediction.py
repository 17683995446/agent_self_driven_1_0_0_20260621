"""
多层预测模型

第一性原理：预测是认知的核心，误差是学习的信号
类比：生物大脑的"预测性编码"——大脑持续预测感官输入，误差驱动学习
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from collections import deque

try:
    import numpy as np
except ImportError:
    np = None

from ....platform.support.models.base.state import EnvironmentState


logger = logging.getLogger(__name__)


class PredictionModel(ABC):
    """
    预测模型抽象基类

    第一性原理：预测 = f(历史状态) → 未来状态
    """

    @abstractmethod
    def predict(self, state_history: List[EnvironmentState]) -> EnvironmentState:
        """预测下一状态"""
        pass

    @abstractmethod
    def update(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """根据预测误差更新模型"""
        pass

    @abstractmethod
    def get_error(self) -> float:
        """获取当前平均误差"""
        pass


class LowLevelPredictor(PredictionModel):
    """
    底层高频预测器

    时间尺度：1-10秒
    模型：趋势外推 + 指数平滑 + 在线自适应学习率
    """

    def __init__(self, alpha: float = 0.3, adaptation_rate: float = 0.1) -> None:
        self.alpha = alpha
        self.base_alpha = alpha
        self.adaptation_rate = adaptation_rate
        self.last_prediction: Optional[EnvironmentState] = None
        self.errors: deque = deque(maxlen=100)
        self.error_history: deque = deque(maxlen=20)
        logger.info("LowLevelPredictor initialized")

    def _get_last_two(self, state_history: List[EnvironmentState]) -> Tuple[EnvironmentState, EnvironmentState]:
        """获取最近两个状态"""
        return state_history[-2], state_history[-1]

    def _compute_trends(self, prev: EnvironmentState, last: EnvironmentState) -> Tuple[float, float]:
        """计算趋势（简单差分）"""
        trend_cpu = last.system.cpu_overall - prev.system.cpu_overall
        trend_mem = last.system.memory_usage - prev.system.memory_usage
        return trend_cpu, trend_mem

    def _extrapolate(self, last: EnvironmentState, trend_cpu: float, trend_mem: float) -> Tuple[float, float]:
        """趋势外推"""
        pred_cpu = last.system.cpu_overall + trend_cpu
        pred_mem = last.system.memory_usage + trend_mem
        pred_cpu = max(0.0, min(1.0, pred_cpu))
        pred_mem = max(0.0, min(1.0, pred_mem))
        return pred_cpu, pred_mem

    def _smooth(self, pred_cpu: float, pred_mem: float) -> Tuple[float, float]:
        """指数平滑"""
        if self.last_prediction is None:
            return pred_cpu, pred_mem
        smoothed_cpu = self.alpha * pred_cpu + (1 - self.alpha) * self.last_prediction.system.cpu_overall
        smoothed_mem = self.alpha * pred_mem + (1 - self.alpha) * self.last_prediction.system.memory_usage
        return smoothed_cpu, smoothed_mem

    def _replace_system(self, last: EnvironmentState, cpu: float, mem: float):
        from dataclasses import replace
        return replace(last.system, cpu_overall=cpu, memory_usage=mem)

    def _build_prediction(self, last: EnvironmentState, pred_cpu: float, pred_mem: float) -> EnvironmentState:
        from dataclasses import replace
        return replace(last, timestamp=time.time(), system=self._replace_system(last, pred_cpu, pred_mem))

    def _fallback_prediction(self, state_history: List[EnvironmentState]) -> EnvironmentState:
        """返回回退预测"""
        if state_history:
            return state_history[-1]
        return EnvironmentState()

    def _apply_prediction_pipeline(self, prev: EnvironmentState, last: EnvironmentState) -> EnvironmentState:
        """应用预测流水线"""
        trend_cpu, trend_mem = self._compute_trends(prev, last)
        pred_cpu, pred_mem = self._extrapolate(last, trend_cpu, trend_mem)
        pred_cpu, pred_mem = self._smooth(pred_cpu, pred_mem)
        return self._build_prediction(last, pred_cpu, pred_mem)

    def predict(self, state_history: List[EnvironmentState]) -> EnvironmentState:
        """
        预测下一状态

        算法：
        1. 如果有历史，计算趋势
        2. 趋势外推
        3. 指数平滑
        """
        if len(state_history) < 2:
            return self._fallback_prediction(state_history)
        prev, last = self._get_last_two(state_history)
        prediction = self._apply_prediction_pipeline(prev, last)
        self.last_prediction = prediction
        return prediction

    def _compute_error(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """计算预测误差"""
        cpu_error = abs(prediction.system.cpu_overall - actual.system.cpu_overall)
        mem_error = abs(prediction.system.memory_usage - actual.system.memory_usage)
        return (cpu_error + mem_error) / 2.0

    def _compute_error_averages(self, recent_errors: List[float]) -> Tuple[float, float]:
        """计算早期和近期误差均值"""
        early_avg = sum(recent_errors[:5]) / 5.0
        late_avg = sum(recent_errors[-5:]) / 5.0
        return early_avg, late_avg

    def _apply_alpha_adjustment(self, early_avg: float, late_avg: float) -> None:
        """应用学习率调整"""
        if late_avg > early_avg:
            self.alpha = min(0.8, self.alpha + self.adaptation_rate)
        else:
            self.alpha = max(0.05, self.alpha - self.adaptation_rate * 0.5)

    def _adapt_alpha(self, error: float) -> None:
        """根据误差自适应调整学习率"""
        self.error_history.append(error)
        if len(self.error_history) < 5:
            return
        recent_errors = list(self.error_history)
        if len(recent_errors) >= 10:
            early_avg, late_avg = self._compute_error_averages(recent_errors)
            self._apply_alpha_adjustment(early_avg, late_avg)

    def update(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """更新模型（计算误差并自适应调整）"""
        error = self._compute_error(prediction, actual)
        self.errors.append(error)
        self._adapt_alpha(error)
        return error

    def get_error(self) -> float:
        """获取平均误差"""
        if not self.errors:
            return 0.0
        return sum(self.errors) / len(self.errors)

    def get_error_trend(self) -> float:
        """获取误差趋势"""
        if len(self.errors) < 10:
            return 0.0
        recent = list(self.errors)[-10:]
        half = len(recent) // 2
        early = sum(recent[:half]) / half
        late = sum(recent[half:]) / (len(recent) - half)
        return late - early


class MidLevelPredictor(PredictionModel):
    """
    中层趋势预测器

    时间尺度：1-30分钟
    模型：移动平均 + 权重自适应
    """

    def __init__(self, window_size: int = 10) -> None:
        self.window_size = window_size
        self.errors: deque = deque(maxlen=100)
        self.error_history: deque = deque(maxlen=20)
        self.weight = 0.3
        logger.info("MidLevelPredictor initialized")

    def _get_recent(self, state_history: List[EnvironmentState]) -> List[EnvironmentState]:
        """获取最近window_size个状态"""
        return state_history[-self.window_size:]

    def _compute_averages(self, recent: List[EnvironmentState]) -> Tuple[float, float]:
        """计算移动平均"""
        avg_cpu = sum(s.system.cpu_overall for s in recent) / len(recent)
        avg_mem = sum(s.system.memory_usage for s in recent) / len(recent)
        return avg_cpu, avg_mem

    def _replace_system(self, last: EnvironmentState, cpu: float, mem: float):
        from dataclasses import replace
        return replace(last.system, cpu_overall=cpu, memory_usage=mem)

    def _build_prediction(self, last: EnvironmentState, avg_cpu: float, avg_mem: float) -> EnvironmentState:
        from dataclasses import replace
        return replace(last, timestamp=time.time(), system=self._replace_system(last, avg_cpu, avg_mem))

    def predict(self, state_history: List[EnvironmentState]) -> EnvironmentState:
        """预测下一状态（移动平均）"""
        if not state_history:
            return EnvironmentState()
        recent = self._get_recent(state_history)
        avg_cpu, avg_mem = self._compute_averages(recent)
        return self._build_prediction(state_history[-1], avg_cpu, avg_mem)

    def _compute_error(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """计算预测误差"""
        cpu_error = abs(prediction.system.cpu_overall - actual.system.cpu_overall)
        mem_error = abs(prediction.system.memory_usage - actual.system.memory_usage)
        return (cpu_error + mem_error) / 2.0

    def _compute_halves_avg(self, recent: List[float]) -> Tuple[float, float]:
        """计算前后半段平均值"""
        half = len(recent) // 2
        early = sum(recent[:half]) / half
        late = sum(recent[half:]) / (len(recent) - half)
        return early, late

    def _apply_weight_adjustment(self, early: float, late: float) -> None:
        """应用权重调整"""
        if late > early * 1.2:
            self.weight = max(0.1, self.weight * 0.9)
        elif late < early * 0.8:
            self.weight = min(0.5, self.weight * 1.1)

    def _adapt_weight(self, error: float) -> None:
        """根据误差调整模型权重"""
        self.error_history.append(error)
        if len(self.error_history) < 10:
            return
        recent = list(self.error_history)[-10:]
        early, late = self._compute_halves_avg(recent)
        self._apply_weight_adjustment(early, late)

    def update(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """更新模型"""
        error = self._compute_error(prediction, actual)
        self.errors.append(error)
        self._adapt_weight(error)
        return error

    def get_error(self) -> float:
        """获取平均误差"""
        if not self.errors:
            return 0.0
        return sum(self.errors) / len(self.errors)

    def _compute_error_trend(self, recent: List[float]) -> float:
        """计算误差趋势"""
        half = len(recent) // 2
        early = sum(recent[:half]) / half
        late = sum(recent[half:]) / (len(recent) - half)
        return late - early

    def get_error_trend(self) -> float:
        """获取误差趋势"""
        if len(self.errors) < 10:
            return 0.0
        recent = list(self.errors)[-10:]
        return self._compute_error_trend(recent)


class HighLevelPredictor(PredictionModel):
    """
    高层抽象预测器

    时间尺度：1-24小时
    模型：长期趋势 + 周期性检测
    """

    def __init__(self) -> None:
        self.errors: deque = deque(maxlen=100)
        self.error_history: deque = deque(maxlen=20)
        self.long_term_average = 0.5
        self.weight = 0.2
        logger.info("HighLevelPredictor initialized")

    def _get_recent_for_average(self, state_history: List[EnvironmentState]) -> List[EnvironmentState]:
        """获取用于计算长期平均的状态"""
        if len(state_history) > 100:
            return state_history[-100:]
        return state_history

    def _compute_long_term_average(self, recent: List[EnvironmentState]) -> float:
        """计算长期平均"""
        return sum(s.system.cpu_overall for s in recent) / len(recent)

    def _replace_system(self, last: EnvironmentState, avg: float):
        from dataclasses import replace
        return replace(last.system, cpu_overall=avg, memory_usage=avg)

    def _build_prediction(self, last: EnvironmentState, avg: float) -> EnvironmentState:
        from dataclasses import replace
        return replace(last, timestamp=time.time(), system=self._replace_system(last, avg))

    def predict(self, state_history: List[EnvironmentState]) -> EnvironmentState:
        """预测下一状态（长期平均值）"""
        if not state_history:
            return EnvironmentState()
        recent = self._get_recent_for_average(state_history)
        self.long_term_average = self._compute_long_term_average(recent)
        return self._build_prediction(state_history[-1], self.long_term_average)

    def _compute_error(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """计算预测误差"""
        cpu_error = abs(prediction.system.cpu_overall - actual.system.cpu_overall)
        mem_error = abs(prediction.system.memory_usage - actual.system.memory_usage)
        return (cpu_error + mem_error) / 2.0

    def _compute_halves_avg(self, recent: List[float]) -> Tuple[float, float]:
        """计算前后半段平均值"""
        half = len(recent) // 2
        early = sum(recent[:half]) / half
        late = sum(recent[half:]) / (len(recent) - half)
        return early, late

    def _apply_weight_adjustment(self, early: float, late: float) -> None:
        """应用权重调整"""
        if late > early * 1.2:
            self.weight = max(0.05, self.weight * 0.9)
        elif late < early * 0.8:
            self.weight = min(0.3, self.weight * 1.1)

    def _adapt_weight(self, error: float) -> None:
        """根据误差调整模型权重"""
        self.error_history.append(error)
        if len(self.error_history) < 10:
            return
        recent = list(self.error_history)[-10:]
        early, late = self._compute_halves_avg(recent)
        self._apply_weight_adjustment(early, late)

    def update(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """更新模型"""
        error = self._compute_error(prediction, actual)
        self.errors.append(error)
        self._adapt_weight(error)
        return error

    def get_error(self) -> float:
        """获取平均误差"""
        if not self.errors:
            return 0.0
        return sum(self.errors) / len(self.errors)

    def _compute_error_trend(self, recent: List[float]) -> float:
        """计算误差趋势"""
        half = len(recent) // 2
        early = sum(recent[:half]) / half
        late = sum(recent[half:]) / (len(recent) - half)
        return late - early

    def get_error_trend(self) -> float:
        """获取误差趋势"""
        if len(self.errors) < 10:
            return 0.0
        recent = list(self.errors)[-10:]
        return self._compute_error_trend(recent)


class HierarchicalPredictionModel:
    """
    分层预测模型

    管理三层预测器之间的信息流动与自适应权重组合
    """

    def __init__(self) -> None:
        self.low = LowLevelPredictor()
        self.mid = MidLevelPredictor()
        self.high = HighLevelPredictor()
        self.state_history: deque = deque(maxlen=1000)
        self.combination_weights = [0.5, 0.3, 0.2]
        logger.info("HierarchicalPredictionModel initialized")

    def _get_history(self) -> List[EnvironmentState]:
        """获取当前历史状态列表"""
        return list(self.state_history)

    def _compute_combined_cpu(self, low_pred: EnvironmentState, mid_pred: EnvironmentState, high_pred: EnvironmentState) -> float:
        """计算组合CPU预测"""
        return (
            self.combination_weights[0] * low_pred.system.cpu_overall +
            self.combination_weights[1] * mid_pred.system.cpu_overall +
            self.combination_weights[2] * high_pred.system.cpu_overall
        )

    def _compute_combined_mem(self, low_pred: EnvironmentState, mid_pred: EnvironmentState, high_pred: EnvironmentState) -> float:
        """计算组合内存预测"""
        return (
            self.combination_weights[0] * low_pred.system.memory_usage +
            self.combination_weights[1] * mid_pred.system.memory_usage +
            self.combination_weights[2] * high_pred.system.memory_usage
        )

    def _replace_system(self, last: EnvironmentState, cpu: float, mem: float):
        from dataclasses import replace
        return replace(last.system, cpu_overall=cpu, memory_usage=mem)

    def _build_combined_prediction(self, last: EnvironmentState, combined_cpu: float, combined_mem: float) -> EnvironmentState:
        from dataclasses import replace
        return replace(last, timestamp=time.time(), system=self._replace_system(last, combined_cpu, combined_mem))

    def _run_layer_predictions(self, history: List[EnvironmentState]) -> Tuple[EnvironmentState, EnvironmentState, EnvironmentState]:
        """运行三层预测"""
        return (
            self.low.predict(history),
            self.mid.predict(history),
            self.high.predict(history),
        )

    def predict(self) -> EnvironmentState:
        """
        分层预测

        信息流动：
        1. 底层预测（高频）
        2. 中层预测（中频）
        3. 高层预测（低频）
        4. 组合预测（自适应权重）
        """
        history = self._get_history()
        if not history:
            return EnvironmentState()
        low_pred, mid_pred, high_pred = self._run_layer_predictions(history)
        combined_cpu = self._compute_combined_cpu(low_pred, mid_pred, high_pred)
        combined_mem = self._compute_combined_mem(low_pred, mid_pred, high_pred)
        return self._build_combined_prediction(history[-1], combined_cpu, combined_mem)

    def _get_pred_history(self, history: List[EnvironmentState]) -> List[EnvironmentState]:
        """获取用于预测的子历史（排除最后一个）"""
        return history[:-1]

    def _update_predictors(self, pred_history: List[EnvironmentState], actual: EnvironmentState) -> Tuple[float, float, float]:
        """更新各层预测器"""
        low_pred = self.low.predict(pred_history)
        mid_pred = self.mid.predict(pred_history)
        high_pred = self.high.predict(pred_history)
        low_error = self.low.update(low_pred, actual)
        mid_error = self.mid.update(mid_pred, actual)
        high_error = self.high.update(high_pred, actual)
        return low_error, mid_error, high_error

    def _compute_inverse_errors(self, total_error: float, errors: Tuple[float, float, float]) -> List[float]:
        """计算逆误差列表"""
        return [max(0.01, total_error - e) for e in errors]

    def _normalize_weights(self, inverse_errors: List[float]) -> List[float]:
        """归一化权重"""
        total_inverse = sum(inverse_errors)
        return [e / total_inverse for e in inverse_errors]

    def _adapt_combination_weights(self, low_error: float, mid_error: float, high_error: float) -> None:
        """根据各层误差自适应调整组合权重"""
        total_error = low_error + mid_error + high_error
        if total_error < 1e-6:
            return
        inverse_errors = self._compute_inverse_errors(total_error, (low_error, mid_error, high_error))
        self.combination_weights = self._normalize_weights(inverse_errors)

    def _log_update(self, low_error: float, mid_error: float, high_error: float) -> None:
        """记录更新日志"""
        logger.debug(
            f"Prediction errors: low={low_error:.3f}, "
            f"mid={mid_error:.3f}, high={high_error:.3f}, "
            f"weights={self.combination_weights}"
        )

    def _prepare_history(self, actual: EnvironmentState) -> Optional[List[EnvironmentState]]:
        self.state_history.append(actual)
        history = self._get_history()
        if len(history) < 2:
            return None
        return self._get_pred_history(history)

    def update(self, actual: EnvironmentState) -> None:
        """
        更新所有预测器

        第一性原理：误差是学习的信号
        """
        pred_history = self._prepare_history(actual)
        if pred_history is None:
            return
        low_error, mid_error, high_error = self._update_predictors(pred_history, actual)
        self._adapt_combination_weights(low_error, mid_error, high_error)
        self._log_update(low_error, mid_error, high_error)

    def get_average_error(self) -> float:
        """获取综合平均误差"""
        errors = [
            self.low.get_error(),
            self.mid.get_error(),
            self.high.get_error()
        ]
        return sum(errors) / len(errors) if errors else 0.0

    def get_error_trend(self) -> float:
        """
        获取误差趋势

        Returns:
            float: 正=误差上升，负=误差下降，0=稳定
        """
        trends = [
            self.low.get_error_trend(),
            self.mid.get_error_trend(),
            self.high.get_error_trend(),
        ]
        valid_trends = [t for t in trends if t != 0.0]
        return sum(valid_trends) / len(valid_trends) if valid_trends else 0.0

    def _build_layer_stats(self) -> dict:
        return {
            "low_error": self.low.get_error(),
            "mid_error": self.mid.get_error(),
            "high_error": self.high.get_error(),
        }

    def _build_meta_stats(self) -> dict:
        return {
            "low_alpha": self.low.alpha,
            "mid_weight": self.mid.weight,
            "high_weight": self.high.weight,
            "combination_weights": self.combination_weights,
            "error_trend": self.get_error_trend(),
            "history_size": len(self.state_history),
        }

    def _build_learning_stats(self) -> dict:
        return {**self._build_layer_stats(), **self._build_meta_stats()}

    def get_learning_stats(self) -> dict:
        """获取学习统计信息"""
        return self._build_learning_stats()

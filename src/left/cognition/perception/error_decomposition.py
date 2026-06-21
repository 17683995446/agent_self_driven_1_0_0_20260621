"""
预测误差分解

第一性原理：误差必须可分解，才能定位问题来源
类比：生物大脑的误差归因——区分感觉误差、运动误差、预测误差
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ....platform.support.models.base.state import EnvironmentState

try:
    import numpy as np
except ImportError:
    np = None


@dataclass
class ErrorDecomposition:
    """误差分解结果"""
    total_error: float
    bias_error: float
    variance_error: float
    noise_error: float
    component_errors: Dict[str, float]


class PredictionErrorDecomposer:
    """
    预测误差分解器

    将总误差分解为偏差、方差、噪声三个部分
    """

    def __init__(self) -> None:
        self.history: List[Tuple[EnvironmentState, EnvironmentState]] = []

    def add(self, prediction: EnvironmentState, actual: EnvironmentState) -> None:
        """添加预测-实际对"""
        self.history.append((prediction, actual))

    def decompose(self, prediction: EnvironmentState, actual: EnvironmentState) -> ErrorDecomposition:
        """
        分解误差

        分解：
        1. 偏差误差（系统性的预测偏差）
        2. 方差误差（预测的不稳定性）
        3. 噪声误差（不可预测的部分）
        """
        total = self._compute_total_error(prediction, actual)
        bias = self._compute_bias_error()
        variance = self._compute_variance_error(prediction)
        noise = max(0.0, total - bias - variance)
        components = self._compute_component_errors(prediction, actual)
        return ErrorDecomposition(
            total_error=total,
            bias_error=bias,
            variance_error=variance,
            noise_error=noise,
            component_errors=components,
        )

    def _compute_total_error(self, prediction: EnvironmentState, actual: EnvironmentState) -> float:
        """计算总误差"""
        pred_vec = prediction.to_vector()
        actual_vec = actual.to_vector()
        if np is not None:
            return float(np.mean(np.abs(np.array(pred_vec) - np.array(actual_vec))))
        diffs = [abs(p - a) for p, a in zip(pred_vec, actual_vec)]
        return sum(diffs) / len(diffs) if diffs else 0.0

    def _compute_bias_error(self) -> float:
        """计算偏差误差（历史平均误差）"""
        if len(self.history) < 2:
            return 0.0
        errors = []
        for pred, actual in self.history:
            pred_vec = pred.to_vector()
            actual_vec = actual.to_vector()
            if np is not None:
                errors.append(float(np.mean(np.abs(np.array(pred_vec) - np.array(actual_vec)))))
            else:
                diffs = [abs(p - a) for p, a in zip(pred_vec, actual_vec)]
                errors.append(sum(diffs) / len(diffs) if diffs else 0.0)
        return sum(errors) / len(errors) if errors else 0.0

    def _compute_variance_error(self, prediction: EnvironmentState) -> float:
        """计算方差误差（预测的不稳定性）"""
        if len(self.history) < 2:
            return 0.0
        pred_vecs = [p.to_vector() for p, _ in self.history[-10:]]
        pred_vecs.append(prediction.to_vector())
        if np is not None:
            return float(np.mean(np.var(np.array(pred_vecs), axis=0)))
        # 纯Python降级：计算每维方差再取均值
        if not pred_vecs:
            return 0.0
        dim = len(pred_vecs[0])
        var_sum = 0.0
        for d in range(dim):
            col = [v[d] for v in pred_vecs if d < len(v)]
            mean = sum(col) / len(col) if col else 0.0
            var_sum += sum((x - mean) ** 2 for x in col) / len(col) if col else 0.0
        return var_sum / dim if dim > 0 else 0.0

    def _compute_component_errors(self, prediction: EnvironmentState, actual: EnvironmentState) -> Dict[str, float]:
        """计算各组件误差"""
        return {
            "cpu": abs(prediction.system.cpu_overall - actual.system.cpu_overall),
            "memory": abs(prediction.system.memory_usage - actual.system.memory_usage),
            "disk": abs(prediction.system.disk_usage - actual.system.disk_usage),
        }

    def clear(self) -> None:
        """清空历史"""
        self.history.clear()

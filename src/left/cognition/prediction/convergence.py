"""
权重收敛性分析器

第一性原理：系统必须稳定，否则无法持续运行
类比：生物体内稳态——体温、血糖等必须收敛到稳定范围
"""

from dataclasses import dataclass
from typing import List, Tuple
import math

from ....platform.support.models.base.state import DriveWeights, GapState

try:
    import numpy as np
except ImportError:
    np = None


@dataclass
class ConvergenceResult:
    """收敛性分析结果"""
    converged: bool
    iterations: int
    final_weights: DriveWeights
    weight_history: List[DriveWeights]
    gap_history: List[GapState]


class WeightConvergenceAnalyzer:
    """
    权重收敛性分析器

    验证权重更新是否满足收敛条件
    """

    def __init__(
        self,
        max_iterations: int = 1000,
        tolerance: float = 1e-6,
    ) -> None:
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def analyze(
        self,
        initial_weights: DriveWeights,
        gap_sequence: List[GapState],
        adaptation_rate: float = 0.3,
    ) -> ConvergenceResult:
        """
        分析权重序列的收敛性

        模拟权重更新过程，检查是否收敛
        """
        weights = initial_weights
        weight_history: List[DriveWeights] = [weights]
        gap_history: List[GapState] = []

        for i, gaps in enumerate(gap_sequence):
            new_weights = self._update_weights(weights, gaps, adaptation_rate)
            weight_history.append(new_weights)
            gap_history.append(gaps)
            if self._check_convergence(weights, new_weights):
                return ConvergenceResult(
                    converged=True,
                    iterations=i + 1,
                    final_weights=new_weights,
                    weight_history=weight_history,
                    gap_history=gap_history,
                )
            weights = new_weights

        return ConvergenceResult(
            converged=False,
            iterations=len(gap_sequence),
            final_weights=weights,
            weight_history=weight_history,
            gap_history=gap_history,
        )

    def _update_weights(
        self,
        weights: DriveWeights,
        gaps: GapState,
        rate: float,
    ) -> DriveWeights:
        """模拟一次权重更新"""
        total_gap = gaps.total_gap
        if total_gap <= 0:
            return weights
        gap_w = DriveWeights(
            safe=gaps.safety / total_gap,
            gain=gaps.gain / total_gap,
            eff=gaps.efficiency / total_gap,
        )
        new_w = DriveWeights(
            safe=rate * weights.safe + (1 - rate) * gap_w.safe,
            gain=rate * weights.gain + (1 - rate) * gap_w.gain,
            eff=rate * weights.eff + (1 - rate) * gap_w.eff,
        )
        return self._normalize(new_w)

    def _normalize(self, weights: DriveWeights) -> DriveWeights:
        """归一化权重"""
        total = weights.safe + weights.gain + weights.eff
        return DriveWeights(
            safe=weights.safe / total,
            gain=weights.gain / total,
            eff=weights.eff / total,
        )

    def _check_convergence(
        self,
        old: DriveWeights,
        new: DriveWeights,
    ) -> bool:
        """检查是否收敛"""
        sq_sum = (
            (old.safe - new.safe) ** 2 +
            (old.gain - new.gain) ** 2 +
            (old.eff - new.eff) ** 2
        )
        diff = float(np.sqrt(sq_sum)) if np is not None else math.sqrt(sq_sum)
        return diff < self.tolerance

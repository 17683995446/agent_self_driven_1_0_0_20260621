"""
缺口计算公理化

第一性原理：缺口 = 进化动力，必须满足数学公理
公理：
1. 非负性：Gap >= 0
2. 有界性：Gap <= 1
3. 单调性：奖励越高，缺口越小
4. 连续性：微小奖励变化导致微小缺口变化
5. 理想态：奖励=1时，缺口=0
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class GapAxiomResult:
    """公理验证结果"""
    valid: bool
    violations: list


class GapCalculatorBase(ABC):
    """缺口计算器抽象基类"""

    @abstractmethod
    def compute(self, reward: float) -> float:
        """计算缺口"""
        pass


class SmoothGapCalculator(GapCalculatorBase):
    """
    平滑缺口计算器

    使用平滑函数确保数值稳定性和可微分性
    """

    def __init__(self, epsilon: float = 1e-7) -> None:
        self.epsilon = epsilon

    def compute(self, reward: float) -> float:
        """
        计算缺口

        公式：gap = 1 - reward + epsilon
        确保 gap > 0 且平滑
        """
        clamped = max(0.0, min(1.0, reward))
        return 1.0 - clamped + self.epsilon

    def verify_axioms(self) -> GapAxiomResult:
        """验证缺口计算满足五大公理"""
        violations: list = []
        violations.extend(self._check_non_negativity())
        violations.extend(self._check_boundedness())
        violations.extend(self._check_monotonicity())
        violations.extend(self._check_continuity())
        violations.extend(self._check_ideal_state())
        return GapAxiomResult(valid=len(violations) == 0, violations=violations)

    def _check_non_negativity(self) -> list:
        """验证非负性"""
        for r in [0.0, 0.5, 1.0]:
            if self.compute(r) < 0:
                return ["non_negativity violated"]
        return []

    def _check_boundedness(self) -> list:
        """验证有界性"""
        for r in [0.0, 0.5, 1.0]:
            if self.compute(r) > 1.0 + self.epsilon * 2:
                return ["boundedness violated"]
        return []

    def _check_monotonicity(self) -> list:
        """验证单调性"""
        g1 = self.compute(0.2)
        g2 = self.compute(0.8)
        if g1 <= g2:
            return ["monotonicity violated"]
        return []

    def _check_continuity(self) -> list:
        """验证连续性"""
        g1 = self.compute(0.5)
        g2 = self.compute(0.500001)
        if abs(g1 - g2) > 1e-3:
            return ["continuity violated"]
        return []

    def _check_ideal_state(self) -> list:
        """验证理想态"""
        g = self.compute(1.0)
        if g > self.epsilon * 2:
            return ["ideal_state violated"]
        return []

"""
可微分驱力奖励

第一性原理：奖励函数必须可微分，以便梯度下降优化
类比：生物神经元的激活函数是平滑的（sigmoid），而非阶跃函数
"""

from abc import ABC, abstractmethod
from typing import List, Any

from ....platform.support.models.base.state import EnvironmentState, SystemState

try:
    import numpy as np
except ImportError:
    np = None


class DifferentiableRewardBase(ABC):
    """可微分奖励抽象基类"""

    @abstractmethod
    def compute(self, state_vector: Any) -> float:
        """计算奖励值"""
        pass

    @abstractmethod
    def gradient(self, state_vector: Any) -> Any:
        """计算梯度"""
        pass


class SmoothSafetyReward(DifferentiableRewardBase):
    """
    平滑安全奖励

    使用sigmoid替代阶跃函数，确保可微分
    """

    def __init__(self, steepness: float = 10.0) -> None:
        self.steepness = steepness

    def compute(self, state_vector: Any) -> float:
        """计算平滑安全奖励"""
        import math
        cpu = state_vector[0]
        memory = state_vector[1]
        penalty = 0.5 * cpu + 0.5 * memory
        if np is not None:
            return float(1.0 / (1.0 + np.exp(self.steepness * (penalty - 0.5))))
        return float(1.0 / (1.0 + math.exp(self.steepness * (penalty - 0.5))))

    def gradient(self, state_vector: Any) -> Any:
        """数值微分计算梯度"""
        return self._numerical_gradient(state_vector)

    def _numerical_gradient(self, state_vector: Any) -> Any:
        eps = 1e-7
        if np is not None:
            grad = np.zeros_like(state_vector)
            base = self.compute(state_vector)
            for i in range(len(state_vector)):
                perturbed = state_vector.copy()
                perturbed[i] += eps
                grad[i] = (self.compute(perturbed) - base) / eps
            return grad
        # 纯Python降级
        grad = [0.0] * len(state_vector)
        base = self.compute(state_vector)
        for i in range(len(state_vector)):
            perturbed = list(state_vector)
            perturbed[i] += eps
            grad[i] = (self.compute(perturbed) - base) / eps
        return grad


class SmoothEfficiencyReward(DifferentiableRewardBase):
    """平滑能效奖励"""

    def compute(self, state_vector: Any) -> float:
        """计算平滑能效奖励"""
        import math
        agent_cpu = state_vector[13] if len(state_vector) > 13 else 0.0
        agent_mem = state_vector[14] if len(state_vector) > 14 else 0.0
        penalty = 0.5 * agent_cpu + 0.5 * agent_mem
        if np is not None:
            return float(np.exp(-penalty))
        return float(math.exp(-penalty))

    def gradient(self, state_vector: Any) -> Any:
        """数值微分计算梯度"""
        return self._numerical_gradient(state_vector)

    def _numerical_gradient(self, state_vector: Any) -> Any:
        eps = 1e-7
        if np is not None:
            grad = np.zeros_like(state_vector)
            base = self.compute(state_vector)
            for i in range(len(state_vector)):
                perturbed = state_vector.copy()
                perturbed[i] += eps
                grad[i] = (self.compute(perturbed) - base) / eps
            return grad
        grad = [0.0] * len(state_vector)
        base = self.compute(state_vector)
        for i in range(len(state_vector)):
            perturbed = list(state_vector)
            perturbed[i] += eps
            grad[i] = (self.compute(perturbed) - base) / eps
        return grad

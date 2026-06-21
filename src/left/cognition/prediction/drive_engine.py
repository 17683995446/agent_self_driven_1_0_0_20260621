"""
驱力引擎模块

第一性原理：所有动机必须内生，不能外源
类比：生物大脑的"边缘系统"——产生情绪、动机、驱力
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Tuple

from ....platform.support.models.base.state import (
    EnvironmentState, DriveRewards, DriveWeights,
    GapState, DriveType
)


logger = logging.getLogger(__name__)


class DriveEngineBase(ABC):
    """驱力引擎抽象基类"""

    @abstractmethod
    def compute_drive_rewards(self, state: EnvironmentState) -> DriveRewards:
        """计算驱力奖励值"""
        pass

    @abstractmethod
    def compute_gaps(self, rewards: DriveRewards) -> GapState:
        """计算价值缺口"""
        pass

    @abstractmethod
    def compute_weights(self, state: EnvironmentState, gaps: GapState) -> DriveWeights:
        """动态调整驱力权重"""
        pass


class DriveEngineModule(DriveEngineBase):
    """
    驱力引擎模块

    系统的"动机系统"，负责：
    1. 计算三大原生驱力的奖励值
    2. 动态调整驱力权重
    3. 计算价值缺口
    4. 生成全局总奖励信号

    第一性原理：
    - 所有动机必须内生，不能外源
    - 驱力计算必须实时、连续
    - 权重调整必须自适应环境
    - 缺口计算必须可量化

    数学保证：
    - 奖励函数有界：[0, 1]
    - 权重和为1：W_safe + W_gain + W_eff = 1
    - 缺口永不为零：Gap > 0
    """

    def _init_cache(self, base_weights: DriveWeights) -> None:
        self.current_weights = base_weights
        self.last_rewards: DriveRewards = DriveRewards()
        self.last_gaps: GapState = GapState()
        self.weight_history: List[Tuple[float, DriveWeights]] = []

    def __init__(
        self,
        base_weights: DriveWeights = None,
        adaptation_rate: float = 0.3
    ) -> None:
        self.base_weights = base_weights or DriveWeights()
        self.adaptation_rate = adaptation_rate
        self._init_cache(self.base_weights)
        logger.info(f"Drive engine initialized with weights: {self.base_weights.to_dict()}")

    def _build_rewards(self, safety: float, gain: float, efficiency: float) -> DriveRewards:
        """构建奖励对象并缓存"""
        rewards = DriveRewards(safety=safety, gain=gain, efficiency=efficiency)
        self.last_rewards = rewards
        return rewards

    def compute_drive_rewards(self, state: EnvironmentState) -> DriveRewards:
        """
        计算三大驱力奖励值

        第一性原理：驱力是系统内部状态到实数的映射，表示"满意程度"
        """
        safety_reward = self._compute_safety_reward(state)
        gain_reward = self._compute_gain_reward(state)
        efficiency_reward = self._compute_efficiency_reward(state)
        return self._build_rewards(safety_reward, gain_reward, efficiency_reward)

    def _compute_penalties(self, state: EnvironmentState) -> float:
        """计算安全驱力惩罚项"""
        return (
            0.3 * state.system.cpu_overall +
            0.3 * state.system.memory_pressure +
            0.2 * state.system.disk_usage +
            0.1 * state.logs.error_rate +
            0.1 * state.system.zombie_ratio
        )

    def _compute_safety_reward(self, state: EnvironmentState) -> float:
        """
        计算安全驱力奖励

        逻辑：异常越多、未知越多 → 安全收益越低
        """
        penalties = self._compute_penalties(state)
        reward = max(0.0, 1.0 - penalties)
        return reward

    def _compute_gain_reward(self, state: EnvironmentState) -> float:
        """
        计算收益驱力奖励

        MVP简化：使用预测误差作为代理指标
        """
        prediction_error = state.self.prediction_error
        base_gain = 0.3
        error_contribution = prediction_error * 0.5
        exploration_bonus = 0.2
        reward = min(1.0, base_gain + error_contribution + exploration_bonus)
        return reward

    def _compute_efficiency_reward(self, state: EnvironmentState) -> float:
        """
        计算能效驱力奖励

        逻辑：资源消耗越高 → 能效收益越低
        """
        agent_cpu = state.self.agent_cpu
        agent_memory = state.self.agent_memory
        efficiency = 1.0 - (agent_cpu * 0.5 + agent_memory * 0.5)
        return max(0.0, efficiency)

    def _resolve_rewards(self, rewards: DriveRewards = None) -> DriveRewards:
        """解析使用的奖励对象"""
        return rewards if rewards is not None else self.last_rewards

    def _compute_single_gap(self, reward: float) -> float:
        """计算单个缺口值"""
        return max(0.01, 1.0 - reward)

    def _build_gaps(self, safety: float, gain: float, efficiency: float) -> GapState:
        """构建缺口对象并缓存"""
        gaps = GapState(safety=safety, gain=gain, efficiency=efficiency)
        self.last_gaps = gaps
        return gaps

    def compute_gaps(self, rewards: DriveRewards = None) -> GapState:
        """
        计算价值缺口

        第一性原理：缺口 = 进化动力
        """
        rewards = self._resolve_rewards(rewards)
        safety_gap = self._compute_single_gap(rewards.safety)
        gain_gap = self._compute_single_gap(rewards.gain)
        efficiency_gap = self._compute_single_gap(rewards.efficiency)
        return self._build_gaps(safety_gap, gain_gap, efficiency_gap)

    def _build_gap_weights(self, gaps: GapState, total_gap: float) -> DriveWeights:
        return DriveWeights(
            safe=gaps.safety / total_gap,
            gain=gaps.gain / total_gap,
            eff=gaps.efficiency / total_gap
        )

    def _compute_gap_weights(self, gaps: GapState) -> DriveWeights:
        """基于缺口计算权重"""
        total_gap = gaps.total_gap
        if total_gap > 0:
            return self._build_gap_weights(gaps, total_gap)
        return DriveWeights(1 / 3, 1 / 3, 1 / 3)

    def _mix_weights(self, base: DriveWeights, gap_weights: DriveWeights) -> DriveWeights:
        """混合基础权重和缺口权重"""
        rate = self.adaptation_rate
        return DriveWeights(
            safe=rate * base.safe + (1 - rate) * gap_weights.safe,
            gain=rate * base.gain + (1 - rate) * gap_weights.gain,
            eff=rate * base.eff + (1 - rate) * gap_weights.eff
        )

    def _normalize_weights(self, weights: DriveWeights) -> DriveWeights:
        """归一化权重"""
        total = weights.safe + weights.gain + weights.eff
        return DriveWeights(
            safe=weights.safe / total,
            gain=weights.gain / total,
            eff=weights.eff / total
        )

    def _resolve_gaps(self, gaps: GapState = None) -> GapState:
        """解析使用的缺口对象"""
        return gaps if gaps is not None else self.last_gaps

    def _finalize_weights(self, weights: DriveWeights) -> DriveWeights:
        """归一化并记录权重"""
        normalized = self._normalize_weights(weights)
        self.current_weights = normalized
        self._record_weight_history(normalized)
        return normalized

    def compute_weights(
        self,
        state: EnvironmentState,
        gaps: GapState = None
    ) -> DriveWeights:
        """
        动态调整驱力权重

        第一性原理：权重必须自适应环境
        """
        gaps = self._resolve_gaps(gaps)
        gap_weights = self._compute_gap_weights(gaps)
        new_weights = self._mix_weights(self.base_weights, gap_weights)
        new_weights = self._apply_emergency_override(new_weights, gaps, state)
        return self._finalize_weights(new_weights)

    def _record_weight_history(self, weights: DriveWeights) -> None:
        """记录权重历史"""
        self.weight_history.append((time.time(), weights))
        if len(self.weight_history) > 1000:
            self.weight_history = self.weight_history[-1000:]

    def _safety_override(self) -> DriveWeights:
        """安全优先覆盖"""
        logger.warning("Emergency override: Safety priority!")
        return DriveWeights(safe=0.7, gain=0.2, eff=0.1)

    def _efficiency_override(self) -> DriveWeights:
        """效率优先覆盖"""
        logger.warning("Emergency override: Efficiency priority!")
        return DriveWeights(safe=0.2, gain=0.1, eff=0.7)

    def _apply_emergency_override(
        self,
        weights: DriveWeights,
        gaps: GapState,
        state: EnvironmentState
    ) -> DriveWeights:
        """
        紧急场景权重覆盖

        第一性原理：安全优先（生命优先）
        """
        if gaps.safety > 0.7 or state.system.cpu_overall > 0.9:
            return self._safety_override()
        if state.system.memory_pressure > 0.9:
            return self._efficiency_override()
        return weights

    def compute_global_reward(
        self,
        rewards: DriveRewards = None,
        weights: DriveWeights = None
    ) -> float:
        """
        计算全局总奖励

        公式：R_global = W_safe * R_safe + W_gain * R_gain + W_eff * R_eff
        """
        if rewards is None:
            rewards = self.last_rewards
        if weights is None:
            weights = self.current_weights
        return rewards.weighted_sum(weights)

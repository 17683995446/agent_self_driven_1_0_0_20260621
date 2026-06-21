"""
自适应探索-利用平衡模块

第一性原理：探索与利用的平衡是智能系统的核心权衡
- 稳态时增加探索：寻找更优解
- 动荡时减少探索：保守利用已知解
- 基于反馈动态调整：成功→维持，失败→调整
- 多时间尺度：短期波动不干扰长期策略

类比：生物的"觅食策略"——资源丰富时尝试新食物，资源匮乏时依赖已知食物
"""

import random
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque


logger = logging.getLogger(__name__)


@dataclass
class ExplorationState:
    """探索状态记录"""
    ratio: float = 0.3
    success_count: int = 0
    failure_count: int = 0
    exploitation_success: int = 0
    exploitation_failure: int = 0
    last_adjustment: float = field(default_factory=time.time)
    adjustment_count: int = 0

    @property
    def total_explorations(self) -> int:
        return self.success_count + self.failure_count

    @property
    def total_exploitations(self) -> int:
        return self.exploitation_success + self.exploitation_failure

    @property
    def exploration_success_rate(self) -> float:
        if self.total_explorations == 0:
            return 0.5
        return self.success_count / self.total_explorations

    @property
    def exploitation_success_rate(self) -> float:
        if self.total_exploitations == 0:
            return 0.5
        return self.exploitation_success / self.total_exploitations

    @property
    def overall_success_rate(self) -> float:
        total = self.total_explorations + self.total_exploitations
        if total == 0:
            return 0.5
        return (self.success_count + self.exploitation_success) / total


class ExplorationBalancerBase(ABC):
    """探索平衡器抽象基类"""

    @abstractmethod
    def should_explore(self) -> bool:
        """决定是否探索"""
        pass

    @abstractmethod
    def adjust(self, force: bool = False) -> float:
        """调整探索比例"""
        pass


class AdaptiveExplorationBalancer(ExplorationBalancerBase):
    """
    自适应探索-利用平衡器

    第一性原理：探索比例必须根据系统状态动态调整
    """

    def _init_histories(self, window_size: int, stagnation_threshold: int) -> None:
        self._error_history: deque = deque(maxlen=window_size)
        self._reward_history: deque = deque(maxlen=max(window_size, stagnation_threshold * 2))
        self._min_adjustment_interval = 5.0

    def _init_state(self, base_ratio: float) -> None:
        self.state = ExplorationState(ratio=base_ratio)

    def _init_bounds(self, min_ratio: float, max_ratio: float) -> None:
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio

    def _init_params(self, base_ratio: float, min_ratio: float, max_ratio: float, adaptation_rate: float, stagnation_threshold: int, window_size: int) -> None:
        self.base_ratio = base_ratio
        self.adaptation_rate = adaptation_rate
        self.stagnation_threshold = stagnation_threshold
        self.window_size = window_size
        self._init_bounds(min_ratio, max_ratio)
        self._init_state(base_ratio)
        self._init_histories(window_size, stagnation_threshold)

    def __init__(
        self,
        base_ratio: float = 0.3,
        min_ratio: float = 0.05,
        max_ratio: float = 0.7,
        adaptation_rate: float = 0.05,
        stagnation_threshold: int = 50,
        window_size: int = 20,
    ) -> None:
        self._init_params(base_ratio, min_ratio, max_ratio, adaptation_rate, stagnation_threshold, window_size)

    def should_explore(self) -> bool:
        return random.random() < self.state.ratio

    def record_exploration_result(self, success: bool, reward: float = 0.0) -> None:
        if success:
            self.state.success_count += 1
        else:
            self.state.failure_count += 1
        self._reward_history.append(reward)

    def record_exploitation_result(self, success: bool, reward: float = 0.0) -> None:
        if success:
            self.state.exploitation_success += 1
        else:
            self.state.exploitation_failure += 1
        self._reward_history.append(reward)

    def update_error(self, error: float) -> None:
        self._error_history.append(error)

    def _check_cooldown(self, force: bool) -> bool:
        if force:
            return True
        elapsed = time.time() - self.state.last_adjustment
        return elapsed >= self._min_adjustment_interval

    def _compute_error_trend(self) -> float:
        if len(self._error_history) < 5:
            return 0.0
        recent = list(self._error_history)
        half = len(recent) // 2
        first_half = sum(recent[:half]) / half
        second_half = sum(recent[half:]) / (len(recent) - half)
        return second_half - first_half

    def _is_stagnating(self) -> bool:
        if len(self._reward_history) < self.stagnation_threshold:
            return False
        recent = list(self._reward_history)[-self.stagnation_threshold:]
        mean_reward = sum(recent) / len(recent)
        return mean_reward < 0.1

    def _apply_error_adjustment(self, ratio: float, trend: float) -> float:
        if trend > 0.01:
            return ratio - self.adaptation_rate * 1.5
        elif trend < -0.01:
            return ratio + self.adaptation_rate
        return ratio

    def _compute_success_delta(self) -> float:
        exp_rate = self.state.exploration_success_rate
        if exp_rate < 0.2:
            return -self.adaptation_rate * 2.0
        elif exp_rate > 0.6:
            return self.adaptation_rate * 0.5
        return 0.0

    def _apply_success_adjustment(self, ratio: float) -> float:
        if self.state.total_explorations < 10:
            return ratio
        return ratio + self._compute_success_delta()

    def _compute_comparison_delta(self) -> float:
        exp_rate = self.state.exploration_success_rate
        ext_rate = self.state.exploitation_success_rate
        if exp_rate > ext_rate + 0.2:
            return self.adaptation_rate
        elif ext_rate > exp_rate + 0.3:
            return -self.adaptation_rate
        return 0.0

    def _apply_comparison_adjustment(self, ratio: float) -> float:
        if self.state.total_exploitations < 10 or self.state.total_explorations < 10:
            return ratio
        return ratio + self._compute_comparison_delta()

    def _apply_stagnation_adjustment(self, ratio: float) -> float:
        if self._is_stagnating():
            return ratio + self.adaptation_rate * 2.0
        return ratio

    def _clamp_ratio(self, ratio: float) -> float:
        return max(self.min_ratio, min(self.max_ratio, ratio))

    def _apply_all_adjustments(self, ratio: float) -> float:
        """应用所有调整策略"""
        ratio = self._apply_error_adjustment(ratio, self._compute_error_trend())
        ratio = self._apply_success_adjustment(ratio)
        ratio = self._apply_comparison_adjustment(ratio)
        ratio = self._apply_stagnation_adjustment(ratio)
        return self._clamp_ratio(ratio)

    def _commit_ratio_change(self, old_ratio: float, new_ratio: float) -> None:
        """提交比例变更"""
        if abs(new_ratio - old_ratio) > 0.001:
            self.state.ratio = new_ratio
            self.state.last_adjustment = time.time()
            self.state.adjustment_count += 1
            logger.info(f"Exploration ratio adjusted: {old_ratio:.3f} -> {new_ratio:.3f}")

    def adjust(self, force: bool = False) -> float:
        if not self._check_cooldown(force):
            return self.state.ratio

        old_ratio = self.state.ratio
        new_ratio = self._apply_all_adjustments(old_ratio)
        self._commit_ratio_change(old_ratio, new_ratio)
        return self.state.ratio

    def _build_rates_dict(self) -> Dict:
        return {
            "success_rate": self.state.overall_success_rate,
            "exploration_success_rate": self.state.exploration_success_rate,
            "exploitation_success_rate": self.state.exploitation_success_rate,
        }

    def _build_counts_dict(self) -> Dict:
        return {
            "total_explorations": self.state.total_explorations,
            "total_exploitations": self.state.total_exploitations,
            "adjustment_count": self.state.adjustment_count,
        }

    def _build_state_dict(self) -> Dict:
        return {
            "ratio": self.state.ratio,
            **self._build_rates_dict(),
            **self._build_counts_dict(),
            "error_trend": self._compute_error_trend(),
        }

    def get_state(self) -> Dict:
        return self._build_state_dict()

    def reset(self) -> None:
        self.state = ExplorationState(ratio=self.base_ratio)
        self._error_history.clear()
        self._reward_history.clear()


class MultiArmedBanditExplorer:
    """
    多臂老虎机探索器

    使用UCB1算法：Upper Confidence Bound
    """

    def __init__(self, exploration_constant: float = 1.414) -> None:
        self.exploration_constant = exploration_constant
        self._counts: Dict[str, int] = {}
        self._values: Dict[str, float] = {}
        self._total_pulls = 0

    def register_arm(self, arm_id: str) -> None:
        if arm_id not in self._counts:
            self._counts[arm_id] = 0
            self._values[arm_id] = 0.0

    def _find_untried_arm(self) -> Optional[str]:
        for arm_id, count in self._counts.items():
            if count == 0:
                return arm_id
        return None

    def _compute_ucb(self, arm_id: str) -> float:
        import math
        count = self._counts[arm_id]
        value = self._values[arm_id]
        return value + self.exploration_constant * math.sqrt(
            math.log(self._total_pulls) / count
        )

    def _update_best_ucb(self, arm_id: str, best_value: float, best_arm: Optional[str]) -> Tuple[float, Optional[str]]:
        ucb = self._compute_ucb(arm_id)
        if ucb > best_value:
            return ucb, arm_id
        return best_value, best_arm

    def _find_best_ucb_arm(self) -> str:
        """查找UCB值最高的臂"""
        best_arm = None
        best_value = float("-inf")
        for arm_id in self._counts:
            best_value, best_arm = self._update_best_ucb(arm_id, best_value, best_arm)
        return best_arm

    def select_arm(self) -> Optional[str]:
        if not self._counts:
            return None
        untried = self._find_untried_arm()
        if untried:
            return untried
        return self._find_best_ucb_arm()

    def update(self, arm_id: str, reward: float) -> None:
        if arm_id not in self._counts:
            self.register_arm(arm_id)
        self._counts[arm_id] += 1
        self._total_pulls += 1
        n = self._counts[arm_id]
        old_value = self._values[arm_id]
        self._values[arm_id] = ((n - 1) / n) * old_value + (1 / n) * reward

    def get_arm_stats(self) -> Dict[str, Dict]:
        return {
            arm_id: {
                "count": self._counts[arm_id],
                "average_reward": self._values[arm_id],
            }
            for arm_id in self._counts
        }

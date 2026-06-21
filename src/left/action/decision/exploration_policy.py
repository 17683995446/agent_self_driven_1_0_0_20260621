"""
探索-利用决策策略

第一性原理：探索与利用的平衡是智能系统的核心权衡
基于UCB (Upper Confidence Bound) 理论，保证渐进最优
"""

import math
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from ....platform.support.models.base.task import Task, TaskPool
from ....platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class ExplorationPolicy(ABC):
    """探索-利用策略抽象基类"""

    @abstractmethod
    def select_task(
        self,
        scored_tasks: List[Tuple[float, Task]],
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """从已评分的任务中选择下一个任务"""
        pass


class UCBExplorationPolicy(ExplorationPolicy):
    """
    UCB探索-利用策略

    基于多臂老虎机理论，使用UCB1算法
    平衡探索（尝试次数少的任务）和利用（平均分高的任务）
    """

    def __init__(self, exploration_constant: float = 1.414) -> None:
        self.exploration_constant = exploration_constant
        self._counts: Dict[str, int] = {}
        self._values: Dict[str, float] = {}
        self._total_pulls: int = 0

    def select_task(
        self,
        scored_tasks: List[Tuple[float, Task]],
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """使用UCB策略选择任务"""
        if not scored_tasks:
            return None
        untried = self._find_untried_task(scored_tasks)
        if untried:
            self._record_pull(untried.id)
            return untried
        best = self._find_best_ucb_task(scored_tasks)
        if best:
            self._record_pull(best.id)
        return best

    def _find_untried_task(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        """查找未尝试过的任务"""
        for _, task in scored_tasks:
            if self._counts.get(task.id, 0) == 0:
                return task
        return None

    def _compute_ucb(self, task_id: str, base_score: float) -> float:
        """计算UCB值"""
        count = self._counts.get(task_id, 0)
        if count == 0:
            return float("inf")
        value = self._values.get(task_id, 0.0)
        return value + self.exploration_constant * math.sqrt(
            math.log(self._total_pulls) / count
        )

    def _find_best_ucb_task(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        """查找UCB值最高的任务"""
        best_task = None
        best_value = float("-inf")
        for score, task in scored_tasks:
            ucb = self._compute_ucb(task.id, score)
            if ucb > best_value:
                best_value = ucb
                best_task = task
        return best_task

    def _record_pull(self, task_id: str) -> None:
        """记录一次选择"""
        self._total_pulls += 1
        if task_id not in self._counts:
            self._counts[task_id] = 0

    def update_reward(self, task_id: str, reward: float) -> None:
        """更新任务的奖励估计"""
        if task_id not in self._counts:
            self._counts[task_id] = 0
        if task_id not in self._values:
            self._values[task_id] = 0.0
        self._counts[task_id] += 1
        n = self._counts[task_id]
        old_value = self._values[task_id]
        self._values[task_id] = ((n - 1) / n) * old_value + (1 / n) * reward

    def get_stats(self) -> Dict[str, Dict]:
        """获取统计信息"""
        return {
            task_id: {
                "count": self._counts[task_id],
                "average_reward": self._values[task_id],
            }
            for task_id in self._counts
        }


class EpsilonGreedyPolicy(ExplorationPolicy):
    """
    Epsilon-贪婪策略

    以epsilon概率随机探索，以1-epsilon概率选择最优
    """

    def __init__(self, epsilon: float = 0.3, min_epsilon: float = 0.05) -> None:
        self.epsilon = epsilon
        self.min_epsilon = min_epsilon
        self._exploration_count: int = 0
        self._exploitation_count: int = 0

    def select_task(
        self,
        scored_tasks: List[Tuple[float, Task]],
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """使用epsilon-贪婪策略选择任务"""
        if not scored_tasks:
            return None
        if random.random() < self.epsilon:
            self._exploration_count += 1
            return self._explore(scored_tasks)
        self._exploitation_count += 1
        return self._exploit(scored_tasks)

    def _explore(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        """随机探索"""
        candidates = scored_tasks[-3:] if len(scored_tasks) >= 3 else scored_tasks
        if candidates:
            selected = random.choice(candidates)[1]
            selected.is_exploration = True
            return selected
        return None

    def _exploit(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        """贪婪利用"""
        return scored_tasks[0][1] if scored_tasks else None

    def decay_epsilon(self, decay_rate: float = 0.99) -> None:
        """衰减epsilon值"""
        self.epsilon = max(self.min_epsilon, self.epsilon * decay_rate)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "exploration_count": self._exploration_count,
            "exploitation_count": self._exploitation_count,
            "current_epsilon": self.epsilon,
        }


class SoftmaxExplorationPolicy(ExplorationPolicy):
    """
    Softmax探索策略

    第一性原理：基于概率分布的探索，避免UCB的确定性偏差
    温度参数控制探索程度：高温=更多探索，低温=更多利用
    """

    def __init__(self, temperature: float = 1.0) -> None:
        self.temperature = temperature

    def select_task(
        self,
        scored_tasks: List[Tuple[float, Task]],
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """使用Softmax策略选择任务"""
        if not scored_tasks:
            return None
        probs = self._compute_probabilities(scored_tasks)
        selected = self._sample_task(scored_tasks, probs)
        return selected

    def _compute_probabilities(self, scored_tasks: List[Tuple[float, Task]]) -> List[float]:
        """计算Softmax概率分布"""
        scores = [s for s, _ in scored_tasks]
        exp_scores = [math.exp(s / self.temperature) for s in scores]
        total = sum(exp_scores)
        return [e / total for e in exp_scores]

    def _sample_task(self, scored_tasks: List[Tuple[float, Task]], probs: List[float]) -> Optional[Task]:
        """按概率采样任务"""
        r = random.random()
        cumulative = 0.0
        for i, prob in enumerate(probs):
            cumulative += prob
            if r <= cumulative:
                return scored_tasks[i][1]
        return scored_tasks[-1][1] if scored_tasks else None

    def get_stats(self) -> Dict[str, float]:
        """获取统计信息"""
        return {"temperature": self.temperature}


class ThompsonSamplingPolicy(ExplorationPolicy):
    """
    Thompson采样策略

    第一性原理：贝叶斯方法，从后验分布采样，自然平衡探索与利用
    使用Beta分布作为共轭先验
    """

    def __init__(self) -> None:
        self._alpha: Dict[str, float] = {}
        self._beta: Dict[str, float] = {}

    def select_task(
        self,
        scored_tasks: List[Tuple[float, Task]],
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """使用Thompson采样选择任务"""
        if not scored_tasks:
            return None
        best_task = None
        best_sample = float("-inf")
        for _, task in scored_tasks:
            sample = self._sample_posterior(task.id)
            if sample > best_sample:
                best_sample = sample
                best_task = task
        return best_task

    def _sample_posterior(self, task_id: str) -> float:
        """从Beta后验分布采样"""
        import random
        a = self._alpha.get(task_id, 1.0)
        b = self._beta.get(task_id, 1.0)
        return random.betavariate(a, b)

    def update_reward(self, task_id: str, reward: float) -> None:
        """更新Beta分布参数"""
        if task_id not in self._alpha:
            self._alpha[task_id] = 1.0
            self._beta[task_id] = 1.0
        if reward > 0.5:
            self._alpha[task_id] += 1.0
        else:
            self._beta[task_id] += 1.0

    def get_stats(self) -> Dict[str, Dict]:
        """获取统计信息"""
        return {
            task_id: {"alpha": self._alpha[task_id], "beta": self._beta[task_id]}
            for task_id in self._alpha
        }

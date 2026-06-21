"""
任务评分函数精确化

第一性原理：任务评分是多目标优化问题，必须透明、可解释、可配置
Score = w1 * GapMatch + w2 * Urgency + w3 * SuccessRate + w4 * Novelty - w5 * Cost + w6 * ExpiredBonus
"""

from abc import ABC, abstractmethod
from typing import Dict

from ....platform.support.models.base.task import Task, TaskPriority
from ....platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class TaskScorer(ABC):
    """任务评分器抽象基类"""

    @abstractmethod
    def score(self, task: Task, gaps: GapState, weights: DriveWeights, state: EnvironmentState) -> float:
        """计算任务得分，返回 [0.0, 1.0]"""
        pass


class StandardTaskScorer(TaskScorer):
    """
    标准任务评分器

    基于多目标优化的任务评分，权重固定但可配置
    """

    WEIGHT_GAP_MATCH: float = 0.25
    WEIGHT_URGENCY: float = 0.20
    WEIGHT_SUCCESS_RATE: float = 0.20
    WEIGHT_NOVELTY: float = 0.15
    WEIGHT_COST: float = 0.10
    WEIGHT_EXPIRED: float = 0.10

    def score(self, task: Task, gaps: GapState, weights: DriveWeights, state: EnvironmentState) -> float:
        """计算任务得分"""
        components = self._score_components(task, gaps)
        raw = self._compute_raw_score(*components)
        return self._clamp_score(raw)

    def _score_components(self, task: Task, gaps: GapState) -> tuple:
        """提取评分组件"""
        return (
            self._compute_gap_match(task, gaps),
            self._compute_urgency(task),
            self._compute_success_rate(task),
            self._compute_novelty(task),
            self._compute_cost(task),
            self._compute_expired_bonus(task),
        )

    def _compute_gap_match(self, task: Task, gaps: GapState) -> float:
        """计算缺口匹配度"""
        if task.target_drive == "safe":
            return gaps.safety
        elif task.target_drive == "gain":
            return gaps.gain
        elif task.target_drive == "eff":
            return gaps.efficiency
        return 0.0

    def _compute_urgency(self, task: Task) -> float:
        """计算紧急程度"""
        return 1.0 - (task.priority.value / 4.0)

    def _compute_success_rate(self, task: Task) -> float:
        """计算历史成功率"""
        if task.execution_count == 0:
            return 0.5
        return task.success_count / task.execution_count

    def _compute_novelty(self, task: Task) -> float:
        """计算新颖性"""
        return 0.3 if task.is_exploration else 0.0

    def _compute_cost(self, task: Task) -> float:
        """计算资源成本"""
        return (task.max_cpu_usage + task.max_memory_usage) / 2.0

    def _compute_expired_bonus(self, task: Task) -> float:
        """计算过期奖励"""
        return 1.0 if task.is_expired else 0.0

    def _compute_raw_score(
        self,
        gap_match: float,
        urgency: float,
        success_rate: float,
        novelty: float,
        cost: float,
        expired_bonus: float,
    ) -> float:
        """计算原始分数"""
        return (
            self.WEIGHT_GAP_MATCH * gap_match +
            self.WEIGHT_URGENCY * urgency +
            self.WEIGHT_SUCCESS_RATE * success_rate +
            self.WEIGHT_NOVELTY * novelty -
            self.WEIGHT_COST * cost +
            self.WEIGHT_EXPIRED * expired_bonus
        )

    def _clamp_score(self, score: float) -> float:
        """将分数限制在 [0.0, 1.0]"""
        return max(0.0, min(1.0, score))

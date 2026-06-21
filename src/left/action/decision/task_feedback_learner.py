"""
任务结果反馈学习器

第一性原理：智能系统必须从结果中学习——成功的行为应被强化，失败的行为应被抑制
- 记录：每种任务的历史执行结果
- 评估：计算成功率、平均奖励、连续失败次数
- 调整：成功率低的任务降级，成功率高的任务提升
- 保护：连续失败的任务暂停，避免空转

类比：生物的"操作性条件反射"——基于行为结果调整未来行为概率

核心机制：
1. 成功率<30% → 任务降级（优先级降低）
2. 成功率>80% → 任务提升（优先级升高）
3. 连续失败3次 → 任务暂停
4. 暂停后冷却期结束 → 任务恢复
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.task import Task, TaskResult, TaskPriority


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务学习状态"""
    ACTIVE = "active"
    DEGRADED = "degraded"
    PROMOTED = "promoted"
    SUSPENDED = "suspended"
    COOLDOWN = "cooldown"


@dataclass
class TaskHistoryEntry:
    """任务历史条目"""
    task_name: str
    success: bool
    reward: float
    timestamp: float
    execution_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "success": self.success,
            "reward": round(self.reward, 4),
            "timestamp": self.timestamp,
            "execution_time": round(self.execution_time, 4),
        }


@dataclass
class TaskStatistics:
    """任务统计"""
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    success_rate: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_execution: float = 0.0
    status: TaskStatus = TaskStatus.ACTIVE
    priority_multiplier: float = 1.0
    suspension_count: int = 0

    @property
    def failure_rate(self) -> float:
        """失败率"""
        if self.total_executions == 0:
            return 0.0
        return self.failure_count / self.total_executions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_reward": round(self.total_reward, 4),
            "avg_reward": round(self.avg_reward, 4),
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_execution": self.last_execution,
            "status": self.status.value,
            "priority_multiplier": round(self.priority_multiplier, 4),
            "suspension_count": self.suspension_count,
        }


class FeedbackPolicy(ABC):
    """反馈策略抽象基类"""

    @abstractmethod
    def evaluate(
        self, stats: TaskStatistics, current_time: float,
    ) -> Tuple[TaskStatus, float]:
        """评估任务状态和优先级倍率"""
        pass


class DefaultFeedbackPolicy(FeedbackPolicy):
    """默认反馈策略"""

    DEGRADE_THRESHOLD: float = 0.30
    PROMOTE_THRESHOLD: float = 0.80
    SUSPEND_FAILURES: int = 3
    COOLDOWN_SECONDS: float = 60.0
    MIN_MULTIPLIER: float = 0.1
    MAX_MULTIPLIER: float = 2.0
    MIN_SAMPLES: int = 3

    def evaluate(
        self, stats: TaskStatistics, current_time: float,
    ) -> Tuple[TaskStatus, float]:
        """评估任务状态"""
        if self._is_in_cooldown(stats, current_time):
            return TaskStatus.COOLDOWN, 0.0
        if self._should_suspend(stats):
            return TaskStatus.SUSPENDED, 0.0
        return self._evaluate_performance(stats)

    def _is_in_cooldown(
        self, stats: TaskStatistics, current_time: float,
    ) -> bool:
        """检查是否在冷却期"""
        if stats.status != TaskStatus.COOLDOWN:
            return False
        return (current_time - stats.last_execution) < self.COOLDOWN_SECONDS

    def _should_suspend(self, stats: TaskStatistics) -> bool:
        """检查是否应暂停"""
        return stats.consecutive_failures >= self.SUSPEND_FAILURES

    def _evaluate_performance(
        self, stats: TaskStatistics,
    ) -> Tuple[TaskStatus, float]:
        """评估性能"""
        if stats.total_executions < self.MIN_SAMPLES:
            return TaskStatus.ACTIVE, 1.0
        if stats.success_rate < self.DEGRADE_THRESHOLD:
            return self._degrade(stats)
        if stats.success_rate > self.PROMOTE_THRESHOLD:
            return self._promote(stats)
        return TaskStatus.ACTIVE, 1.0

    def _degrade(self, stats: TaskStatistics) -> Tuple[TaskStatus, float]:
        """降级"""
        multiplier = max(self.MIN_MULTIPLIER, stats.success_rate)
        return TaskStatus.DEGRADED, multiplier

    def _promote(self, stats: TaskStatistics) -> Tuple[TaskStatus, float]:
        """提升"""
        multiplier = min(self.MAX_MULTIPLIER, 1.0 + stats.success_rate)
        return TaskStatus.PROMOTED, multiplier


class TaskFeedbackLearner:
    """
    任务结果反馈学习器

    第一性原理：从执行结果中学习，调整未来任务优先级
    - 记录每次任务执行结果
    - 计算成功率、连续失败数
    - 根据策略调整任务状态和优先级倍率
    - 暂停失败任务，冷却后恢复
    """

    HISTORY_LIMIT: int = 200

    def __init__(
        self,
        policy: Optional[FeedbackPolicy] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._policy = policy or DefaultFeedbackPolicy()
        self._clock = clock or time.time
        self._stats: Dict[str, TaskStatistics] = {}
        self._history: List[TaskHistoryEntry] = []

    def record_result(
        self,
        task_name: str,
        result: TaskResult,
        execution_time: float = 0.0,
    ) -> TaskStatistics:
        """记录任务执行结果"""
        current_time = self._clock()
        reward = self._extract_reward(result)
        entry = TaskHistoryEntry(
            task_name=task_name,
            success=result.success,
            reward=reward,
            timestamp=current_time,
            execution_time=execution_time,
        )
        self._history.append(entry)
        self._trim_history()
        stats = self._get_or_create_stats(task_name)
        self._update_stats(stats, entry, current_time)
        self._apply_policy(stats, current_time)
        return stats

    def _extract_reward(self, result: TaskResult) -> float:
        """提取奖励值"""
        if not result.success:
            return 0.0
        data = result.data if isinstance(result.data, dict) else {}
        return float(data.get("reward", 1.0))

    def _trim_history(self) -> None:
        """裁剪历史"""
        if len(self._history) > self.HISTORY_LIMIT:
            self._history = self._history[-self.HISTORY_LIMIT:]

    def _get_or_create_stats(self, task_name: str) -> TaskStatistics:
        """获取或创建统计"""
        if task_name not in self._stats:
            self._stats[task_name] = TaskStatistics()
        return self._stats[task_name]

    def _update_stats(
        self,
        stats: TaskStatistics,
        entry: TaskHistoryEntry,
        current_time: float,
    ) -> None:
        """更新统计"""
        stats.total_executions += 1
        stats.last_execution = current_time
        self._update_success_failure(stats, entry)
        stats.total_reward += entry.reward
        stats.avg_reward = stats.total_reward / stats.total_executions
        stats.success_rate = stats.success_count / stats.total_executions

    def _update_success_failure(
        self,
        stats: TaskStatistics,
        entry: TaskHistoryEntry,
    ) -> None:
        """更新成功失败计数"""
        if entry.success:
            stats.success_count += 1
            stats.consecutive_failures = 0
            stats.consecutive_successes += 1
        else:
            stats.failure_count += 1
            stats.consecutive_successes = 0
            stats.consecutive_failures += 1

    def _apply_policy(
        self,
        stats: TaskStatistics,
        current_time: float,
    ) -> None:
        """应用反馈策略"""
        prev_status = stats.status
        new_status, multiplier = self._policy.evaluate(stats, current_time)
        stats.status = new_status
        stats.priority_multiplier = multiplier
        if prev_status != TaskStatus.SUSPENDED and new_status == TaskStatus.SUSPENDED:
            stats.suspension_count += 1

    def get_statistics(self, task_name: str) -> Optional[TaskStatistics]:
        """获取任务统计"""
        return self._stats.get(task_name)

    def get_all_statistics(self) -> Dict[str, TaskStatistics]:
        """获取所有任务统计"""
        return dict(self._stats)

    def is_task_available(self, task_name: str) -> bool:
        """检查任务是否可用（非暂停非冷却）"""
        stats = self._stats.get(task_name)
        if stats is None:
            return True
        return stats.status not in (TaskStatus.SUSPENDED, TaskStatus.COOLDOWN)

    def get_priority_multiplier(self, task_name: str) -> float:
        """获取任务优先级倍率"""
        stats = self._stats.get(task_name)
        if stats is None:
            return 1.0
        return stats.priority_multiplier

    def adjust_task_priority(
        self, task: Task,
    ) -> Task:
        """根据学习结果调整任务优先级"""
        multiplier = self.get_priority_multiplier(task.name)
        if not self.is_task_available(task.name):
            task.priority = TaskPriority.LOW
            return task
        return self._apply_multiplier(task, multiplier)

    def _apply_multiplier(
        self, task: Task, multiplier: float,
    ) -> Task:
        """应用优先级倍率"""
        if multiplier >= 1.5:
            task.priority = TaskPriority.HIGH
        elif multiplier >= 0.8:
            pass
        elif multiplier >= 0.3:
            task.priority = TaskPriority.NORMAL
        else:
            task.priority = TaskPriority.LOW
        return task

    def get_history(
        self, task_name: Optional[str] = None,
    ) -> List[TaskHistoryEntry]:
        """获取历史记录"""
        if task_name is None:
            return list(self._history)
        return [e for e in self._history if e.task_name == task_name]

    def get_summary(self) -> Dict[str, Any]:
        """获取汇总"""
        total = len(self._history)
        successes = sum(1 for e in self._history if e.success)
        return {
            "total_tasks_tracked": len(self._stats),
            "total_executions": total,
            "overall_success_rate": round(successes / max(total, 1), 4),
            "suspended_tasks": [
                name for name, s in self._stats.items()
                if s.status == TaskStatus.SUSPENDED
            ],
            "degraded_tasks": [
                name for name, s in self._stats.items()
                if s.status == TaskStatus.DEGRADED
            ],
            "promoted_tasks": [
                name for name, s in self._stats.items()
                if s.status == TaskStatus.PROMOTED
            ],
        }

    def reset(self) -> None:
        """重置学习器"""
        self._stats.clear()
        self._history.clear()

"""
任务生命周期状态机

第一性原理：任务必须有明确的生命周期，状态转换必须严格可控
状态转换图定义了所有合法的状态迁移路径，任何非法转换必须被拒绝
"""

import time
from abc import ABC
from typing import Dict, List, Optional, Set, Type

from ....platform.support.models.base.task import Task, TaskStatus
from ....platform.support.models.base.error_code import ErrorCode, ValidationError


class InvalidTransitionError(Exception):
    """非法状态转换异常"""

    def __init__(self, from_status: TaskStatus, to_status: TaskStatus) -> None:
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Cannot transition from {from_status.value} to {to_status.value}"
        super().__init__(msg)


class TaskLifecycle(ABC):
    """
    任务生命周期状态机

    严格定义任务的状态转换规则
    """

    TRANSITIONS: Dict[TaskStatus, List[TaskStatus]] = {
        TaskStatus.CREATED: [TaskStatus.PENDING, TaskStatus.CANCELLED],
        TaskStatus.PENDING: [TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.EXPIRED],
        TaskStatus.RUNNING: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.COMPLETED: [],
        TaskStatus.FAILED: [TaskStatus.PENDING],
        TaskStatus.CANCELLED: [],
        TaskStatus.EXPIRED: [],
    }

    TERMINAL_STATES: Set[TaskStatus] = {
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    }

    @classmethod
    def can_transition(cls: Type["TaskLifecycle"], from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """检查状态转换是否合法"""
        allowed = cls.TRANSITIONS.get(from_status, [])
        return to_status in allowed

    @classmethod
    def get_allowed_transitions(cls: Type["TaskLifecycle"], status: TaskStatus) -> List[TaskStatus]:
        """获取从当前状态可转换到的所有状态"""
        return list(cls.TRANSITIONS.get(status, []))

    @classmethod
    def is_terminal(cls: Type["TaskLifecycle"], status: TaskStatus) -> bool:
        """检查是否为终态"""
        return status in cls.TERMINAL_STATES

    @classmethod
    def transition(cls: Type["TaskLifecycle"], task: Task, new_status: TaskStatus) -> Task:
        """执行状态转换"""
        cls._validate_transition(task.status, new_status)
        cls._update_task_status(task, new_status)
        cls._record_timestamp(task, new_status)
        return task

    @classmethod
    def _validate_transition(cls: Type["TaskLifecycle"], from_status: TaskStatus, to_status: TaskStatus) -> None:
        """验证状态转换合法性"""
        if not cls.can_transition(from_status, to_status):
            raise InvalidTransitionError(from_status, to_status)

    @classmethod
    def _update_task_status(cls: Type["TaskLifecycle"], task: Task, new_status: TaskStatus) -> None:
        """更新任务状态"""
        task.status = new_status

    @classmethod
    def _record_timestamp(cls: Type["TaskLifecycle"], task: Task, new_status: TaskStatus) -> None:
        """记录时间戳"""
        if new_status == TaskStatus.RUNNING:
            task.started_at = time.time()
        elif cls.is_terminal(new_status):
            task.completed_at = time.time()

    @classmethod
    def validate_task_status(cls: Type["TaskLifecycle"], status: TaskStatus) -> None:
        """验证任务状态是否有效"""
        if not isinstance(status, TaskStatus):
            raise ValidationError(
                ErrorCode.PARAMETER_TYPE_ERROR,
                "status",
                f"expected TaskStatus, got {type(status).__name__}",
            )

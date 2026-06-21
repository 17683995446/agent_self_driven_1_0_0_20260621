"""
任务中断机制

第一性原理：高优先级任务必须能够中断低优先级任务
安全任务 > 高缺口任务 > 紧急任务
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ....platform.support.models.base.task import Task, TaskPriority
from ....platform.support.models.base.state import GapState


@dataclass
class TaskContext:
    """任务上下文"""
    task: Task
    progress: float = 0.0
    state: Dict = field(default_factory=dict)
    interrupted_at: float = field(default_factory=time.time)


class TaskInterruptHandler:
    """
    任务中断处理器

    处理高优先级任务中断低优先级任务
    """

    SAFETY_GAP_THRESHOLD: float = 0.5
    GAP_RATIO_THRESHOLD: float = 2.0

    def __init__(self) -> None:
        self._interrupt_stack: List[TaskContext] = []
        self._current_task: Optional[Task] = None

    @property
    def current_task(self) -> Optional[Task]:
        """当前任务"""
        return self._current_task

    @property
    def interrupt_count(self) -> int:
        """中断次数"""
        return len(self._interrupt_stack)

    def can_interrupt(self, current_task: Task, new_task: Task, gaps: GapState) -> bool:
        """判断是否允许中断"""
        if self._is_safety_override(current_task, new_task, gaps):
            return True
        if self._is_gap_dominant(current_task, new_task, gaps):
            return True
        if self._is_urgency_override(current_task, new_task):
            return True
        return False

    def _is_safety_override(self, current_task: Task, new_task: Task, gaps: GapState) -> bool:
        """安全任务优先"""
        if new_task.target_drive == "safe" and current_task.target_drive != "safe":
            return gaps.safety > self.SAFETY_GAP_THRESHOLD
        return False

    def _is_gap_dominant(self, current_task: Task, new_task: Task, gaps: GapState) -> bool:
        """缺口比较"""
        current_gap = self._get_gap_for_task(current_task, gaps)
        new_gap = self._get_gap_for_task(new_task, gaps)
        return new_gap > current_gap * self.GAP_RATIO_THRESHOLD

    def _is_urgency_override(self, current_task: Task, new_task: Task) -> bool:
        """紧急程度比较"""
        return self._is_urgent(new_task) and not self._is_urgent(current_task)

    def _get_gap_for_task(self, task: Task, gaps: GapState) -> float:
        """获取任务对应的缺口值"""
        if task.target_drive == "safe":
            return gaps.safety
        elif task.target_drive == "gain":
            return gaps.gain
        elif task.target_drive == "eff":
            return gaps.efficiency
        return 0.0

    def _is_urgent(self, task: Task) -> bool:
        """判断任务是否紧急"""
        return task.priority == TaskPriority.CRITICAL

    def interrupt(self, current_task: Task, new_task: Task) -> TaskContext:
        """执行中断"""
        context = self._save_context(current_task)
        self._interrupt_stack.append(context)
        self._current_task = new_task
        return context

    def _save_context(self, task: Task) -> TaskContext:
        """保存任务上下文"""
        return TaskContext(
            task=task,
            progress=self._get_progress(task),
            state=self._get_state(task),
        )

    def _get_progress(self, task: Task) -> float:
        """获取任务进度"""
        return 0.0

    def _get_state(self, task: Task) -> Dict:
        """获取任务状态"""
        return task.to_dict()

    def resume(self) -> Optional[Task]:
        """恢复被中断的任务"""
        if not self._interrupt_stack:
            return None
        context = self._interrupt_stack.pop()
        self._current_task = context.task
        return context.task

    def get_stack(self) -> List[TaskContext]:
        """获取中断栈"""
        return list(self._interrupt_stack)

    def clear(self) -> None:
        """清空中断栈"""
        self._interrupt_stack.clear()
        self._current_task = None

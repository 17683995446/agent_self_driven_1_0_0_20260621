"""
任务资源预算

第一性原理：资源是有限的，必须为每个任务分配可控的预算
确保总资源使用不超过系统安全阈值
"""

from dataclasses import dataclass
from typing import Dict, Optional

from ....platform.support.models.base.task import Task, TaskPriority


@dataclass
class ResourceAllocation:
    """资源分配"""
    cpu: float = 0.0
    memory: float = 0.0
    approved: bool = True
    message: str = "Approved"


class TaskResourceBudget:
    """
    任务资源预算

    为每个任务分配资源预算，确保总资源不超限
    """

    def __init__(self, total_cpu: float = 0.2, total_memory: float = 0.2) -> None:
        self.total_cpu = total_cpu
        self.total_memory = total_memory
        self._allocated: Dict[str, ResourceAllocation] = {}

    @property
    def used_cpu(self) -> float:
        """已使用CPU"""
        return sum(a.cpu for a in self._allocated.values())

    @property
    def used_memory(self) -> float:
        """已使用内存"""
        return sum(a.memory for a in self._allocated.values())

    @property
    def available_cpu(self) -> float:
        """可用CPU"""
        return self.total_cpu - self.used_cpu

    @property
    def available_memory(self) -> float:
        """可用内存"""
        return self.total_memory - self.used_memory

    def allocate(self, task: Task) -> ResourceAllocation:
        """为任务分配资源"""
        cpu = self._compute_cpu_allocation(task)
        memory = self._compute_memory_allocation(task)
        approved = self._is_approved(task, cpu, memory)
        allocation = ResourceAllocation(
            cpu=cpu,
            memory=memory,
            approved=approved,
            message="Approved" if approved else "Throttled",
        )
        self._allocated[task.id] = allocation
        return allocation

    def _compute_cpu_allocation(self, task: Task) -> float:
        """计算CPU分配"""
        return min(task.max_cpu_usage, self.available_cpu * 0.8)

    def _compute_memory_allocation(self, task: Task) -> float:
        """计算内存分配"""
        return min(task.max_memory_usage, self.available_memory * 0.8)

    def _is_approved(self, task: Task, cpu: float, memory: float) -> bool:
        """判断分配是否完全批准"""
        return cpu >= task.max_cpu_usage and memory >= task.max_memory_usage

    def release(self, task_id: str) -> None:
        """释放任务资源"""
        if task_id in self._allocated:
            del self._allocated[task_id]

    def get_allocation(self, task_id: str) -> Optional[ResourceAllocation]:
        """获取任务的资源分配"""
        return self._allocated.get(task_id)

    def is_within_budget(self) -> bool:
        """检查是否在预算内"""
        return self.used_cpu <= self.total_cpu and self.used_memory <= self.total_memory

    def clear(self) -> None:
        """清空所有分配"""
        self._allocated.clear()

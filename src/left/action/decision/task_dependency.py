"""
任务依赖管理

第一性原理：复杂任务必须分解为有序的子任务序列
使用拓扑排序确保依赖关系被正确满足
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set

from ....platform.support.models.base.task import Task


class TaskDependencyManager(ABC):
    """任务依赖管理器抽象基类"""

    @abstractmethod
    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """添加依赖关系"""
        pass

    @abstractmethod
    def can_execute(self, task_id: str, completed_tasks: Set[str]) -> bool:
        """检查任务是否可以执行"""
        pass

    @abstractmethod
    def get_execution_order(self, tasks: List[Task]) -> List[Task]:
        """获取执行顺序（拓扑排序）"""
        pass


class StandardTaskDependencyManager(TaskDependencyManager):
    """
    标准任务依赖管理器

    管理任务间的依赖关系，支持拓扑排序
    """

    def __init__(self) -> None:
        self._dependencies: Dict[str, Set[str]] = {}
        self._dependents: Dict[str, Set[str]] = {}

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """添加依赖关系：task_id 依赖于 depends_on"""
        self._ensure_task(task_id)
        self._ensure_task(depends_on)
        self._dependencies[task_id].add(depends_on)
        self._dependents[depends_on].add(task_id)

    def _ensure_task(self, task_id: str) -> None:
        """确保任务在数据结构中"""
        if task_id not in self._dependencies:
            self._dependencies[task_id] = set()
        if task_id not in self._dependents:
            self._dependents[task_id] = set()

    def remove_dependency(self, task_id: str, depends_on: str) -> None:
        """移除依赖关系"""
        if task_id in self._dependencies:
            self._dependencies[task_id].discard(depends_on)
        if depends_on in self._dependents:
            self._dependents[depends_on].discard(task_id)

    def get_dependencies(self, task_id: str) -> Set[str]:
        """获取任务的所有依赖"""
        return set(self._dependencies.get(task_id, set()))

    def get_dependents(self, task_id: str) -> Set[str]:
        """获取依赖于该任务的所有任务"""
        return set(self._dependents.get(task_id, set()))

    def can_execute(self, task_id: str, completed_tasks: Set[str]) -> bool:
        """检查任务是否可以执行（所有依赖已完成）"""
        deps = self._dependencies.get(task_id, set())
        return deps.issubset(completed_tasks)

    def get_execution_order(self, tasks: List[Task]) -> List[Task]:
        """使用拓扑排序获取执行顺序"""
        task_map = {t.id: t for t in tasks}
        graph = {t.id: self.get_dependencies(t.id) for t in tasks}
        return self._topological_sort(graph, task_map)

    def _topological_sort(self, graph: Dict[str, Set[str]], task_map: Dict[str, Task]) -> List[Task]:
        """拓扑排序算法"""
        in_degree = {tid: len(deps) for tid, deps in graph.items()}
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result: List[str] = []
        while queue:
            current = queue.pop(0)
            result.append(current)
            for tid in graph:
                if current in graph[tid]:
                    in_degree[tid] -= 1
                    if in_degree[tid] == 0:
                        queue.append(tid)
        return [task_map[tid] for tid in result if tid in task_map]

    def has_cycle(self) -> bool:
        """检测是否存在循环依赖"""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        for task_id in self._dependencies:
            if self._has_cycle_dfs(task_id, visited, rec_stack):
                return True
        return False

    def _has_cycle_dfs(self, task_id: str, visited: Set[str], rec_stack: Set[str]) -> bool:
        """DFS检测循环"""
        visited.add(task_id)
        rec_stack.add(task_id)
        for dep in self._dependencies.get(task_id, set()):
            if dep not in visited:
                if self._has_cycle_dfs(dep, visited, rec_stack):
                    return True
            elif dep in rec_stack:
                return True
        rec_stack.discard(task_id)
        return False

    def clear(self) -> None:
        """清空所有依赖关系"""
        self._dependencies.clear()
        self._dependents.clear()

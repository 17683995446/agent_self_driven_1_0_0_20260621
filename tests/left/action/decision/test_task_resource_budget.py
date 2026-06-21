"""
任务资源预算测试

验证资源分配、释放、边界条件
"""

import pytest

from src.left.action.decision.task_resource_budget import TaskResourceBudget, ResourceAllocation
from src.platform.support.models.base.task import Task, TaskPriority


class TestTaskResourceBudgetAllocate:
    """测试资源分配"""

    def setup_method(self):
        self.budget = TaskResourceBudget(total_cpu=0.5, total_memory=0.5)

    def test_allocate_normal_task(self):
        """正常值：正常任务分配"""
        task = Task(name="task", max_cpu_usage=0.1, max_memory_usage=0.1)
        alloc = self.budget.allocate(task)
        assert alloc.cpu == 0.1
        assert alloc.memory == 0.1
        assert alloc.approved

    def test_allocate_large_task_throttled(self):
        """正常值：大任务被限制"""
        task = Task(name="large", max_cpu_usage=1.0, max_memory_usage=1.0)
        alloc = self.budget.allocate(task)
        assert alloc.cpu < task.max_cpu_usage
        assert alloc.memory < task.max_memory_usage
        assert not alloc.approved
        assert alloc.message == "Throttled"

    def test_allocate_multiple_tasks(self):
        """正常值：多个任务分配"""
        t1 = Task(name="t1", max_cpu_usage=0.2, max_memory_usage=0.2)
        t2 = Task(name="t2", max_cpu_usage=0.2, max_memory_usage=0.2)
        a1 = self.budget.allocate(t1)
        a2 = self.budget.allocate(t2)
        assert a1.approved
        assert a2.approved
        assert self.budget.used_cpu == 0.4
        assert self.budget.used_memory == 0.4

    def test_allocate_exceeds_budget(self):
        """边界极值：超出预算"""
        t1 = Task(name="t1", max_cpu_usage=0.4, max_memory_usage=0.4)
        t2 = Task(name="t2", max_cpu_usage=0.4, max_memory_usage=0.4)
        t3 = Task(name="t3", max_cpu_usage=0.4, max_memory_usage=0.4)
        self.budget.allocate(t1)
        self.budget.allocate(t2)
        a3 = self.budget.allocate(t3)
        assert a3.cpu < t3.max_cpu_usage or a3.memory < t3.max_memory_usage
        assert not a3.approved


class TestTaskResourceBudgetRelease:
    """测试资源释放"""

    def setup_method(self):
        self.budget = TaskResourceBudget(total_cpu=0.5, total_memory=0.5)

    def test_release_frees_resources(self):
        """正常值：释放资源"""
        task = Task(name="task", max_cpu_usage=0.2, max_memory_usage=0.2)
        self.budget.allocate(task)
        assert self.budget.used_cpu == 0.2
        self.budget.release(task.id)
        assert self.budget.used_cpu == 0.0
        assert self.budget.used_memory == 0.0

    def test_release_unknown_task(self):
        """空入参：释放未知任务不报错"""
        self.budget.release("unknown")
        assert self.budget.used_cpu == 0.0

    def test_get_allocation(self):
        """正常值：获取分配信息"""
        task = Task(name="task", max_cpu_usage=0.1, max_memory_usage=0.1)
        self.budget.allocate(task)
        alloc = self.budget.get_allocation(task.id)
        assert alloc is not None
        assert alloc.cpu == 0.1

    def test_get_allocation_unknown(self):
        """空入参：获取未知任务分配"""
        assert self.budget.get_allocation("unknown") is None


class TestTaskResourceBudgetBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.budget = TaskResourceBudget(total_cpu=0.5, total_memory=0.5)

    def test_zero_budget(self):
        """边界极值：零预算"""
        budget = TaskResourceBudget(total_cpu=0.0, total_memory=0.0)
        task = Task(name="task", max_cpu_usage=0.1, max_memory_usage=0.1)
        alloc = budget.allocate(task)
        assert alloc.cpu == 0.0
        assert alloc.memory == 0.0
        assert not alloc.approved

    def test_exact_budget_fit(self):
        """边界极值：恰好填满预算"""
        budget = TaskResourceBudget(total_cpu=0.25, total_memory=0.25)
        task = Task(name="task", max_cpu_usage=0.2, max_memory_usage=0.2)
        alloc = budget.allocate(task)
        assert alloc.cpu == 0.2
        assert alloc.memory == 0.2
        assert alloc.approved
        assert budget.is_within_budget()

    def test_is_within_budget(self):
        """正常值：预算检查"""
        task = Task(name="task", max_cpu_usage=0.1, max_memory_usage=0.1)
        self.budget.allocate(task)
        assert self.budget.is_within_budget()

    def test_clear_all(self):
        """正常值：清空所有"""
        t1 = Task(name="t1", max_cpu_usage=0.1, max_memory_usage=0.1)
        t2 = Task(name="t2", max_cpu_usage=0.1, max_memory_usage=0.1)
        self.budget.allocate(t1)
        self.budget.allocate(t2)
        self.budget.clear()
        assert self.budget.used_cpu == 0.0
        assert self.budget.get_allocation(t1.id) is None

    def test_available_resources_decrease(self):
        """边界：可用资源递减"""
        t1 = Task(name="t1", max_cpu_usage=0.2, max_memory_usage=0.2)
        t2 = Task(name="t2", max_cpu_usage=0.2, max_memory_usage=0.2)
        self.budget.allocate(t1)
        before_cpu = self.budget.available_cpu
        self.budget.allocate(t2)
        after_cpu = self.budget.available_cpu
        assert after_cpu < before_cpu


class TestTaskResourceBudgetInvalidInputs:
    """测试非法输入"""

    def test_negative_total_budget(self):
        """非法格式：负预算返回非正值"""
        budget = TaskResourceBudget(total_cpu=-0.1, total_memory=-0.1)
        task = Task(name="task", max_cpu_usage=0.1, max_memory_usage=0.1)
        alloc = budget.allocate(task)
        assert alloc.cpu <= 0.0
        assert alloc.memory <= 0.0
        assert not alloc.approved

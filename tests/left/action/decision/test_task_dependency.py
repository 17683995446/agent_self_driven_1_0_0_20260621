"""
任务依赖管理测试

验证依赖添加、拓扑排序、循环检测、边界条件
"""

import pytest

from src.left.action.decision.task_dependency import StandardTaskDependencyManager
from src.platform.support.models.base.task import Task


class TestTaskDependencyAdd:
    """测试依赖添加"""

    def setup_method(self):
        self.manager = StandardTaskDependencyManager()

    def test_add_single_dependency(self):
        """正常值：添加单个依赖"""
        self.manager.add_dependency("t2", "t1")
        assert self.manager.get_dependencies("t2") == {"t1"}
        assert self.manager.get_dependents("t1") == {"t2"}

    def test_add_multiple_dependencies(self):
        """正常值：添加多个依赖"""
        self.manager.add_dependency("t3", "t1")
        self.manager.add_dependency("t3", "t2")
        assert self.manager.get_dependencies("t3") == {"t1", "t2"}

    def test_remove_dependency(self):
        """正常值：移除依赖"""
        self.manager.add_dependency("t2", "t1")
        self.manager.remove_dependency("t2", "t1")
        assert self.manager.get_dependencies("t2") == set()

    def test_no_dependencies(self):
        """空入参：无依赖的任务"""
        assert self.manager.get_dependencies("t1") == set()
        assert self.manager.get_dependents("t1") == set()


class TestTaskDependencyCanExecute:
    """测试执行判断"""

    def setup_method(self):
        self.manager = StandardTaskDependencyManager()

    def test_can_execute_no_deps(self):
        """正常值：无依赖可直接执行"""
        assert self.manager.can_execute("t1", set())

    def test_can_execute_with_deps_met(self):
        """正常值：依赖已满足"""
        self.manager.add_dependency("t2", "t1")
        assert self.manager.can_execute("t2", {"t1"})

    def test_can_execute_with_deps_unmet(self):
        """正常值：依赖未满足"""
        self.manager.add_dependency("t2", "t1")
        assert not self.manager.can_execute("t2", set())

    def test_can_execute_partial_deps(self):
        """正常值：部分依赖满足"""
        self.manager.add_dependency("t3", "t1")
        self.manager.add_dependency("t3", "t2")
        assert not self.manager.can_execute("t3", {"t1"})
        assert self.manager.can_execute("t3", {"t1", "t2"})


class TestTaskDependencyTopologicalSort:
    """测试拓扑排序"""

    def setup_method(self):
        self.manager = StandardTaskDependencyManager()

    def test_linear_chain(self):
        """正常值：线性依赖链"""
        t1 = Task(id="t1", name="t1")
        t2 = Task(id="t2", name="t2")
        t3 = Task(id="t3", name="t3")
        self.manager.add_dependency("t2", "t1")
        self.manager.add_dependency("t3", "t2")
        order = self.manager.get_execution_order([t1, t2, t3])
        ids = [t.id for t in order]
        assert ids.index("t1") < ids.index("t2") < ids.index("t3")

    def test_diamond_dependency(self):
        """正常值：菱形依赖"""
        t1 = Task(id="t1", name="t1")
        t2 = Task(id="t2", name="t2")
        t3 = Task(id="t3", name="t3")
        t4 = Task(id="t4", name="t4")
        self.manager.add_dependency("t2", "t1")
        self.manager.add_dependency("t3", "t1")
        self.manager.add_dependency("t4", "t2")
        self.manager.add_dependency("t4", "t3")
        order = self.manager.get_execution_order([t1, t2, t3, t4])
        ids = [t.id for t in order]
        assert ids.index("t1") < ids.index("t4")
        assert ids.index("t2") < ids.index("t4")
        assert ids.index("t3") < ids.index("t4")

    def test_independent_tasks(self):
        """正常值：独立任务"""
        t1 = Task(id="t1", name="t1")
        t2 = Task(id="t2", name="t2")
        order = self.manager.get_execution_order([t1, t2])
        assert len(order) == 2

    def test_empty_list(self):
        """空入参：空任务列表"""
        order = self.manager.get_execution_order([])
        assert order == []


class TestTaskDependencyCycleDetection:
    """测试循环检测"""

    def setup_method(self):
        self.manager = StandardTaskDependencyManager()

    def test_no_cycle(self):
        """正常值：无循环依赖"""
        self.manager.add_dependency("t2", "t1")
        self.manager.add_dependency("t3", "t2")
        assert not self.manager.has_cycle()

    def test_simple_cycle(self):
        """正常值：简单循环"""
        self.manager.add_dependency("t1", "t2")
        self.manager.add_dependency("t2", "t1")
        assert self.manager.has_cycle()

    def test_indirect_cycle(self):
        """正常值：间接循环"""
        self.manager.add_dependency("t1", "t2")
        self.manager.add_dependency("t2", "t3")
        self.manager.add_dependency("t3", "t1")
        assert self.manager.has_cycle()

    def test_self_cycle(self):
        """边界极值：自依赖"""
        self.manager.add_dependency("t1", "t1")
        assert self.manager.has_cycle()


class TestTaskDependencyBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.manager = StandardTaskDependencyManager()

    def test_large_dependency_graph(self):
        """边界极值：大量任务"""
        tasks = [Task(id=f"t{i}", name=f"t{i}") for i in range(100)]
        for i in range(1, 100):
            self.manager.add_dependency(f"t{i}", f"t{i-1}")
        order = self.manager.get_execution_order(tasks)
        assert len(order) == 100

    def test_clear_resets_state(self):
        """正常值：清空重置状态"""
        self.manager.add_dependency("t2", "t1")
        self.manager.clear()
        assert self.manager.get_dependencies("t2") == set()
        assert not self.manager.has_cycle()

    def test_unknown_task_dependencies(self):
        """边界：未知任务的依赖"""
        assert self.manager.get_dependencies("unknown") == set()
        assert self.manager.can_execute("unknown", set())

"""
任务DAG动态分解器测试

验证规则分解、组合分解、验证器
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.decision.task_dag_planner import (
    RuleBasedTaskDecomposer, CompositeTaskDecomposer,
    DecompositionValidator, TaskDecomposer,
)
from src.platform.support.models.base.task import Task
from src.platform.support.models.base.dag import DAGNode, DAGPlan


class TestRuleBasedTaskDecomposer:
    """测试基于规则的分解器"""

    def setup_method(self):
        self.decomposer = RuleBasedTaskDecomposer()

    def test_can_decompose_fetch_analyze(self):
        task = Task(name="fetch_and_analyze", description="fetch weather then analyze it")
        assert self.decomposer.can_decompose(task) is True

    def test_can_decompose_file_process(self):
        task = Task(name="file_process", description="read file and write result")
        assert self.decomposer.can_decompose(task) is True

    def test_cannot_decompose_simple_task(self):
        task = Task(name="simple", description="just do something simple")
        assert self.decomposer.can_decompose(task) is False

    def test_decompose_fetch_analyze(self):
        task = Task(name="fetch_and_analyze", description="fetch weather then analyze it")
        plan = self.decomposer.decompose(task)
        assert len(plan.nodes) == 2
        names = {n.name for n in plan.nodes.values()}
        assert "fetch_data" in names
        assert "analyze_data" in names

    def test_decompose_file_process(self):
        task = Task(name="file_process", description="read file and write result")
        plan = self.decomposer.decompose(task)
        assert len(plan.nodes) == 3
        order = plan.get_execution_order()
        assert len(order) == 3

    def test_decompose_simple_returns_single_node(self):
        task = Task(name="simple", description="just do something simple")
        plan = self.decomposer.decompose(task)
        assert len(plan.nodes) == 1

    def test_dependencies_set(self):
        task = Task(name="fetch_and_analyze", description="fetch weather then analyze it")
        plan = self.decomposer.decompose(task)
        analyze = [n for n in plan.nodes.values() if n.name == "analyze_data"][0]
        fetch = [n for n in plan.nodes.values() if n.name == "fetch_data"][0]
        assert analyze.dependencies == {fetch.id}

    def test_empty_description(self):
        task = Task(name="empty", description="")
        assert self.decomposer.can_decompose(task) is False

    def test_chinese_pattern(self):
        task = Task(name="chinese", description="获取数据并分析")
        assert self.decomposer.can_decompose(task) is True


class TestDecompositionValidator:
    """测试分解验证器"""

    def setup_method(self):
        self.validator = DecompositionValidator()

    def test_valid_plan(self):
        plan = DAGPlan()
        plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="p"))
        plan.add_node(DAGNode(id="b", name="b", action="x", plugin_name="p", dependencies={"a"}))
        assert self.validator.validate(plan) is True

    def test_empty_plan_invalid(self):
        plan = DAGPlan()
        assert self.validator.validate(plan) is False
        assert "plan has no nodes" in self.validator.get_errors()

    def test_dangling_dependency_invalid(self):
        plan = DAGPlan()
        plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="p", dependencies={"missing"}))
        assert self.validator.validate(plan) is False
        assert "missing node" in self.validator.get_errors()[0]

    def test_cycle_invalid(self):
        plan = DAGPlan()
        plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="p", dependencies={"b"}))
        plan.add_node(DAGNode(id="b", name="b", action="x", plugin_name="p", dependencies={"a"}))
        assert self.validator.validate(plan) is False
        assert "cycle" in self.validator.get_errors()[0]

    def test_self_loop_invalid(self):
        plan = DAGPlan()
        plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="p", dependencies={"a"}))
        assert self.validator.validate(plan) is False


class TestCompositeTaskDecomposer:
    """测试组合分解器"""

    def test_composite_uses_rule_decomposer(self):
        rule = RuleBasedTaskDecomposer()
        composite = CompositeTaskDecomposer([rule])
        task = Task(name="fetch_and_analyze", description="fetch then analyze")
        assert composite.can_decompose(task) is True
        plan = composite.decompose(task)
        assert len(plan.nodes) == 2

    def test_composite_falls_back_to_single(self):
        rule = RuleBasedTaskDecomposer()
        composite = CompositeTaskDecomposer([rule])
        task = Task(name="simple", description="just run")
        plan = composite.decompose(task)
        assert len(plan.nodes) == 1

    def test_composite_empty_list(self):
        composite = CompositeTaskDecomposer([])
        task = Task(name="simple", description="just run")
        plan = composite.decompose(task)
        assert len(plan.nodes) == 1

    def test_composite_invalid_plan_falls_back(self):
        class BadDecomposer(TaskDecomposer):
            def can_decompose(self, task: Task) -> bool:
                return True

            def decompose(self, task: Task) -> DAGPlan:
                plan = DAGPlan()
                plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="p", dependencies={"missing"}))
                return plan

        composite = CompositeTaskDecomposer([BadDecomposer()])
        task = Task(name="bad", description="bad")
        plan = composite.decompose(task)
        assert len(plan.nodes) == 1

    def test_composite_is_subclass(self):
        assert issubclass(CompositeTaskDecomposer, TaskDecomposer)


class TestTaskDecomposerBase:
    """测试分解器基类"""

    def test_base_is_abstract(self):
        with pytest.raises(TypeError):
            TaskDecomposer()

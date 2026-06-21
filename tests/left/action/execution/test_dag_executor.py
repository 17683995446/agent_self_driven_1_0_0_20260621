"""
DAG执行器测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
import time

from src.left.action.execution.dag_executor import DAGExecutor
from src.platform.support.models.base.dag import DAGPlan, DAGNode, DAGNodeStatus
from src.platform.lifecycle.memory.plugin_manager import PluginManager


class TestDAGExecutor:
    """DAG执行器测试类"""

    @pytest.fixture
    def executor(self):
        pm = PluginManager()
        pm.initialize()
        return DAGExecutor(pm, max_workers=2)

    def test_execute_empty_plan(self, executor):
        """测试执行空计划"""
        plan = DAGPlan()
        result = executor.execute(plan)
        assert result["total_nodes"] == 0
        assert result["success"] == 0

    def test_execute_single_node(self, executor):
        """测试执行单节点"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="test", action="time", plugin_name="tool_plugin")
        plan.add_node(node)
        result = executor.execute(plan)
        assert result["total_nodes"] == 1

    def test_execute_sequential(self, executor):
        """测试顺序执行"""
        plan = DAGPlan()
        a = DAGNode(id="A", name="a", action="time", plugin_name="tool_plugin")
        b = DAGNode(id="B", name="b", action="time", plugin_name="tool_plugin", dependencies={"A"})
        plan.add_node(a)
        plan.add_node(b)
        result = executor.execute(plan)
        assert result["total_nodes"] == 2

    def test_execute_parallel(self, executor):
        """测试并行执行"""
        plan = DAGPlan()
        a = DAGNode(id="A", name="a", action="time", plugin_name="tool_plugin")
        b = DAGNode(id="B", name="b", action="time", plugin_name="tool_plugin")
        plan.add_node(a)
        plan.add_node(b)
        result = executor.execute(plan)
        assert result["total_nodes"] == 2

    def test_shutdown(self, executor):
        """测试关闭"""
        executor.shutdown()

    def test_build_result(self, executor):
        """测试结果构建"""
        plan = DAGPlan()
        a = DAGNode(id="A", name="a", action="time", plugin_name="tool_plugin")
        a.status = DAGNodeStatus.COMPLETED
        plan.add_node(a)
        result = executor._build_result(plan, 1.0)
        assert result["success"] == 1
        assert result["failed"] == 0
        assert result["duration"] == 1.0

    def test_count_success(self, executor):
        """测试成功计数"""
        plan = DAGPlan()
        a = DAGNode(id="A", name="a", action="time", plugin_name="tool_plugin")
        a.status = DAGNodeStatus.COMPLETED
        b = DAGNode(id="B", name="b", action="time", plugin_name="tool_plugin")
        b.status = DAGNodeStatus.FAILED
        plan.add_node(a)
        plan.add_node(b)
        assert executor._count_success(plan) == 1
        assert executor._count_failed(plan) == 1

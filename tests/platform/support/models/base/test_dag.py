"""
DAG模型测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.support.models.base.dag import DAGPlan, DAGNode, DAGNodeStatus


class TestDAGNode:
    """DAG节点测试类"""

    def test_node_creation(self):
        """测试节点创建"""
        node = DAGNode(id="n1", name="test", action="read", plugin_name="file")
        assert node.id == "n1"
        assert node.status == DAGNodeStatus.PENDING

    def test_node_duration_not_started(self):
        """测试未开始节点时长"""
        node = DAGNode(id="n1", name="test", action="read", plugin_name="file")
        assert node.duration == 0.0

    def test_node_duration_running(self):
        """测试运行中节点时长"""
        import time
        node = DAGNode(id="n1", name="test", action="read", plugin_name="file")
        node.start_time = time.time()
        assert node.duration >= 0.0


class TestDAGPlan:
    """DAG计划测试类"""

    @pytest.fixture
    def simple_plan(self):
        """简单计划：A -> B"""
        plan = DAGPlan(description="simple")
        a = DAGNode(id="A", name="node_a", action="read", plugin_name="file")
        b = DAGNode(id="B", name="node_b", action="write", plugin_name="file", dependencies={"A"})
        plan.add_node(a)
        plan.add_node(b)
        return plan

    @pytest.fixture
    def parallel_plan(self):
        """并行计划：A, B -> C"""
        plan = DAGPlan(description="parallel")
        a = DAGNode(id="A", name="node_a", action="read", plugin_name="file")
        b = DAGNode(id="B", name="node_b", action="read", plugin_name="file")
        c = DAGNode(id="C", name="node_c", action="write", plugin_name="file", dependencies={"A", "B"})
        plan.add_node(a)
        plan.add_node(b)
        plan.add_node(c)
        return plan

    def test_add_node(self):
        """测试添加节点"""
        plan = DAGPlan()
        node = DAGNode(id="n1", name="test", action="read", plugin_name="file")
        plan.add_node(node)
        assert "n1" in plan.nodes

    def test_execution_order_simple(self, simple_plan):
        """测试简单计划执行顺序"""
        order = simple_plan.get_execution_order()
        assert order.index("A") < order.index("B")

    def test_execution_order_parallel(self, parallel_plan):
        """测试并行计划执行顺序"""
        order = parallel_plan.get_execution_order()
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("C")

    def test_get_ready_nodes_initial(self, simple_plan):
        """测试初始就绪节点"""
        ready = simple_plan.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "A"

    def test_get_ready_nodes_after_complete(self, simple_plan):
        """测试完成后就绪节点"""
        simple_plan.nodes["A"].status = DAGNodeStatus.COMPLETED
        ready = simple_plan.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "B"

    def test_is_complete_false(self, simple_plan):
        """测试未完成状态"""
        assert simple_plan.is_complete() is False

    def test_is_complete_true(self, simple_plan):
        """测试完成状态"""
        for node in simple_plan.nodes.values():
            node.status = DAGNodeStatus.COMPLETED
        assert simple_plan.is_complete() is True

    def test_is_complete_with_failed(self, simple_plan):
        """测试含失败节点的完成状态"""
        for node in simple_plan.nodes.values():
            node.status = DAGNodeStatus.FAILED
        assert simple_plan.is_complete() is True

    def test_empty_plan(self):
        """测试空计划"""
        plan = DAGPlan()
        assert plan.is_complete() is True
        assert plan.get_execution_order() == []
        assert plan.get_ready_nodes() == []

    def test_to_dict(self, simple_plan):
        """测试转换为字典"""
        data = simple_plan.to_dict()
        assert "id" in data
        assert "nodes" in data
        assert "A" in data["nodes"]
        assert "B" in data["nodes"]

    def test_circular_dependency(self):
        """测试循环依赖（边界）"""
        plan = DAGPlan()
        a = DAGNode(id="A", name="a", action="read", plugin_name="file", dependencies={"B"})
        b = DAGNode(id="B", name="b", action="read", plugin_name="file", dependencies={"A"})
        plan.add_node(a)
        plan.add_node(b)
        order = plan.get_execution_order()
        assert len(order) < 2

    def test_single_node_plan(self):
        """测试单节点计划"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="a", action="read", plugin_name="file")
        plan.add_node(node)
        order = plan.get_execution_order()
        assert order == ["A"]
        ready = plan.get_ready_nodes()
        assert len(ready) == 1

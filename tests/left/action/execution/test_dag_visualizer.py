"""
DAG可视化与监控测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.execution.dag_visualizer import (
    DAGRenderer,
    MermaidDAGRenderer,
    DotDAGRenderer,
    TextDAGRenderer,
    DAGMonitor,
    DAGExecutionEvent,
)
from src.left.action.execution.dag_executor import DAGExecutor
from src.platform.support.models.base.dag import DAGPlan, DAGNode, DAGNodeStatus
from src.platform.support.models.base.task import TaskResult


class TestMermaidRenderer:
    """Mermaid渲染器测试"""

    def setup_method(self):
        self.renderer = MermaidDAGRenderer()

    def test_render_empty_plan(self):
        """测试空计划"""
        text = self.renderer.render(DAGPlan())
        assert "flowchart TD" in text
        assert "-->" not in text

    def test_render_single_node(self):
        """测试单节点"""
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        text = self.renderer.render(plan)
        assert 'A["a"]' in text
        assert ":::pending" in text

    def test_render_dependencies(self):
        """测试依赖边"""
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        plan.add_node(DAGNode(
            id="B", name="b", action="x", plugin_name="p", dependencies={"A"}
        ))
        text = self.renderer.render(plan)
        assert "A --> B" in text

    def test_render_status_colors(self):
        """测试状态颜色"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        node.status = DAGNodeStatus.COMPLETED
        plan.add_node(node)
        text = self.renderer.render(plan)
        assert ":::completed" in text

    def test_render_invalid_plan_raises(self):
        """测试非法入参"""
        with pytest.raises(AttributeError):
            self.renderer.render(None)


class TestDotRenderer:
    """DOT渲染器测试"""

    def setup_method(self):
        self.renderer = DotDAGRenderer()

    def test_render_empty_plan(self):
        """测试空计划"""
        text = self.renderer.render(DAGPlan())
        assert "digraph G" in text
        assert "->" not in text

    def test_render_single_node(self):
        """测试单节点"""
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        text = self.renderer.render(plan)
        assert '"A"' in text
        assert 'label="a"' in text

    def test_render_dependencies(self):
        """测试依赖边"""
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        plan.add_node(DAGNode(
            id="B", name="b", action="x", plugin_name="p", dependencies={"A"}
        ))
        text = self.renderer.render(plan)
        assert '"A" -> "B"' in text

    def test_render_status_color(self):
        """测试状态颜色"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        node.status = DAGNodeStatus.FAILED
        plan.add_node(node)
        text = self.renderer.render(plan)
        assert 'color="red"' in text


class TestTextRenderer:
    """文本渲染器测试"""

    def setup_method(self):
        self.renderer = TextDAGRenderer()

    def test_render_empty_plan(self):
        """测试空计划"""
        text = self.renderer.render(DAGPlan(description="empty"))
        assert "DAG: empty" in text
        assert "[pending]" not in text

    def test_render_nodes(self):
        """测试节点渲染"""
        plan = DAGPlan(description="demo")
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        plan.add_node(DAGNode(
            id="B", name="b", action="x", plugin_name="p", dependencies={"A"}
        ))
        text = self.renderer.render(plan)
        assert "[pending] a deps=none" in text
        assert "[pending] b deps=A" in text

    def test_render_completed_status(self):
        """测试完成状态"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        node.status = DAGNodeStatus.COMPLETED
        plan.add_node(node)
        text = self.renderer.render(plan)
        assert "[completed] a" in text


class TestDAGRendererBase:
    """渲染器基类测试"""

    def test_cannot_instantiate_abstract(self):
        """测试抽象基类不可实例化"""
        with pytest.raises(TypeError):
            DAGRenderer()


class TestDAGMonitor:
    """DAG监控器测试"""

    def setup_method(self):
        self.monitor = DAGMonitor()

    def test_record_start_event(self):
        """测试记录开始事件"""
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        self.monitor.record_start(node)
        events = self.monitor.get_events()
        assert len(events) == 1
        assert events[0].event_type == "start"
        assert events[0].node_id == "A"

    def test_record_complete_event(self):
        """测试记录完成事件"""
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        node.status = DAGNodeStatus.COMPLETED
        node.start_time = 1.0
        node.end_time = 2.0
        self.monitor.record_complete(node)
        events = self.monitor.get_events()
        assert len(events) == 1
        assert events[0].event_type == "complete"
        assert events[0].status == "completed"
        assert events[0].duration == 1.0

    def test_empty_snapshot(self):
        """测试空快照"""
        plan = DAGPlan(id="p1")
        snapshot = self.monitor.snapshot(plan)
        assert snapshot["plan_id"] == "p1"
        assert snapshot["events"] == []
        assert snapshot["nodes"] == {}

    def test_snapshot_after_events(self):
        """测试事件后快照"""
        plan = DAGPlan()
        node = DAGNode(id="A", name="a", action="x", plugin_name="p")
        plan.add_node(node)
        self.monitor.record_start(node)
        self.monitor.record_complete(node)
        snapshot = self.monitor.snapshot(plan)
        assert len(snapshot["events"]) == 2
        assert "A" in snapshot["nodes"]

    def test_event_to_dict(self):
        """测试事件序列化"""
        event = DAGExecutionEvent(
            timestamp=1.0,
            node_id="A",
            node_name="a",
            event_type="start",
        )
        data = event.to_dict()
        assert data["node_id"] == "A"
        assert data["event_type"] == "start"
        assert data["status"] is None


class MockPluginManager:
    """模拟插件管理器"""

    def execute(self, plugin_name: str, action: str, params: dict) -> TaskResult:
        return TaskResult(success=True, data={"plugin": plugin_name, "action": action})


class TestDAGExecutorMonitoring:
    """DAG执行器与监控集成测试"""

    def test_execute_records_monitor_events(self):
        """测试执行时记录监控事件"""
        monitor = DAGMonitor()
        executor = DAGExecutor(MockPluginManager(), max_workers=2, monitor=monitor)
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        plan.add_node(DAGNode(
            id="B", name="b", action="x", plugin_name="p", dependencies={"A"}
        ))
        result = executor.execute(plan)
        executor.shutdown()
        events = monitor.get_events()
        assert result["failed"] == 0
        assert len(events) == 4
        assert events[0].event_type == "start"
        assert events[1].event_type == "complete"

    def test_execute_snapshot(self):
        """测试执行后快照"""
        monitor = DAGMonitor()
        executor = DAGExecutor(MockPluginManager(), max_workers=2, monitor=monitor)
        plan = DAGPlan(id="plan1")
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        executor.execute(plan)
        executor.shutdown()
        snapshot = monitor.snapshot(plan)
        assert snapshot["plan_id"] == "plan1"
        assert len(snapshot["events"]) == 2
        assert snapshot["nodes"]["A"]["status"] == "completed"

    def test_execute_without_monitor(self):
        """测试无监控器时不报错"""
        executor = DAGExecutor(MockPluginManager(), max_workers=2)
        plan = DAGPlan()
        plan.add_node(DAGNode(id="A", name="a", action="x", plugin_name="p"))
        result = executor.execute(plan)
        executor.shutdown()
        assert result["success"] == 1

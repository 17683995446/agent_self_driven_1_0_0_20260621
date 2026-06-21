"""
复杂任务处理器R75测试

验证复杂任务识别、分解、执行、跨工具结果传递
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.decision.complex_task_handler import ComplexTaskHandler
from src.left.action.decision.task_dag_planner import CompositeTaskDecomposer, RuleBasedTaskDecomposer
from src.left.action.decision.decision_v2 import DecisionEngineV2
from src.platform.support.models.base.task import Task, TaskResult
from src.platform.support.models.base.dag import DAGNode, DAGPlan, DAGNodeStatus
from src.platform.lifecycle.memory.plugin_manager import PluginManager


class MockPluginManager:
    """模拟插件管理器"""

    def execute(self, plugin_name: str, action: str, params: dict) -> TaskResult:
        if plugin_name == "http_plugin":
            return TaskResult(success=True, data={"content": "weather data"})
        if plugin_name == "llm_plugin":
            return TaskResult(success=True, data={"content": f"analyzed: {params.get('text', '')}"})
        if plugin_name == "file_plugin":
            return TaskResult(success=True, data={"content": params.get("content", "")})
        return TaskResult(success=False, message="unknown plugin")


class TestComplexTaskHandler:
    """测试复杂任务处理器"""

    def setup_method(self):
        self.plugins = MockPluginManager()
        decomposer = CompositeTaskDecomposer([RuleBasedTaskDecomposer()])
        self.handler = ComplexTaskHandler(self.plugins, decomposer=decomposer)

    def teardown_method(self):
        self.handler.shutdown()

    def test_is_complex_fetch_analyze(self):
        task = Task(name="complex", description="fetch weather then analyze it")
        assert self.handler.is_complex(task) is True

    def test_is_complex_simple(self):
        task = Task(name="simple", description="just run")
        assert self.handler.is_complex(task) is False

    def test_handle_fetch_analyze(self):
        task = Task(name="complex", description="fetch weather then analyze it")
        result = self.handler.handle(task)
        assert result.success is True
        assert "2/2" in result.message

    def test_handle_file_process(self):
        task = Task(name="complex", description="read file and write result")
        result = self.handler.handle(task)
        assert result.success is True
        assert "3/3" in result.message

    def test_handle_simple_fallback(self):
        task = Task(name="simple", description="just run")
        result = self.handler.handle(task)
        assert result.success is False
        assert "could not be decomposed" in result.message

    def test_empty_task(self):
        task = Task(name="empty", description="")
        assert self.handler.is_complex(task) is False


class TestDecisionEngineV2ComplexTask:
    """测试决策引擎V2复杂任务集成"""

    def setup_method(self):
        self.plugins = MockPluginManager()
        self.engine = DecisionEngineV2(self.plugins)

    def teardown_method(self):
        self.engine.complex_handler.shutdown()

    def test_complex_task_executed_via_handler(self):
        task = Task(name="complex", description="fetch weather then analyze it")
        result = self.engine.execute_task(task)
        assert result.success is True
        assert task.status.value == "completed"

    def test_simple_task_executed_normally(self):
        def execute_fn() -> TaskResult:
            return TaskResult(success=True, message="ok")
        task = Task(name="simple", description="just run", execute_fn=execute_fn)
        result = self.engine.execute_task(task)
        assert result.success is True
        assert result.message == "ok"

    def test_simple_task_no_execute_fn(self):
        task = Task(name="simple", description="just run")
        result = self.engine.execute_task(task)
        assert result.success is False
        assert "No execute function" in result.message


class TestDAGResultRefs:
    """测试DAG结果引用"""

    def test_ref_resolution(self):
        from src.left.action.execution.dag_executor import DAGExecutor
        executor = DAGExecutor(MockPluginManager())
        plan = DAGPlan()
        plan.add_node(DAGNode(id="a", name="a", action="x", plugin_name="http_plugin"))
        plan.add_node(DAGNode(
            id="b", name="b", action="x", plugin_name="llm_plugin",
            dependencies={"a"}, params={"text": {"$ref": "a.content"}}
        ))
        result = executor.execute(plan)
        executor.shutdown()
        assert result["failed"] == 0
        node_b = plan.nodes["b"]
        assert node_b.result is not None
        assert "weather data" in node_b.result.data.get("content", "")

    def test_ref_missing_node(self):
        from src.left.action.execution.dag_executor import DAGExecutor
        executor = DAGExecutor(MockPluginManager())
        plan = DAGPlan()
        plan.add_node(DAGNode(
            id="b", name="b", action="x", plugin_name="llm_plugin",
            params={"text": {"$ref": "missing.content"}}
        ))
        result = executor.execute(plan)
        executor.shutdown()
        assert result["failed"] == 0
        assert result["success"] == 1

"""
复杂任务处理器

第一性原理：复杂任务必须被识别、分解、编排、执行
- 识别：判断任务是否需要分解
- 分解：生成DAG执行计划
- 编排：按依赖顺序调度执行
- 回退：分解失败时降级为单任务执行

类比：生物的"复杂行为序列"——筑巢需要收集材料、编织、加固多个步骤
"""

from typing import Dict, Any, Optional

from ....platform.support.models.base.task import Task, TaskResult
from ....platform.support.models.base.dag import DAGPlan
from ....platform.lifecycle.memory.plugin_manager import PluginManager
from .task_dag_planner import CompositeTaskDecomposer
from ..execution.dag_executor import DAGExecutor


class ComplexTaskHandler:
    """
    复杂任务处理器

    将复杂任务自动分解为DAG并执行
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        decomposer: Optional[CompositeTaskDecomposer] = None,
        max_workers: int = 4,
    ) -> None:
        self.decomposer = decomposer or CompositeTaskDecomposer([])
        self.dag_executor = DAGExecutor(plugin_manager, max_workers=max_workers)

    def is_complex(self, task: Task) -> bool:
        """判断任务是否为复杂任务"""
        return self.decomposer.can_decompose(task)

    def handle(self, task: Task) -> TaskResult:
        """处理复杂任务"""
        plan = self.decomposer.decompose(task)
        if self._is_single_node(plan):
            return self._fallback_result(task)
        return self._execute_plan(plan, task)

    def _is_single_node(self, plan: DAGPlan) -> bool:
        """检查是否为单节点计划"""
        return len(plan.nodes) <= 1

    def _execute_plan(self, plan: DAGPlan, task: Task) -> TaskResult:
        """执行DAG计划"""
        result = self.dag_executor.execute(plan)
        return self._build_task_result(plan, result, task)

    def _build_task_result(
        self,
        plan: DAGPlan,
        dag_result: Dict[str, Any],
        task: Task,
    ) -> TaskResult:
        """构建任务结果"""
        success = dag_result["failed"] == 0
        message = self._build_message(plan, dag_result, success)
        return TaskResult(
            success=success,
            message=message,
            data=dag_result,
            execution_time=plan.nodes[task.name].duration if task.name in plan.nodes else 0.0,
        )

    def _build_message(self, plan: DAGPlan, dag_result: Dict[str, Any], success: bool) -> str:
        """构建结果消息"""
        total = dag_result["total_nodes"]
        completed = dag_result["success"]
        if success:
            return f"Complex task completed: {completed}/{total} nodes"
        return f"Complex task partial failure: {completed}/{total} nodes succeeded"

    def _fallback_result(self, task: Task) -> TaskResult:
        """回退结果"""
        return TaskResult(
            success=False,
            message=f"Task {task.name} could not be decomposed",
        )

    def shutdown(self) -> None:
        """关闭处理器"""
        self.dag_executor.shutdown()

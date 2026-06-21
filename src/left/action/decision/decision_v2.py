"""
生产级自主决策引擎 V2

第一性原理：决策必须完全自主，基于缺口评估和任务打分
支持：插件任务、DAG任务、复杂任务评分

类比：生物的"前额叶皮层"——评估选项、做出选择、执行决策
"""

import random
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable

from ....platform.support.models.base.state import EnvironmentState, GapState, DriveWeights, DriveType
from ....platform.support.models.base.task import Task, TaskPool, TaskResult, TaskStatus, TaskPriority
from ....platform.support.models.base.dag import DAGPlan, DAGNode
from ....platform.lifecycle.memory.plugin_manager import PluginManager
from .task_dag_planner import CompositeTaskDecomposer, RuleBasedTaskDecomposer
from .complex_task_handler import ComplexTaskHandler


logger = logging.getLogger(__name__)


class DecisionEngineV2:
    """
    生产级决策引擎 V2

    支持插件任务和DAG任务的决策
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        base_exploration_ratio: float = 0.3,
        min_exploration_ratio: float = 0.1,
        max_exploration_ratio: float = 0.5,
    ) -> None:
        self._init_params(plugin_manager, base_exploration_ratio, min_exploration_ratio, max_exploration_ratio)
        self._init_counters()
        logger.info(f"DecisionEngineV2 initialized: exploration={base_exploration_ratio}")

    def _init_params(self, plugin_manager: PluginManager, base: float, min_r: float, max_r: float) -> None:
        self.plugin_manager = plugin_manager
        self.base_exploration_ratio = base
        self.min_exploration_ratio = min_r
        self.max_exploration_ratio = max_r
        self.current_exploration_ratio = base
        self.complex_handler = self._create_complex_handler(plugin_manager)

    def _create_complex_handler(self, plugin_manager: PluginManager) -> ComplexTaskHandler:
        """创建复杂任务处理器"""
        decomposer = CompositeTaskDecomposer([RuleBasedTaskDecomposer()])
        return ComplexTaskHandler(plugin_manager, decomposer=decomposer)

    def _init_counters(self) -> None:
        self.exploration_count = 0
        self.exploitation_count = 0

    def _create_plugin_task(
        self,
        name: str,
        plugin: str,
        action: str,
        params: Dict[str, Any],
        drive: str = "gain",
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> Task:
        """创建插件任务"""
        def execute_fn() -> TaskResult:
            result = self.plugin_manager.execute(plugin, action, params)
            return TaskResult(
                success=result.success,
                message=result.message,
                data=result.data,
                execution_time=result.execution_time,
            )
        return Task(
            name=name,
            description=f"{plugin}.{action}",
            target_drive=drive,
            priority=priority,
            execute_fn=execute_fn,
        )

    def _create_file_read_task(self, path: str) -> Task:
        """创建文件读取任务"""
        return self._create_plugin_task(
            name=f"read_file_{path}",
            plugin="file_plugin",
            action="read",
            params={"path": path},
            drive="gain",
        )

    def _create_file_write_task(self, path: str, content: str) -> Task:
        """创建文件写入任务"""
        return self._create_plugin_task(
            name=f"write_file_{path}",
            plugin="file_plugin",
            action="write",
            params={"path": path, "content": content},
            drive="gain",
        )

    def _create_http_get_task(self, url: str) -> Task:
        """创建HTTP GET任务"""
        return self._create_plugin_task(
            name=f"http_get_{url[:30]}",
            plugin="http_plugin",
            action="get",
            params={"url": url},
            drive="gain",
        )

    def _create_db_query_task(self, sql: str) -> Task:
        """创建数据库查询任务"""
        return self._create_plugin_task(
            name=f"db_query_{sql[:30]}",
            plugin="database_plugin",
            action="query",
            params={"sql": sql},
            drive="gain",
        )

    def _create_code_task(self, code: str) -> Task:
        """创建代码执行任务"""
        return self._create_plugin_task(
            name="execute_code",
            plugin="code_plugin",
            action="run_python",
            params={"code": code},
            drive="gain",
            priority=TaskPriority.HIGH,
        )

    def _create_tool_calculate_task(self, expression: str) -> Task:
        """创建计算任务"""
        return self._create_plugin_task(
            name=f"calculate_{expression[:20]}",
            plugin="tool_plugin",
            action="calculate",
            params={"expression": expression},
            drive="eff",
        )

    def _create_safety_monitor_task(self, state: EnvironmentState) -> Task:
        """创建安全监控任务"""
        return self._create_plugin_task(
            name="monitor_resources",
            plugin="tool_plugin",
            action="time",
            params={"format": "iso"},
            drive="safe",
            priority=TaskPriority.HIGH,
        )

    def generate_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """
        根据缺口动态生成生产级任务
        """
        tasks: List[Task] = []
        self._maybe_add_safety(tasks, gaps, state)
        self._maybe_add_gain(tasks, gaps, state)
        self._maybe_add_efficiency(tasks, gaps)
        self._ensure_fallback(tasks)
        return tasks

    def _maybe_add_safety(self, tasks: List[Task], gaps: GapState, state: EnvironmentState) -> None:
        """添加安全相关任务"""
        if gaps.safety > 0.3:
            tasks.append(self._create_safety_monitor_task(state))

    def _maybe_add_gain(self, tasks: List[Task], gaps: GapState, state: EnvironmentState) -> None:
        """添加收益相关任务"""
        if gaps.gain > 0.3:
            tasks.append(self._create_file_read_task("logs/agent.log"))
            tasks.append(self._create_http_get_task("https://httpbin.org/get"))
            tasks.append(self._create_tool_calculate_task("2 + 2"))

    def _maybe_add_efficiency(self, tasks: List[Task], gaps: GapState) -> None:
        """添加能效相关任务"""
        if gaps.efficiency > 0.3:
            tasks.append(self._create_code_task("print('hello world')"))

    def _ensure_fallback(self, tasks: List[Task]) -> None:
        """确保有保底任务"""
        if not tasks:
            tasks.append(self._create_tool_calculate_task("1 + 1"))

    def _compute_gap_match(self, task: Task, gaps: GapState) -> float:
        """计算缺口匹配度"""
        if task.target_drive == "safe":
            return gaps.safety
        elif task.target_drive == "gain":
            return gaps.gain
        elif task.target_drive == "eff":
            return gaps.efficiency
        return 0.0

    def _compute_urgency(self, task: Task) -> float:
        """计算紧急程度"""
        return 1.0 - (task.priority.value / 4.0)

    def _compute_novelty(self, task: Task) -> float:
        """计算新颖性"""
        return 0.3 if task.is_exploration else 0.0

    def _compute_cost(self, task: Task) -> float:
        """计算成本"""
        return (task.max_cpu_usage + task.max_memory_usage) / 2.0

    def _compute_expired_bonus(self, task: Task) -> float:
        """计算过期奖励"""
        return 1.0 if task.is_expired else 0.0

    def _compute_raw_score(
        self,
        gap_match: float,
        urgency: float,
        success_rate: float,
        novelty: float,
        cost: float,
        expired_bonus: float,
    ) -> float:
        """计算原始分数"""
        return (
            0.25 * gap_match +
            0.20 * urgency +
            0.20 * success_rate +
            0.15 * novelty -
            0.10 * cost +
            0.10 * expired_bonus
        )

    def score_task(self, task: Task, gaps: GapState, weights: DriveWeights) -> float:
        """任务评分函数"""
        components = self._score_components(task, gaps)
        score = self._compute_raw_score(*components)
        return max(0.0, min(1.0, score))

    def _score_components(self, task: Task, gaps: GapState) -> tuple:
        """提取评分组件"""
        return (
            self._compute_gap_match(task, gaps),
            self._compute_urgency(task),
            task.success_rate,
            self._compute_novelty(task),
            self._compute_cost(task),
            self._compute_expired_bonus(task),
        )

    def select_next_task(
        self,
        task_pool: TaskPool,
        gaps: GapState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        """
        选择下一个任务
        """
        pending = task_pool.get_pending_tasks()
        if not pending:
            new_tasks = self.generate_tasks(gaps, EnvironmentState())
            for task in new_tasks:
                task_pool.add_task(task)
            pending = task_pool.get_pending_tasks()
        if not pending:
            return None
        scored = [(self.score_task(t, gaps, weights), t) for t in pending]
        scored.sort(reverse=True, key=lambda x: x[0])
        if random.random() < self.current_exploration_ratio:
            return self._explore_select(scored)
        return self._exploit_select(scored)

    def _explore_select(self, scored_tasks: List[tuple]) -> Optional[Task]:
        """探索策略"""
        self.exploration_count += 1
        candidates = scored_tasks[-3:]
        if candidates:
            selected = random.choice(candidates)[1]
            selected.is_exploration = True
            logger.info(f"Exploration: selected {selected.name}")
            return selected
        return None

    def _exploit_select(self, scored_tasks: List[tuple]) -> Task:
        """利用策略"""
        self.exploitation_count += 1
        selected = scored_tasks[0][1]
        logger.info(f"Exploitation: selected {selected.name}")
        return selected

    def execute_task(self, task: Task) -> TaskResult:
        """执行任务"""
        if self.complex_handler.is_complex(task):
            return self._execute_complex(task)
        return self._execute_simple(task)

    def _execute_complex(self, task: Task) -> TaskResult:
        """执行复杂任务"""
        result = self.complex_handler.handle(task)
        self._complete_task(task, result)
        return result

    def _execute_simple(self, task: Task) -> TaskResult:
        """执行简单任务"""
        if task.execute_fn is None:
            return TaskResult(success=False, message="No execute function defined")
        task.start()
        try:
            result = task.execute_fn()
            self._complete_task(task, result)
            return result
        except Exception as e:
            result = TaskResult(success=False, message=str(e))
            self._complete_task(task, result)
            return result

    def _complete_task(self, task: Task, result: TaskResult) -> None:
        """完成任务"""
        task.complete(result)
        logger.info(f"Task {task.name} completed: {result.success}")

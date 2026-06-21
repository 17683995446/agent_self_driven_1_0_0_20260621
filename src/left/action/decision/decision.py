"""
自主决策引擎

第一性原理：决策必须完全自主，基于缺口评估和任务打分
类比：生物的"前额叶皮层"——评估选项、做出选择、执行决策
"""

import random
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable, Tuple

from ....platform.support.models.base.state import EnvironmentState, GapState, DriveWeights, DriveType
from ....platform.support.models.base.task import Task, TaskPool, TaskResult, TaskStatus, TaskPriority
from ....platform.lifecycle.memory.plugin_manager import PluginManager


logger = logging.getLogger(__name__)


class DecisionEngineBase(ABC):
    """决策引擎抽象基类"""

    @abstractmethod
    def generate_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """根据缺口动态生成任务"""
        pass

    @abstractmethod
    def select_next_task(
        self,
        task_pool: TaskPool,
        gaps: GapState,
        weights: DriveWeights
    ) -> Optional[Task]:
        """选择下一个任务"""
        pass


class DecisionEngine(DecisionEngineBase):
    """
    决策引擎

    系统的"前额叶皮层"，负责：
    1. 评估候选任务
    2. 选择最优任务
    3. 平衡探索与利用
    4. 处理任务中断

    第一性原理：
    - 决策必须完全自主
    - 评分机制必须透明
    - 探索利用必须平衡（70%利用/30%探索）
    - 高优先级可中断低优先级

    秩序化（O1）：支持注入真实任务源（RealTaskFactory/DynamicTaskGenerator）
    - 注入后优先使用真实任务，占位任务作为兜底
    - 未注入时保持原有占位行为（向后兼容）

    秩序化（O3）：支持注入TaskFeedbackLearner
    - 执行后记录结果到学习器
    - 选择任务时过滤暂停任务、调整优先级

    秩序化（O4）：支持注入PredictionCorrectionLoop
    - 每轮预测下一时刻误差
    - 用实际状态误差修正预测
    - 误差趋势驱动探索比例调整
    - 误差回填到感知层
    """

    def __init__(
        self,
        plugin_manager: Optional[PluginManager] = None,
        base_exploration_ratio: float = 0.3,
        min_exploration_ratio: float = 0.1,
        max_exploration_ratio: float = 0.5,
        real_task_factory: Optional[Any] = None,
        dynamic_task_generator: Optional[Any] = None,
        feedback_learner: Optional[Any] = None,
        prediction_correction_loop: Optional[Any] = None,
        circuit_breaker: Optional[Any] = None,
        state_feedback_channel: Optional[Any] = None,
    ) -> None:
        self._init_params(plugin_manager, base_exploration_ratio, min_exploration_ratio, max_exploration_ratio)
        self._init_counters()
        self._real_task_factory = real_task_factory
        self._dynamic_task_generator = dynamic_task_generator
        self._feedback_learner = feedback_learner
        self._prediction_correction_loop = prediction_correction_loop
        self._circuit_breaker = circuit_breaker
        self._state_feedback_channel = state_feedback_channel
        logger.info(f"Decision engine initialized: exploration={base_exploration_ratio}, "
                    f"real_factory={real_task_factory is not None}, "
                    f"dynamic_gen={dynamic_task_generator is not None}, "
                    f"feedback_learner={feedback_learner is not None}, "
                    f"prediction_loop={prediction_correction_loop is not None}, "
                    f"circuit_breaker={circuit_breaker is not None}")

    def _init_params(self, plugin_manager: Optional[PluginManager], base: float, min_r: float, max_r: float) -> None:
        self.plugin_manager = plugin_manager
        self.base_exploration_ratio = base
        self.min_exploration_ratio = min_r
        self.max_exploration_ratio = max_r
        self.current_exploration_ratio = base

    def _init_counters(self) -> None:
        self.exploration_count = 0
        self.exploitation_count = 0

    def _monitor_task(self, gaps: GapState, state: EnvironmentState) -> Task:
        priority = TaskPriority.HIGH if gaps.safety > 0.5 else TaskPriority.NORMAL
        return Task(
            name="monitor_system_resources",
            description="监控系统资源使用情况",
            target_drive="safe",
            priority=priority,
            execute_fn=self._create_monitor_task(state)
        )

    def _error_check_task(self) -> Task:
        return Task(
            name="check_system_errors",
            description="检查系统错误日志",
            target_drive="safe",
            priority=TaskPriority.NORMAL,
            execute_fn=self._create_error_check_task()
        )

    def _create_safety_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建安全相关任务"""
        return [
            self._monitor_task(gaps, state),
            self._error_check_task(),
        ]

    def _create_gain_tasks(self) -> List[Task]:
        """创建收益相关任务"""
        return [Task(
            name="explore_new_patterns",
            description="探索新的系统行为模式",
            target_drive="gain",
            priority=TaskPriority.EXPLORATION,
            is_exploration=True,
            execute_fn=self._create_exploration_task()
        )]

    def _create_efficiency_tasks(self) -> List[Task]:
        """创建能效相关任务"""
        return [Task(
            name="optimize_resource_usage",
            description="优化资源使用效率",
            target_drive="eff",
            priority=TaskPriority.LOW,
            execute_fn=self._create_optimization_task()
        )]

    def _create_fallback_task(self) -> List[Task]:
        """创建保底任务"""
        return [Task(
            name="idle_observation",
            description="空闲观察，收集环境数据",
            target_drive="gain",
            priority=TaskPriority.LOW,
            execute_fn=self._create_observation_task()
        )]

    def _maybe_add_safety(self, tasks: List[Task], gaps: GapState, state: EnvironmentState) -> None:
        if gaps.safety > 0.3:
            tasks.extend(self._create_safety_tasks(gaps, state))

    def _maybe_add_gain(self, tasks: List[Task], gaps: GapState) -> None:
        if gaps.gain > 0.3:
            tasks.extend(self._create_gain_tasks())

    def _maybe_add_efficiency(self, tasks: List[Task], gaps: GapState) -> None:
        if gaps.efficiency > 0.3:
            tasks.extend(self._create_efficiency_tasks())

    def _ensure_fallback(self, tasks: List[Task]) -> None:
        if not tasks:
            tasks.extend(self._create_fallback_task())

    def _collect_real_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """从真实任务源收集任务（秩序化O1）"""
        tasks: List[Task] = []
        if self._real_task_factory is not None:
            tasks.extend(self._real_task_factory.create_tasks(gaps, state))
        if self._dynamic_task_generator is not None:
            tasks.extend(self._dynamic_task_generator.generate_tasks(gaps, state))
        return tasks

    def generate_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """
        根据缺口动态生成任务

        第一性原理：任务必须内生，根据缺口自动生成
        秩序化（O1）：优先使用真实任务源，占位任务作为兜底
        """
        real_tasks = self._collect_real_tasks(gaps, state)
        if real_tasks:
            return real_tasks
        tasks: List[Task] = []
        self._maybe_add_safety(tasks, gaps, state)
        self._maybe_add_gain(tasks, gaps)
        self._maybe_add_efficiency(tasks, gaps)
        self._ensure_fallback(tasks)
        return tasks

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
        expired_bonus: float
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

    def _collect_task_features(self, task: Task, gaps: GapState) -> Dict[str, float]:
        return {
            "gap_match": self._compute_gap_match(task, gaps),
            "urgency": self._compute_urgency(task),
            "success_rate": task.success_rate,
            "novelty": self._compute_novelty(task),
            "cost": self._compute_cost(task),
            "expired_bonus": self._compute_expired_bonus(task),
        }

    def score_task(self, task: Task, gaps: GapState, weights: DriveWeights) -> float:
        """
        任务评分函数

        Score = w1 * GapMatch + w2 * ExpectedReward + w3 * Urgency
                + w4 * SuccessRate - w5 * Cost + w6 * Novelty
        """
        f = self._collect_task_features(task, gaps)
        score = self._compute_raw_score(
            f["gap_match"], f["urgency"], f["success_rate"],
            f["novelty"], f["cost"], f["expired_bonus"]
        )
        return max(0.0, min(1.0, score))

    def _generate_and_add(self, task_pool: TaskPool, gaps: GapState) -> None:
        logger.info("No pending tasks, generating new tasks")
        new_tasks = self.generate_tasks(gaps, EnvironmentState())
        for task in new_tasks:
            task_pool.add_task(task)

    def _filter_available_tasks(self, tasks: List[Task]) -> List[Task]:
        """过滤可用任务（秩序化O3：反馈学习过滤暂停任务）"""
        if self._feedback_learner is None:
            return tasks
        return [t for t in tasks if self._feedback_learner.is_task_available(t.name)]

    def _adjust_priorities(self, tasks: List[Task]) -> None:
        """调整任务优先级（秩序化O3：反馈学习调整优先级）"""
        if self._feedback_learner is None:
            return
        for task in tasks:
            self._feedback_learner.adjust_task_priority(task)

    def _get_pending_or_generate(
        self,
        task_pool: TaskPool,
        gaps: GapState
    ) -> List[Task]:
        """获取待执行任务，如果没有则生成新任务"""
        pending = task_pool.get_pending_tasks()
        if not pending:
            self._generate_and_add(task_pool, gaps)
            pending = task_pool.get_pending_tasks()
        return self._filter_available_tasks(pending)

    def _append_score(self, scored: List[Tuple[float, Task]], task: Task, gaps: GapState, weights: DriveWeights) -> None:
        score = self.score_task(task, gaps, weights)
        scored.append((score, task))

    def _score_tasks(
        self,
        tasks: List[Task],
        gaps: GapState,
        weights: DriveWeights
    ) -> List[Tuple[float, Task]]:
        """为所有任务评分"""
        scored: List[Tuple[float, Task]] = []
        for task in tasks:
            self._append_score(scored, task, gaps, weights)
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored

    def _explore_select(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        """探索策略：选择得分较低但有潜力的任务"""
        self.exploration_count += 1
        candidates = scored_tasks[-3:]
        if candidates:
            selected = random.choice(candidates)[1]
            selected.is_exploration = True
            logger.info(f"Exploration: selected {selected.name}")
            return selected
        return None

    def _exploit_select(self, scored_tasks: List[Tuple[float, Task]]) -> Task:
        """利用策略：选择得分最高的任务"""
        self.exploitation_count += 1
        selected = scored_tasks[0][1]
        logger.info(f"Exploitation: selected {selected.name}")
        return selected

    def _select_by_strategy(self, scored_tasks: List[Tuple[float, Task]]) -> Optional[Task]:
        if random.random() < self.current_exploration_ratio:
            result = self._explore_select(scored_tasks)
            if result is not None:
                return result
        return self._exploit_select(scored_tasks)

    def select_next_task(
        self,
        task_pool: TaskPool,
        gaps: GapState,
        weights: DriveWeights
    ) -> Optional[Task]:
        """
        选择下一个任务

        双决策机制：
        1. 70% 利用：选择当前得分最高任务
        2. 30% 探索：选择低得分陌生任务
        """
        pending_tasks = self._get_pending_or_generate(task_pool, gaps)
        if not pending_tasks:
            return None
        scored_tasks = self._score_tasks(pending_tasks, gaps, weights)
        return self._select_by_strategy(scored_tasks)

    def _execute_fn(self, task: Task) -> TaskResult:
        """执行任务的执行函数"""
        return task.execute_fn()

    def _run_execute(self, task: Task) -> TaskResult:
        """运行执行函数并计时"""
        start_time = time.time()
        result = self._execute_fn(task)
        result.execution_time = time.time() - start_time
        return result

    def _handle_execute_exception(self, task: Task, exc: Exception) -> TaskResult:
        """处理执行异常"""
        logger.error(f"Task {task.name} failed: {exc}")
        return TaskResult(success=False, message=str(exc))

    def _execute_with_result(self, task: Task) -> TaskResult:
        result = self._run_execute(task)
        task.complete(result)
        logger.info(f"Task {task.name} completed: {result.success}")
        return result

    def _execute_with_fallback(self, task: Task, exc: Exception) -> TaskResult:
        result = self._handle_execute_exception(task, exc)
        task.complete(result)
        return result

    def _record_feedback(self, task: Task, result: TaskResult) -> None:
        """记录反馈到学习器（秩序化O3）"""
        if self._feedback_learner is None:
            return
        try:
            self._feedback_learner.record_result(task.name, result)
        except Exception as e:
            logger.warning(f"Feedback learner record failed: {e}")

    def _check_circuit_breaker(self, task: Task) -> Optional[TaskResult]:
        """检查熔断器是否允许执行（秩序化O8）"""
        if self._circuit_breaker is None:
            return None
        try:
            if not self._circuit_breaker.can_execute():
                logger.warning(f"Circuit breaker open, skipping task: {task.name}")
                return TaskResult(
                    success=False,
                    message=f"Circuit breaker open, task skipped: {task.name}",
                )
        except Exception as e:
            logger.warning(f"Circuit breaker check failed: {e}")
        return None

    def _record_circuit_breaker_result(self, result: TaskResult) -> None:
        """记录执行结果到熔断器（秩序化O8）"""
        if self._circuit_breaker is None:
            return
        try:
            if result.success:
                self._circuit_breaker.record_success()
            else:
                self._circuit_breaker.record_failure()
        except Exception as e:
            logger.warning(f"Circuit breaker record failed: {e}")

    def _record_state_feedback(self, task: Task, result: TaskResult) -> None:
        """记录状态反馈到回填通道（秩序化O9）"""
        if self._state_feedback_channel is None:
            return
        try:
            self._state_feedback_channel.update_from_result(task.name, result)
        except Exception as e:
            logger.warning(f"State feedback record failed: {e}")

    def execute_task(self, task: Task) -> TaskResult:
        """
        执行任务

        第一性原理：执行是决策的闭环，必须有反馈
        秩序化（O3）：执行后记录到反馈学习器
        秩序化（O8）：执行前检查熔断器，执行后记录熔断器
        秩序化（O9）：执行后回填状态到感知层
        """
        if task.execute_fn is None:
            return TaskResult(success=False, message="No execute function defined")
        skipped = self._check_circuit_breaker(task)
        if skipped is not None:
            return skipped
        task.start()
        try:
            result = self._execute_with_result(task)
            self._record_feedback(task, result)
            self._record_circuit_breaker_result(result)
            self._record_state_feedback(task, result)
            return result
        except Exception as e:
            result = self._execute_with_fallback(task, e)
            self._record_feedback(task, result)
            self._record_circuit_breaker_result(result)
            self._record_state_feedback(task, result)
            return result

    def _increase_exploration(self) -> None:
        """增加探索比例"""
        self.current_exploration_ratio = min(
            self.max_exploration_ratio,
            self.current_exploration_ratio + 0.05
        )

    def _decrease_exploration(self) -> None:
        """减少探索比例"""
        self.current_exploration_ratio = max(
            self.min_exploration_ratio,
            self.current_exploration_ratio - 0.02
        )

    def _apply_exploration_adjustment(self, error_trend: float, stagnation_detected: bool) -> None:
        if stagnation_detected:
            self._increase_exploration()
        elif error_trend > 0:
            self._decrease_exploration()
        elif error_trend < 0:
            self._increase_exploration()

    def update_exploration_ratio(
        self,
        error_trend: float,
        stagnation_detected: bool = False
    ) -> None:
        """
        动态调整探索比例

        第一性原理：稳态时增加探索，动荡时减少探索
        """
        self._apply_exploration_adjustment(error_trend, stagnation_detected)
        logger.debug(f"Exploration ratio updated: {self.current_exploration_ratio:.3f}")

    def predict_next_error(self, state: EnvironmentState) -> float:
        """
        预测下一时刻误差（秩序化O4）

        第一性原理：智能 = 预测 + 修正 + 误差驱动进化
        基于历史误差预测下一时刻误差值
        """
        if self._prediction_correction_loop is None:
            return 0.0
        try:
            return self._prediction_correction_loop.predict(state)
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return 0.0

    def compute_state_error(self, state: EnvironmentState) -> float:
        """
        从状态向量计算实际误差（秩序化O4）

        第一性原理：状态向量偏离理想（零负载）的程度即为系统误差
        使用L2范数归一化到[0, 1]
        """
        vector = state.to_vector()
        if not vector:
            return 0.0
        sum_sq = sum(v * v for v in vector)
        dim = len(vector)
        return min(1.0, (sum_sq / dim) ** 0.5)

    def correct_prediction(
        self,
        predicted: float,
        actual: float,
        timestamp: float = 0.0,
    ) -> None:
        """
        修正预测误差（秩序化O4）

        第一性原理：比较预测与实际，记录误差以驱动学习
        """
        if self._prediction_correction_loop is None:
            return
        try:
            self._prediction_correction_loop.correct(predicted, actual, timestamp)
        except Exception as e:
            logger.warning(f"Prediction correction failed: {e}")

    def _trend_to_value(self, trend: Any) -> float:
        """将误差趋势转换为数值（rising=正，falling=负，stable=0）"""
        direction = getattr(trend, "direction", "stable")
        magnitude = abs(getattr(trend, "magnitude", 0.0))
        if direction == "rising":
            return magnitude
        if direction == "falling":
            return -magnitude
        return 0.0

    def adjust_exploration_by_error(self) -> None:
        """
        根据误差趋势调整探索比例（秩序化O4）

        第一性原理：误差上升→减少探索（安全优先），误差下降→增加探索（收益优先）
        """
        if self._prediction_correction_loop is None:
            return
        try:
            trend = self._prediction_correction_loop.get_last_trend()
            error_trend_value = self._trend_to_value(trend)
            self.update_exploration_ratio(error_trend_value, stagnation_detected=False)
        except Exception as e:
            logger.warning(f"Exploration adjustment by error failed: {e}")

    def get_prediction_drive_weights(self) -> Optional[DriveWeights]:
        """
        获取预测驱力权重（秩序化O4）

        第一性原理：误差驱动任务类别权重，高误差→安全优先，低误差→探索优先
        """
        if self._prediction_correction_loop is None:
            return None
        try:
            return self._prediction_correction_loop.get_drive_weights()
        except Exception as e:
            logger.warning(f"Get prediction drive weights failed: {e}")
            return None

    def get_current_prediction_error(self) -> float:
        """
        获取当前预测误差（秩序化O4）

        用于回填到感知层SelfState.prediction_error
        """
        if self._prediction_correction_loop is None:
            return 0.0
        try:
            last_error = self._prediction_correction_loop.get_last_error()
            if last_error is None:
                return 0.0
            return getattr(last_error, "relative_error", 0.0)
        except Exception as e:
            logger.warning(f"Get current prediction error failed: {e}")
            return 0.0

    def _plugin_execute(self, plugin: str, action: str, params: Dict[str, Any]) -> TaskResult:
        """通过插件管理器执行任务"""
        if self.plugin_manager is None:
            return TaskResult(success=False, message="Plugin manager not available")
        plugin_result = self.plugin_manager.execute(plugin, action, params)
        return TaskResult(
            success=plugin_result.success,
            message=plugin_result.message,
            data=plugin_result.data,
            execution_time=plugin_result.execution_time,
        )

    def _create_monitor_task(self, state: EnvironmentState) -> Callable[[], TaskResult]:
        """创建监控任务"""
        def monitor() -> TaskResult:
            return self._plugin_execute("tool_plugin", "time", {"format": "iso"})
        return monitor

    def _create_error_check_task(self) -> Callable[[], TaskResult]:
        """创建错误检查任务"""
        def check_errors() -> TaskResult:
            return self._plugin_execute("code_plugin", "run_python", {"code": "import sys; print(sys.version)"})
        return check_errors

    def _create_exploration_task(self) -> Callable[[], TaskResult]:
        """创建探索任务"""
        def explore() -> TaskResult:
            return self._plugin_execute("tool_plugin", "calculate", {"expression": "random()"})
        return explore

    def _create_optimization_task(self) -> Callable[[], TaskResult]:
        """创建优化任务"""
        def optimize() -> TaskResult:
            return self._plugin_execute("tool_plugin", "count_tokens", {"text": "optimize resource usage"})
        return optimize

    def _create_observation_task(self) -> Callable[[], TaskResult]:
        """创建观察任务"""
        def observe() -> TaskResult:
            return self._plugin_execute("tool_plugin", "time", {})
        return observe

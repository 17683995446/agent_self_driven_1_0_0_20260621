"""
动态任务生成器

第一性原理：任务生成必须随环境状态自适应
- 环境状态变化 → 任务类型变化
- 高压力场景 → 优先安全/效率任务
- 低压力场景 → 优先探索任务

类比：生物的"应激反应"——环境刺激决定行为模式
- 危险 → 战斗/逃跑（安全任务）
- 饥饿 → 觅食（收益任务）
- 疲劳 → 休息（效率任务）
- 安全 → 探索（探索任务）

核心机制：
1. EnvironmentState各维度触发不同任务工厂
2. 多维度同时触发时按优先级合并
3. 空闲状态自动生成探索任务，避免空转
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import (
    DriveType,
    DriveWeights,
    EnvironmentState,
    GapState,
    LogState,
    SelfState,
    SystemState,
    FileState,
)
from ....platform.support.models.base.task import Task, TaskPriority, TaskResult


logger = logging.getLogger(__name__)


# 触发阈值
CPU_HIGH_THRESHOLD: float = 0.80
MEMORY_HIGH_THRESHOLD: float = 0.85
DISK_HIGH_THRESHOLD: float = 0.90
ERROR_RATE_HIGH_THRESHOLD: float = 0.10
WARNING_RATE_HIGH_THRESHOLD: float = 0.30
PREDICTION_ERROR_HIGH_THRESHOLD: float = 0.30
IDLE_ALL_THRESHOLD: float = 0.20


@dataclass(frozen=True)
class EnvironmentTrigger:
    """环境触发器

    第一性原理：触发器 = 环境维度 + 阈值 + 触发结果
    """

    dimension: str
    value: float
    threshold: float
    triggered: bool
    rule_name: str = ""

    def describe(self) -> str:
        """描述触发器状态"""
        status = "TRIGGERED" if self.triggered else "ok"
        return f"{self.dimension}={self.value:.3f} {status} (threshold={self.threshold})"


class TriggerRule(ABC):
    """触发规则抽象基类"""

    @abstractmethod
    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        """评估环境状态，返回触发器"""
        pass

    @abstractmethod
    def rule_name(self) -> str:
        """规则名称"""
        pass


class CpuHighRule(TriggerRule):
    """CPU高负载规则"""

    def rule_name(self) -> str:
        return "cpu_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.system.cpu_overall
        return EnvironmentTrigger(
            dimension="cpu_overall",
            value=value,
            threshold=CPU_HIGH_THRESHOLD,
            triggered=value >= CPU_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class MemoryHighRule(TriggerRule):
    """内存高负载规则"""

    def rule_name(self) -> str:
        return "memory_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.system.memory_usage
        return EnvironmentTrigger(
            dimension="memory_usage",
            value=value,
            threshold=MEMORY_HIGH_THRESHOLD,
            triggered=value >= MEMORY_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class DiskHighRule(TriggerRule):
    """磁盘高使用规则"""

    def rule_name(self) -> str:
        return "disk_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.system.disk_usage
        return EnvironmentTrigger(
            dimension="disk_usage",
            value=value,
            threshold=DISK_HIGH_THRESHOLD,
            triggered=value >= DISK_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class ErrorRateHighRule(TriggerRule):
    """错误率高规则"""

    def rule_name(self) -> str:
        return "error_rate_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.logs.error_rate
        return EnvironmentTrigger(
            dimension="logs.error_rate",
            value=value,
            threshold=ERROR_RATE_HIGH_THRESHOLD,
            triggered=value >= ERROR_RATE_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class WarningRateHighRule(TriggerRule):
    """警告率高规则"""

    def rule_name(self) -> str:
        return "warning_rate_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.logs.warning_rate
        return EnvironmentTrigger(
            dimension="logs.warning_rate",
            value=value,
            threshold=WARNING_RATE_HIGH_THRESHOLD,
            triggered=value >= WARNING_RATE_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class PredictionErrorHighRule(TriggerRule):
    """预测误差高规则"""

    def rule_name(self) -> str:
        return "prediction_error_high"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        value = state.self.prediction_error
        return EnvironmentTrigger(
            dimension="self.prediction_error",
            value=value,
            threshold=PREDICTION_ERROR_HIGH_THRESHOLD,
            triggered=value >= PREDICTION_ERROR_HIGH_THRESHOLD,
            rule_name=self.rule_name(),
        )


class IdleRule(TriggerRule):
    """空闲状态规则

    第一性原理：所有维度都低于阈值时，触发探索任务
    """

    def rule_name(self) -> str:
        return "idle"

    def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
        dims = self._collect_idle_dims(state)
        max_value = max(dims)
        triggered = max_value < IDLE_ALL_THRESHOLD
        return EnvironmentTrigger(
            dimension="idle_max",
            value=max_value,
            threshold=IDLE_ALL_THRESHOLD,
            triggered=triggered,
            rule_name=self.rule_name(),
        )

    def _collect_idle_dims(self, state: EnvironmentState) -> List[float]:
        """收集空闲判断维度"""
        return [
            state.system.cpu_overall,
            state.system.memory_usage,
            state.system.disk_usage,
            state.logs.error_rate,
            state.logs.warning_rate,
            state.self.prediction_error,
        ]


class TaskGenerationStrategy(ABC):
    """任务生成策略抽象基类

    第一性原理：策略 = 触发器 → 任务列表
    不同触发器对应不同任务生成策略
    """

    @abstractmethod
    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        """根据触发器生成任务"""
        pass

    @abstractmethod
    def strategy_name(self) -> str:
        """策略名称"""
        pass


def _make_noop_execute_fn(label: str) -> Callable[[], TaskResult]:
    """创建空操作执行函数（用于策略生成的占位任务）"""

    def execute() -> TaskResult:
        return TaskResult(
            success=True,
            message=f"dynamic task: {label}",
            data={"label": label, "dynamic": True},
        )

    return execute


class ResourceOptimizationStrategy(TaskGenerationStrategy):
    """资源优化策略

    用于CPU/内存/磁盘高负载场景
    """

    def strategy_name(self) -> str:
        return "resource_optimization"

    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        label = f"optimize_{trigger.dimension}"
        return [Task(
            name=label,
            description=f"Resource optimization for {trigger.describe()}",
            target_drive="eff",
            priority=TaskPriority.HIGH,
            target_gap_reduction=0.2,
            execute_fn=_make_noop_execute_fn(label),
        )]


class LogAnalysisStrategy(TaskGenerationStrategy):
    """日志分析策略

    用于错误率/警告率高场景
    """

    def strategy_name(self) -> str:
        return "log_analysis"

    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        label = f"analyze_{trigger.dimension}"
        return [Task(
            name=label,
            description=f"Log analysis for {trigger.describe()}",
            target_drive="safe",
            priority=TaskPriority.CRITICAL,
            target_gap_reduction=0.3,
            execute_fn=_make_noop_execute_fn(label),
        )]


class DiskCleanupStrategy(TaskGenerationStrategy):
    """磁盘清理策略

    用于磁盘满场景
    """

    def strategy_name(self) -> str:
        return "disk_cleanup"

    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        label = "cleanup_disk"
        return [Task(
            name=label,
            description=f"Disk cleanup for {trigger.describe()}",
            target_drive="eff",
            priority=TaskPriority.CRITICAL,
            target_gap_reduction=0.25,
            execute_fn=_make_noop_execute_fn(label),
        )]


class PredictionCorrectionStrategy(TaskGenerationStrategy):
    """预测修正策略

    用于预测误差高场景
    """

    def strategy_name(self) -> str:
        return "prediction_correction"

    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        label = "correct_prediction"
        return [Task(
            name=label,
            description=f"Prediction correction for {trigger.describe()}",
            target_drive="safe",
            priority=TaskPriority.HIGH,
            target_gap_reduction=0.2,
            execute_fn=_make_noop_execute_fn(label),
        )]


class ExplorationStrategy(TaskGenerationStrategy):
    """探索策略

    用于空闲场景
    """

    def strategy_name(self) -> str:
        return "exploration"

    def generate_tasks(
        self,
        trigger: EnvironmentTrigger,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        label = "explore_idle"
        return [Task(
            name=label,
            description=f"Exploration during idle: {trigger.describe()}",
            target_drive="gain",
            priority=TaskPriority.EXPLORATION,
            target_gap_reduction=0.1,
            is_exploration=True,
            execute_fn=_make_noop_execute_fn(label),
        )]


@dataclass
class GenerationDecision:
    """生成决策记录

    第一性原理：决策可追溯，便于审计和调试
    """

    timestamp: float
    triggers: List[EnvironmentTrigger] = field(default_factory=list)
    strategies_applied: List[str] = field(default_factory=list)
    tasks_generated: int = 0
    state_summary: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "triggers": [t.describe() for t in self.triggers],
            "strategies_applied": self.strategies_applied,
            "tasks_generated": self.tasks_generated,
            "state_summary": self.state_summary,
        }


class DynamicTaskGenerator:
    """
    动态任务生成器

    第一性原理：任务生成 = 环境感知 × 规则匹配 × 策略执行
    - 环境感知：从EnvironmentState提取关键维度
    - 规则匹配：评估触发规则，识别活跃触发器
    - 策略执行：根据触发器选择策略，生成对应任务

    类比：生物的"反射弧"——感受器→神经中枢→效应器
    """

    def __init__(
        self,
        rules: Optional[List[TriggerRule]] = None,
        strategies: Optional[Dict[str, TaskGenerationStrategy]] = None,
    ) -> None:
        self._rules: List[TriggerRule] = rules if rules is not None else self._default_rules()
        self._strategies: Dict[str, TaskGenerationStrategy] = (
            strategies if strategies is not None else self._default_strategies()
        )
        self._last_decision: Optional[GenerationDecision] = None
        self._decision_history: List[GenerationDecision] = []
        self._max_history: int = 100

    def _default_rules(self) -> List[TriggerRule]:
        """默认规则集"""
        return [
            CpuHighRule(),
            MemoryHighRule(),
            DiskHighRule(),
            ErrorRateHighRule(),
            WarningRateHighRule(),
            PredictionErrorHighRule(),
            IdleRule(),
        ]

    def _default_strategies(self) -> Dict[str, TaskGenerationStrategy]:
        """默认策略集"""
        return {
            "cpu_high": ResourceOptimizationStrategy(),
            "memory_high": ResourceOptimizationStrategy(),
            "disk_high": DiskCleanupStrategy(),
            "error_rate_high": LogAnalysisStrategy(),
            "warning_rate_high": LogAnalysisStrategy(),
            "prediction_error_high": PredictionCorrectionStrategy(),
            "idle": ExplorationStrategy(),
        }

    def generate_tasks(
        self,
        gaps: GapState,
        state: EnvironmentState,
    ) -> List[Task]:
        """根据环境状态动态生成任务"""
        triggers = self._evaluate_all_rules(state)
        active_triggers = [t for t in triggers if t.triggered]
        if not active_triggers:
            self._record_decision(triggers, [], 0, state)
            return []
        tasks, applied = self._apply_strategies(active_triggers, gaps, state)
        self._record_decision(triggers, applied, len(tasks), state)
        return tasks

    def _evaluate_all_rules(self, state: EnvironmentState) -> List[EnvironmentTrigger]:
        """评估所有规则"""
        triggers: List[EnvironmentTrigger] = []
        for rule in self._rules:
            triggers.append(rule.evaluate(state))
        return triggers

    def _apply_strategies(
        self,
        triggers: List[EnvironmentTrigger],
        gaps: GapState,
        state: EnvironmentState,
    ) -> Tuple[List[Task], List[str]]:
        """应用策略生成任务"""
        tasks: List[Task] = []
        applied: List[str] = []
        for trigger in triggers:
            strategy = self._strategies.get(trigger.rule_name)
            if strategy is None:
                continue
            new_tasks = strategy.generate_tasks(trigger, gaps, state)
            tasks.extend(new_tasks)
            applied.append(strategy.strategy_name())
        return tasks, applied

    def _record_decision(
        self,
        triggers: List[EnvironmentTrigger],
        strategies_applied: List[str],
        task_count: int,
        state: EnvironmentState,
    ) -> None:
        """记录决策"""
        decision = GenerationDecision(
            timestamp=state.timestamp,
            triggers=triggers,
            strategies_applied=strategies_applied,
            tasks_generated=task_count,
            state_summary=self._build_state_summary(state),
        )
        self._last_decision = decision
        self._decision_history.append(decision)
        if len(self._decision_history) > self._max_history:
            self._decision_history = self._decision_history[-self._max_history:]

    def _build_state_summary(self, state: EnvironmentState) -> Dict[str, float]:
        """构建状态摘要"""
        return {
            "cpu": state.system.cpu_overall,
            "memory": state.system.memory_usage,
            "disk": state.system.disk_usage,
            "error_rate": state.logs.error_rate,
            "warning_rate": state.logs.warning_rate,
            "prediction_error": state.self.prediction_error,
        }

    def get_last_decision(self) -> Optional[GenerationDecision]:
        """获取最近一次决策"""
        return self._last_decision

    def get_decision_history(self) -> List[GenerationDecision]:
        """获取决策历史"""
        return list(self._decision_history)

    def add_rule(self, rule: TriggerRule, strategy: TaskGenerationStrategy) -> None:
        """添加自定义规则和策略"""
        self._rules.append(rule)
        self._strategies[rule.rule_name()] = strategy

    def reset(self) -> None:
        """重置生成器状态"""
        self._last_decision = None
        self._decision_history.clear()

    def get_rule_names(self) -> List[str]:
        """获取所有规则名称"""
        return [r.rule_name() for r in self._rules]

    def get_strategy_names(self) -> List[str]:
        """获取所有策略名称"""
        return list(self._strategies.keys())

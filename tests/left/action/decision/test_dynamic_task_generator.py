"""
动态任务生成器测试

第一性原理：测试覆盖四类用例
1. 正常值：典型环境状态触发对应任务
2. 空入参：默认状态、空GapState
3. 边界极值：阈值边界、所有维度同时触发
4. 非法格式：无效状态、自定义规则异常
"""

import pytest
from typing import List

from src.left.action.decision.dynamic_task_generator import (
    CPU_HIGH_THRESHOLD,
    DISK_HIGH_THRESHOLD,
    ERROR_RATE_HIGH_THRESHOLD,
    IDLE_ALL_THRESHOLD,
    MEMORY_HIGH_THRESHOLD,
    PREDICTION_ERROR_HIGH_THRESHOLD,
    WARNING_RATE_HIGH_THRESHOLD,
    CpuHighRule,
    DiskHighRule,
    DiskCleanupStrategy,
    DynamicTaskGenerator,
    EnvironmentTrigger,
    ErrorRateHighRule,
    ExplorationStrategy,
    GenerationDecision,
    IdleRule,
    LogAnalysisStrategy,
    MemoryHighRule,
    PredictionCorrectionStrategy,
    PredictionErrorHighRule,
    ResourceOptimizationStrategy,
    TaskGenerationStrategy,
    TriggerRule,
    WarningRateHighRule,
)
from src.platform.support.models.base.state import (
    EnvironmentState,
    GapState,
    LogState,
    SelfState,
    SystemState,
)
from src.platform.support.models.base.task import Task, TaskPriority


def _make_state(
    cpu: float = 0.0,
    memory: float = 0.0,
    disk: float = 0.0,
    error_rate: float = 0.0,
    warning_rate: float = 0.0,
    prediction_error: float = 0.0,
) -> EnvironmentState:
    """构造测试用EnvironmentState"""
    return EnvironmentState(
        system=SystemState(
            cpu_overall=cpu,
            memory_usage=memory,
            disk_usage=disk,
        ),
        logs=LogState(
            error_rate=error_rate,
            warning_rate=warning_rate,
        ),
        self=SelfState(prediction_error=prediction_error),
    )


def _make_gaps(safety: float = 0.5, gain: float = 0.5, efficiency: float = 0.5) -> GapState:
    """构造测试用GapState"""
    return GapState(safety=safety, gain=gain, efficiency=efficiency)


# ===== EnvironmentTrigger 测试 =====


class TestEnvironmentTrigger:
    """EnvironmentTrigger数据类测试"""

    def test_describe_triggered(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="cpu",
            value=0.9,
            threshold=0.8,
            triggered=True,
        )
        description = trigger.describe()
        assert "TRIGGERED" in description
        assert "cpu" in description
        assert "0.900" in description

    def test_describe_not_triggered(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="memory",
            value=0.3,
            threshold=0.85,
            triggered=False,
        )
        description = trigger.describe()
        assert "ok" in description
        assert "memory" in description

    def test_frozen(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="x", value=0.5, threshold=0.8, triggered=False
        )
        with pytest.raises(AttributeError):
            trigger.value = 0.9  # type: ignore


# ===== 规则测试 =====


class TestCpuHighRule:
    """CPU高负载规则测试"""

    def test_rule_name(self) -> None:
        assert CpuHighRule().rule_name() == "cpu_high"

    def test_triggered(self) -> None:
        state = _make_state(cpu=CPU_HIGH_THRESHOLD)
        trigger = CpuHighRule().evaluate(state)
        assert trigger.triggered is True
        assert trigger.dimension == "cpu_overall"
        assert trigger.rule_name == "cpu_high"

    def test_not_triggered(self) -> None:
        state = _make_state(cpu=0.1)
        trigger = CpuHighRule().evaluate(state)
        assert trigger.triggered is False

    def test_boundary_exactly_threshold(self) -> None:
        state = _make_state(cpu=CPU_HIGH_THRESHOLD)
        trigger = CpuHighRule().evaluate(state)
        assert trigger.triggered is True


class TestMemoryHighRule:
    """内存高负载规则测试"""

    def test_rule_name(self) -> None:
        assert MemoryHighRule().rule_name() == "memory_high"

    def test_triggered(self) -> None:
        state = _make_state(memory=MEMORY_HIGH_THRESHOLD)
        trigger = MemoryHighRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered(self) -> None:
        state = _make_state(memory=0.2)
        trigger = MemoryHighRule().evaluate(state)
        assert trigger.triggered is False


class TestDiskHighRule:
    """磁盘高使用规则测试"""

    def test_rule_name(self) -> None:
        assert DiskHighRule().rule_name() == "disk_high"

    def test_triggered(self) -> None:
        state = _make_state(disk=DISK_HIGH_THRESHOLD)
        trigger = DiskHighRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered(self) -> None:
        state = _make_state(disk=0.5)
        trigger = DiskHighRule().evaluate(state)
        assert trigger.triggered is False


class TestErrorRateHighRule:
    """错误率高规则测试"""

    def test_rule_name(self) -> None:
        assert ErrorRateHighRule().rule_name() == "error_rate_high"

    def test_triggered(self) -> None:
        state = _make_state(error_rate=ERROR_RATE_HIGH_THRESHOLD)
        trigger = ErrorRateHighRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered(self) -> None:
        state = _make_state(error_rate=0.01)
        trigger = ErrorRateHighRule().evaluate(state)
        assert trigger.triggered is False


class TestWarningRateHighRule:
    """警告率高规则测试"""

    def test_rule_name(self) -> None:
        assert WarningRateHighRule().rule_name() == "warning_rate_high"

    def test_triggered(self) -> None:
        state = _make_state(warning_rate=WARNING_RATE_HIGH_THRESHOLD)
        trigger = WarningRateHighRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered(self) -> None:
        state = _make_state(warning_rate=0.05)
        trigger = WarningRateHighRule().evaluate(state)
        assert trigger.triggered is False


class TestPredictionErrorHighRule:
    """预测误差高规则测试"""

    def test_rule_name(self) -> None:
        assert PredictionErrorHighRule().rule_name() == "prediction_error_high"

    def test_triggered(self) -> None:
        state = _make_state(prediction_error=PREDICTION_ERROR_HIGH_THRESHOLD)
        trigger = PredictionErrorHighRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered(self) -> None:
        state = _make_state(prediction_error=0.05)
        trigger = PredictionErrorHighRule().evaluate(state)
        assert trigger.triggered is False


class TestIdleRule:
    """空闲规则测试"""

    def test_rule_name(self) -> None:
        assert IdleRule().rule_name() == "idle"

    def test_triggered_all_low(self) -> None:
        state = _make_state(
            cpu=0.05,
            memory=0.05,
            disk=0.05,
            error_rate=0.01,
            warning_rate=0.02,
            prediction_error=0.02,
        )
        trigger = IdleRule().evaluate(state)
        assert trigger.triggered is True

    def test_not_triggered_some_high(self) -> None:
        state = _make_state(cpu=0.5)
        trigger = IdleRule().evaluate(state)
        assert trigger.triggered is False

    def test_boundary_exactly_threshold(self) -> None:
        """边界：max=IDLE_ALL_THRESHOLD，不触发（< 才触发）"""
        state = _make_state(cpu=IDLE_ALL_THRESHOLD)
        trigger = IdleRule().evaluate(state)
        assert trigger.triggered is False

    def test_just_below_threshold(self) -> None:
        state = _make_state(cpu=IDLE_ALL_THRESHOLD - 0.001)
        trigger = IdleRule().evaluate(state)
        assert trigger.triggered is True


# ===== 策略测试 =====


class TestResourceOptimizationStrategy:
    """资源优化策略测试"""

    def test_strategy_name(self) -> None:
        assert ResourceOptimizationStrategy().strategy_name() == "resource_optimization"

    def test_generate_tasks(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="cpu_overall",
            value=0.9,
            threshold=0.8,
            triggered=True,
        )
        tasks = ResourceOptimizationStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        assert len(tasks) == 1
        assert tasks[0].target_drive == "eff"
        assert tasks[0].priority == TaskPriority.HIGH

    def test_task_has_execute_fn(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="memory_usage", value=0.9, threshold=0.85, triggered=True
        )
        tasks = ResourceOptimizationStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        result = tasks[0].execute_fn()
        assert result.success is True
        assert "dynamic" in result.data


class TestLogAnalysisStrategy:
    """日志分析策略测试"""

    def test_strategy_name(self) -> None:
        assert LogAnalysisStrategy().strategy_name() == "log_analysis"

    def test_generate_tasks(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="logs.error_rate",
            value=0.15,
            threshold=0.10,
            triggered=True,
        )
        tasks = LogAnalysisStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        assert len(tasks) == 1
        assert tasks[0].target_drive == "safe"
        assert tasks[0].priority == TaskPriority.CRITICAL


class TestDiskCleanupStrategy:
    """磁盘清理策略测试"""

    def test_strategy_name(self) -> None:
        assert DiskCleanupStrategy().strategy_name() == "disk_cleanup"

    def test_generate_tasks(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="disk_usage", value=0.95, threshold=0.90, triggered=True
        )
        tasks = DiskCleanupStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        assert len(tasks) == 1
        assert tasks[0].name == "cleanup_disk"
        assert tasks[0].target_drive == "eff"
        assert tasks[0].priority == TaskPriority.CRITICAL


class TestPredictionCorrectionStrategy:
    """预测修正策略测试"""

    def test_strategy_name(self) -> None:
        assert PredictionCorrectionStrategy().strategy_name() == "prediction_correction"

    def test_generate_tasks(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="self.prediction_error",
            value=0.5,
            threshold=0.3,
            triggered=True,
        )
        tasks = PredictionCorrectionStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        assert len(tasks) == 1
        assert tasks[0].name == "correct_prediction"
        assert tasks[0].target_drive == "safe"
        assert tasks[0].priority == TaskPriority.HIGH


class TestExplorationStrategy:
    """探索策略测试"""

    def test_strategy_name(self) -> None:
        assert ExplorationStrategy().strategy_name() == "exploration"

    def test_generate_tasks(self) -> None:
        trigger = EnvironmentTrigger(
            dimension="idle_max", value=0.1, threshold=0.2, triggered=True
        )
        tasks = ExplorationStrategy().generate_tasks(
            trigger, _make_gaps(), _make_state()
        )
        assert len(tasks) == 1
        assert tasks[0].name == "explore_idle"
        assert tasks[0].target_drive == "gain"
        assert tasks[0].priority == TaskPriority.EXPLORATION
        assert tasks[0].is_exploration is True


# ===== DynamicTaskGenerator 测试 =====


class TestDynamicTaskGenerator:
    """动态任务生成器测试"""

    def test_default_rules_count(self) -> None:
        gen = DynamicTaskGenerator()
        assert len(gen.get_rule_names()) == 7

    def test_default_strategies_count(self) -> None:
        gen = DynamicTaskGenerator()
        assert len(gen.get_strategy_names()) == 7

    def test_default_rules_content(self) -> None:
        gen = DynamicTaskGenerator()
        names = gen.get_rule_names()
        assert "cpu_high" in names
        assert "memory_high" in names
        assert "disk_high" in names
        assert "error_rate_high" in names
        assert "warning_rate_high" in names
        assert "prediction_error_high" in names
        assert "idle" in names

    def test_generate_tasks_idle(self) -> None:
        """空闲状态生成探索任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(
            cpu=0.05, memory=0.05, disk=0.05,
            error_rate=0.01, warning_rate=0.01, prediction_error=0.01,
        )
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) == 1
        assert tasks[0].name == "explore_idle"
        assert tasks[0].is_exploration is True

    def test_generate_tasks_cpu_high(self) -> None:
        """CPU高生成资源优化任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(cpu=0.9)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert any("optimize_cpu" in n for n in names)

    def test_generate_tasks_memory_high(self) -> None:
        """内存高生成资源优化任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(memory=0.9)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert any("optimize_memory" in n for n in names)

    def test_generate_tasks_disk_high(self) -> None:
        """磁盘满生成清理任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(disk=0.95)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert "cleanup_disk" in names

    def test_generate_tasks_error_rate_high(self) -> None:
        """错误率高生成日志分析任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(error_rate=0.15)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert any("analyze_logs" in n for n in names)

    def test_generate_tasks_warning_rate_high(self) -> None:
        """警告率高生成日志分析任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(warning_rate=0.35)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert any("analyze_logs" in n for n in names)

    def test_generate_tasks_prediction_error_high(self) -> None:
        """预测误差高生成预测修正任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(prediction_error=0.5)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        names = [t.name for t in tasks]
        assert "correct_prediction" in names

    def test_generate_tasks_multiple_triggers(self) -> None:
        """多维度同时触发"""
        gen = DynamicTaskGenerator()
        state = _make_state(
            cpu=0.9, memory=0.9, disk=0.95,
            error_rate=0.15, warning_rate=0.4, prediction_error=0.5,
        )
        tasks = gen.generate_tasks(_make_gaps(), state)
        # 6个规则全部触发（idle不触发）
        assert len(tasks) >= 6
        names = {t.name for t in tasks}
        assert "cleanup_disk" in names
        assert "correct_prediction" in names

    def test_generate_tasks_no_trigger(self) -> None:
        """无触发器场景（边界：刚好高于空闲阈值）"""
        gen = DynamicTaskGenerator()
        state = _make_state(cpu=0.3)  # 高于IDLE_ALL_THRESHOLD但不触发CPU_HIGH
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) == 0

    def test_get_last_decision_after_generate(self) -> None:
        gen = DynamicTaskGenerator()
        state = _make_state(cpu=0.9)
        gen.generate_tasks(_make_gaps(), state)
        decision = gen.get_last_decision()
        assert decision is not None
        assert decision.tasks_generated >= 1
        assert "cpu" in decision.state_summary

    def test_get_last_decision_none_initially(self) -> None:
        gen = DynamicTaskGenerator()
        assert gen.get_last_decision() is None

    def test_decision_history(self) -> None:
        gen = DynamicTaskGenerator()
        for _ in range(3):
            gen.generate_tasks(_make_gaps(), _make_state(cpu=0.9))
        history = gen.get_decision_history()
        assert len(history) == 3

    def test_decision_history_limit(self) -> None:
        gen = DynamicTaskGenerator()
        for _ in range(150):
            gen.generate_tasks(_make_gaps(), _make_state(cpu=0.9))
        history = gen.get_decision_history()
        assert len(history) == 100

    def test_decision_to_dict(self) -> None:
        gen = DynamicTaskGenerator()
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.9))
        decision = gen.get_last_decision()
        assert decision is not None
        d = decision.to_dict()
        assert "timestamp" in d
        assert "triggers" in d
        assert "strategies_applied" in d
        assert "tasks_generated" in d
        assert "state_summary" in d

    def test_state_summary_content(self) -> None:
        gen = DynamicTaskGenerator()
        state = _make_state(
            cpu=0.5, memory=0.4, disk=0.3,
            error_rate=0.05, warning_rate=0.1, prediction_error=0.2,
        )
        gen.generate_tasks(_make_gaps(), state)
        decision = gen.get_last_decision()
        assert decision is not None
        summary = decision.state_summary
        assert summary["cpu"] == 0.5
        assert summary["memory"] == 0.4
        assert summary["disk"] == 0.3
        assert summary["error_rate"] == 0.05
        assert summary["warning_rate"] == 0.1
        assert summary["prediction_error"] == 0.2

    def test_add_custom_rule(self) -> None:
        class CustomRule(TriggerRule):
            def rule_name(self) -> str:
                return "custom"

            def evaluate(self, state: EnvironmentState) -> EnvironmentTrigger:
                return EnvironmentTrigger(
                    dimension="custom",
                    value=1.0,
                    threshold=0.5,
                    triggered=True,
                    rule_name="custom",
                )

        class CustomStrategy(TaskGenerationStrategy):
            def strategy_name(self) -> str:
                return "custom_strategy"

            def generate_tasks(self, trigger, gaps, state):
                return [Task(name="custom_task", target_drive="gain")]

        gen = DynamicTaskGenerator()
        gen.add_rule(CustomRule(), CustomStrategy())
        assert "custom" in gen.get_rule_names()
        assert "custom" in gen.get_strategy_names()
        tasks = gen.generate_tasks(_make_gaps(), _make_state())
        names = [t.name for t in tasks]
        assert "custom_task" in names

    def test_reset(self) -> None:
        gen = DynamicTaskGenerator()
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.9))
        assert gen.get_last_decision() is not None
        gen.reset()
        assert gen.get_last_decision() is None
        assert len(gen.get_decision_history()) == 0

    def test_custom_rules_in_constructor(self) -> None:
        gen = DynamicTaskGenerator(
            rules=[CpuHighRule()],
            strategies={"cpu_high": ResourceOptimizationStrategy()},
        )
        assert len(gen.get_rule_names()) == 1
        assert gen.get_rule_names() == ["cpu_high"]

    def test_empty_strategies(self) -> None:
        """策略为空时，触发器不产生任务"""
        gen = DynamicTaskGenerator(
            rules=[CpuHighRule()],
            strategies={},
        )
        state = _make_state(cpu=0.9)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) == 0

    def test_strategies_applied_recorded(self) -> None:
        gen = DynamicTaskGenerator()
        state = _make_state(cpu=0.9, disk=0.95)
        gen.generate_tasks(_make_gaps(), state)
        decision = gen.get_last_decision()
        assert decision is not None
        assert "resource_optimization" in decision.strategies_applied
        assert "disk_cleanup" in decision.strategies_applied

    def test_tasks_executable(self) -> None:
        """生成的任务可执行"""
        gen = DynamicTaskGenerator()
        state = _make_state(cpu=0.9)
        tasks = gen.generate_tasks(_make_gaps(), state)
        for task in tasks:
            assert task.execute_fn is not None
            result = task.execute_fn()
            assert result.success is True


# ===== 端到端场景测试 =====


class TestEndToEndScenarios:
    """端到端场景测试"""

    def test_scenario_cpu_spike_to_optimization(self) -> None:
        """场景：CPU突增→生成优化任务"""
        gen = DynamicTaskGenerator()
        normal_state = _make_state(cpu=0.2)
        spike_state = _make_state(cpu=0.95)
        normal_tasks = gen.generate_tasks(_make_gaps(), normal_state)
        spike_tasks = gen.generate_tasks(_make_gaps(), spike_state)
        assert all("optimize" not in t.name for t in normal_tasks)
        assert any("optimize" in t.name for t in spike_tasks)

    def test_scenario_disk_full_to_cleanup(self) -> None:
        """场景：磁盘满→生成清理任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(disk=0.95)
        tasks = gen.generate_tasks(_make_gaps(), state)
        cleanup_tasks = [t for t in tasks if t.name == "cleanup_disk"]
        assert len(cleanup_tasks) == 1
        assert cleanup_tasks[0].priority == TaskPriority.CRITICAL

    def test_scenario_idle_to_exploration(self) -> None:
        """场景：空闲→生成探索任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(
            cpu=0.05, memory=0.05, disk=0.05,
            error_rate=0.01, warning_rate=0.01, prediction_error=0.01,
        )
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) == 1
        assert tasks[0].is_exploration is True
        assert tasks[0].priority == TaskPriority.EXPLORATION

    def test_scenario_error_burst_to_analysis(self) -> None:
        """场景：错误爆发→生成分析任务"""
        gen = DynamicTaskGenerator()
        state = _make_state(error_rate=0.5)
        tasks = gen.generate_tasks(_make_gaps(), state)
        analysis_tasks = [t for t in tasks if "analyze" in t.name]
        assert len(analysis_tasks) >= 1
        assert analysis_tasks[0].priority == TaskPriority.CRITICAL

    def test_scenario_state_change_over_time(self) -> None:
        """场景：状态变化导致任务类型变化"""
        gen = DynamicTaskGenerator()
        # 阶段1：空闲
        idle_tasks = gen.generate_tasks(
            _make_gaps(),
            _make_state(cpu=0.05, memory=0.05, disk=0.05, prediction_error=0.01),
        )
        assert any(t.is_exploration for t in idle_tasks)
        # 阶段2：CPU突增
        cpu_tasks = gen.generate_tasks(_make_gaps(), _make_state(cpu=0.95))
        assert any("optimize" in t.name for t in cpu_tasks)
        assert not any(t.is_exploration for t in cpu_tasks)
        # 阶段3：恢复空闲
        idle_tasks2 = gen.generate_tasks(
            _make_gaps(),
            _make_state(cpu=0.05, memory=0.05, disk=0.05, prediction_error=0.01),
        )
        assert any(t.is_exploration for t in idle_tasks2)

    def test_decision_history_records_progression(self) -> None:
        """决策历史记录状态变化"""
        gen = DynamicTaskGenerator()
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.05))
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.9))
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.05))
        history = gen.get_decision_history()
        assert len(history) == 3
        # 第一次：idle触发
        assert any("idle" in t.rule_name for t in history[0].triggers if t.triggered)
        # 第二次：cpu_high触发
        assert any("cpu_high" in t.rule_name for t in history[1].triggers if t.triggered)

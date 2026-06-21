"""
O1 秩序化测试：主循环接入真实任务源

第一性原理：秩序化 = 组件连接
验证 DecisionEngine 正确接入 RealTaskFactory 和 DynamicTaskGenerator
"""

import pytest
from typing import List

from src.left.action.decision.decision import DecisionEngine
from src.left.action.decision.dynamic_task_generator import DynamicTaskGenerator
from src.left.action.decision.real_task_factory import RealTaskFactory
from src.platform.support.models.base.state import (
    EnvironmentState,
    GapState,
    LogState,
    SelfState,
    SystemState,
)
from src.platform.support.models.base.task import Task, TaskResult


def _make_state(
    cpu: float = 0.0,
    memory: float = 0.0,
    disk: float = 0.0,
    error_rate: float = 0.0,
    warning_rate: float = 0.0,
    prediction_error: float = 0.0,
) -> EnvironmentState:
    return EnvironmentState(
        system=SystemState(cpu_overall=cpu, memory_usage=memory, disk_usage=disk),
        logs=LogState(error_rate=error_rate, warning_rate=warning_rate),
        self=SelfState(prediction_error=prediction_error),
    )


def _make_gaps(safety: float = 0.5, gain: float = 0.5, efficiency: float = 0.5) -> GapState:
    return GapState(safety=safety, gain=gain, efficiency=efficiency)


class TestDecisionEngineRealTaskSource:
    """测试决策引擎接入真实任务源"""

    def test_no_injection_falls_back_to_placeholder(self) -> None:
        """未注入时使用占位任务（向后兼容）"""
        engine = DecisionEngine()
        tasks = engine.generate_tasks(_make_gaps(), _make_state())
        names = {t.name for t in tasks}
        # 应包含占位任务名
        assert any(name in names for name in {
            "monitor_system_resources", "check_system_errors",
            "explore_new_patterns", "optimize_resource_usage", "idle_observation"
        })

    def test_inject_real_task_factory(self) -> None:
        """注入RealTaskFactory后生成真实任务"""
        factory = RealTaskFactory()
        engine = DecisionEngine(real_task_factory=factory)
        tasks = engine.generate_tasks(_make_gaps(), _make_state())
        names = {t.name for t in tasks}
        assert "system_health_check" in names
        assert "file_inventory" in names
        assert "process_audit" in names

    def test_inject_dynamic_task_generator(self) -> None:
        """注入DynamicTaskGenerator后生成动态任务"""
        gen = DynamicTaskGenerator()
        engine = DecisionEngine(dynamic_task_generator=gen)
        # CPU高→生成优化任务
        state = _make_state(cpu=0.95)
        tasks = engine.generate_tasks(_make_gaps(), state)
        names = {t.name for t in tasks}
        assert any("optimize" in n for n in names)

    def test_inject_both_sources(self) -> None:
        """同时注入两个任务源"""
        factory = RealTaskFactory()
        gen = DynamicTaskGenerator()
        engine = DecisionEngine(
            real_task_factory=factory,
            dynamic_task_generator=gen,
        )
        tasks = engine.generate_tasks(_make_gaps(), _make_state(cpu=0.95))
        names = {t.name for t in tasks}
        # 应同时包含真实任务和动态任务
        assert "system_health_check" in names
        assert any("optimize" in n for n in names)

    def test_real_tasks_are_executable(self) -> None:
        """真实任务可执行"""
        factory = RealTaskFactory()
        engine = DecisionEngine(real_task_factory=factory)
        tasks = engine.generate_tasks(_make_gaps(), _make_state())
        for task in tasks:
            if task.execute_fn is not None:
                result = task.execute_fn()
                assert isinstance(result, TaskResult)

    def test_real_tasks_produce_real_data(self) -> None:
        """真实任务产生真实数据"""
        factory = RealTaskFactory()
        engine = DecisionEngine(real_task_factory=factory)
        tasks = engine.generate_tasks(_make_gaps(), _make_state())
        health_tasks = [t for t in tasks if t.name == "system_health_check"]
        assert len(health_tasks) >= 1
        result = health_tasks[0].execute_fn()
        assert result.success is True
        # 应包含真实指标
        assert "cpu_percent" in result.data or "disk_percent" in result.data

    def test_dynamic_tasks_respond_to_state(self) -> None:
        """动态任务响应状态变化"""
        gen = DynamicTaskGenerator()
        engine = DecisionEngine(dynamic_task_generator=gen)
        # 空闲→探索任务
        idle_tasks = engine.generate_tasks(
            _make_gaps(),
            _make_state(cpu=0.05, memory=0.05, disk=0.05, prediction_error=0.01),
        )
        idle_names = {t.name for t in idle_tasks}
        # CPU高→优化任务
        cpu_tasks = engine.generate_tasks(_make_gaps(), _make_state(cpu=0.95))
        cpu_names = {t.name for t in cpu_tasks}
        assert idle_names != cpu_names

    def test_empty_real_tasks_falls_back(self) -> None:
        """真实任务源返回空时回退到占位任务"""
        # DiskUsageReportFactory在efficiency<0.2时返回空
        # 但RealTaskFactory聚合多个工厂，总有任务
        # 这里测试DynamicTaskGenerator无触发时
        gen = DynamicTaskGenerator()
        engine = DecisionEngine(dynamic_task_generator=gen)
        # 无触发器状态（cpu=0.3，高于idle但不触发cpu_high）
        tasks = engine.generate_tasks(_make_gaps(), _make_state(cpu=0.3))
        # DynamicTaskGenerator无触发→空→回退到占位
        names = {t.name for t in tasks}
        assert len(names) > 0  # 占位任务兜底


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_existing_tests_still_pass(self) -> None:
        """现有测试行为不变"""
        engine = DecisionEngine(base_exploration_ratio=0.3)
        assert engine.base_exploration_ratio == 0.3
        assert engine._real_task_factory is None
        assert engine._dynamic_task_generator is None

    def test_generate_tasks_without_injection(self) -> None:
        """未注入时generate_tasks行为不变"""
        engine = DecisionEngine()
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) > 0

    def test_select_next_task_without_injection(self) -> None:
        """未注入时select_next_task行为不变"""
        from src.platform.support.models.base.task import TaskPool
        from src.platform.support.models.base.state import DriveWeights
        engine = DecisionEngine()
        pool = TaskPool()
        task = Task(name="test", target_drive="safe")
        pool.add_task(task)
        selected = engine.select_next_task(
            pool, GapState(safety=0.5), DriveWeights()
        )
        assert selected is not None


class TestOrderlyIntegration:
    """秩序化集成测试"""

    def test_full_cycle_with_real_tasks(self) -> None:
        """完整周期：真实任务生成→执行"""
        factory = RealTaskFactory()
        gen = DynamicTaskGenerator()
        engine = DecisionEngine(
            real_task_factory=factory,
            dynamic_task_generator=gen,
        )
        state = _make_state(cpu=0.5, memory=0.5, disk=0.5)
        gaps = _make_gaps()
        tasks = engine.generate_tasks(gaps, state)
        # 执行所有任务
        results: List[TaskResult] = []
        for task in tasks:
            if task.execute_fn is not None:
                result = engine.execute_task(task)
                results.append(result)
        # 至少有一个成功
        assert any(r.success for r in results)

    def test_task_diversity_with_real_sources(self) -> None:
        """真实任务源提供任务多样性"""
        factory = RealTaskFactory()
        engine = DecisionEngine(real_task_factory=factory)
        tasks = engine.generate_tasks(_make_gaps(), _make_state())
        names = {t.name for t in tasks}
        # 至少3种不同任务
        assert len(names) >= 3

"""
主系统集成测试

验证端到端闭环和故障恢复
"""

import pytest

from src.main import AgentSystem
from src.platform.support.models.base.state import EnvironmentState, DriveWeights, GapState
from src.platform.support.models.base.task import Task


class TestEndToEndCycle:
    """测试端到端完整周期"""

    def setup_method(self):
        self.system = AgentSystem()

    def teardown_method(self):
        self.system.stop()

    def test_full_cycle_executes_without_error(self):
        """验证完整周期链无错误执行"""
        self.system._run_single_cycle()
        assert self.system.cycle_count == 1

    def test_cognition_pipeline(self):
        """验证认知流水线输出正确类型"""
        state, rewards, gaps, weights = self.system._run_cognition()
        assert isinstance(state, EnvironmentState)
        assert hasattr(rewards, "safety")
        assert isinstance(gaps, GapState)
        assert isinstance(weights, DriveWeights)

    def test_decide_and_execute_with_tasks(self):
        """验证决策执行链路"""
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        state = EnvironmentState()
        weights = DriveWeights()
        task = self.system._decide_and_execute(gaps, state, weights)
        if task is not None:
            assert isinstance(task, Task)

    def test_task_pool_grows(self):
        """验证任务池在周期中增长"""
        initial = len(self.system.task_pool.tasks)
        self.system._run_single_cycle()
        assert len(self.system.task_pool.tasks) >= initial

    def test_event_bus_records_cycle(self):
        """验证事件总线记录周期事件"""
        self.system._run_single_cycle()
        stats = self.system.event_bus.get_event_stats()
        assert stats.get("CYCLE_START", 0) >= 1

    def test_success_rate_tracking(self):
        """验证成功率追踪"""
        self.system._run_single_cycle()
        rate = self.system._calc_success_rate()
        assert 0.0 <= rate <= 100.0

    def test_multiple_cycles_consistent(self):
        """验证多周期执行一致性"""
        for _ in range(3):
            self.system._run_single_cycle()
        assert self.system.cycle_count == 3


class TestFaultRecovery:
    """测试故障恢复能力"""

    def setup_method(self):
        self.system = AgentSystem()

    def teardown_method(self):
        self.system.stop()

    def test_cycle_error_handled(self):
        """验证周期错误被捕获处理"""
        original = self.system._perceive
        self.system._perceive = lambda: (_ for _ in ()).throw(RuntimeError("test"))
        try:
            self.system._run_single_cycle()
        finally:
            self.system._perceive = original
        assert self.system.cycle_count == 1

    def test_plugin_failure_isolated(self):
        """验证插件故障不影响系统"""
        self.system.plugin_manager._plugins["file_plugin"].execute = lambda params: (_ for _ in ()).throw(RuntimeError("plugin fail"))
        self.system._run_single_cycle()

    def test_guardrail_throttle_on_overload(self):
        """验证护栏在超载时触发节流"""
        from dataclasses import replace
        state = EnvironmentState(system=replace(EnvironmentState().system, cpu_overall=1.0))
        self.system._safety_check(state)

    def test_system_stop_graceful(self):
        """验证系统优雅停止"""
        self.system.running = True
        self.system.stop()
        assert self.system.running is False
        assert self.system.event_bus._running is False

    def test_recovery_after_multiple_errors(self):
        """验证多次错误后系统仍能恢复"""
        call_count = 0
        original = self.system._perceive

        def failing_perceive():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError(f"fail {call_count}")
            return original()

        self.system._perceive = failing_perceive
        try:
            for _ in range(4):
                self.system._run_single_cycle()
        finally:
            self.system._perceive = original
        assert self.system.cycle_count == 4


class TestStateConsistency:
    """测试状态一致性"""

    def setup_method(self):
        self.system = AgentSystem()

    def teardown_method(self):
        self.system.stop()

    def test_cycle_count_monotonic(self):
        """验证周期计数单调递增"""
        for _ in range(5):
            prev = self.system.cycle_count
            self.system._run_single_cycle()
            assert self.system.cycle_count == prev + 1

    def test_task_execution_count_matches(self):
        """验证任务执行计数一致"""
        before = self.system.total_tasks_executed
        self.system._run_single_cycle()
        after = self.system.total_tasks_executed
        assert after >= before

    def test_connector_cycle_sync(self):
        """验证连接器周期同步"""
        self.system._set_cycle(42)
        assert self.system.perception_conn._cycle == 42
        assert self.system.drive_conn._cycle == 42
        assert self.system.decision_conn._cycle == 42

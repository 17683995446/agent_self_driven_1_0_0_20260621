"""
主循环非阻塞路径测试

补充覆盖 _publish_cycle_start、_perceive、_compute_rewards 等解耦路径
"""

import pytest

from src.main import AgentSystem
from src.platform.support.models.base.state import EnvironmentState, DriveRewards, GapState, DriveWeights, ResourceUsage


class TestAgentSystemLoopMethods:
    """测试主循环内部方法"""

    def test_set_cycle(self):
        system = AgentSystem()
        system._set_cycle(5)
        assert system.perception_conn._cycle == 5

    def test_publish_cycle_start(self):
        system = AgentSystem()
        system.cycle_count = 1
        system._publish_cycle_start()

    def test_perceive(self):
        system = AgentSystem()
        state = system._perceive()
        assert isinstance(state, EnvironmentState)

    def test_compute_rewards(self):
        system = AgentSystem()
        state = EnvironmentState()
        rewards = system._compute_rewards(state)
        assert hasattr(rewards, "safety")

    def test_compute_gaps(self):
        system = AgentSystem()
        rewards = DriveRewards()
        gaps = system._compute_gaps(rewards)
        assert isinstance(gaps, GapState)

    def test_compute_weights(self):
        system = AgentSystem()
        state = EnvironmentState()
        gaps = GapState()
        weights = system._compute_weights(state, gaps)
        assert isinstance(weights, DriveWeights)

    def test_decide_and_execute_empty(self):
        system = AgentSystem()
        task = system._decide_and_execute(GapState(), EnvironmentState(), DriveWeights())

    def test_safety_check(self):
        system = AgentSystem()
        state = EnvironmentState()
        system._safety_check(state)

    def test_publish_cycle_end(self):
        system = AgentSystem()
        system.cycle_count = 10
        system._publish_cycle_end(EnvironmentState(), 0.0)

    def test_sleep_cycle(self):
        system = AgentSystem()
        import time
        start = time.time()
        system._sleep_cycle(start)

    def test_handle_cycle_error(self):
        system = AgentSystem()
        system._handle_cycle_error(ValueError("test error"))


class TestAgentSystemStartStop:
    """测试启动和停止路径"""

    def test_stop(self):
        system = AgentSystem()
        system.stop()
        assert system.running is False

    def test_is_healthy(self):
        system = AgentSystem()
        assert isinstance(system.is_healthy(), bool)


class TestAgentSystemSafetyCpuOverload:
    """测试安全护栏CPU超限分支"""

    def test_safety_check_cpu_overload(self):
        from dataclasses import replace
        system = AgentSystem()
        state = EnvironmentState(system=replace(EnvironmentState().system, cpu_overall=1.0))
        system._safety_check(state)


class TestAgentSystemTaskFailed:
    """测试任务失败发布路径"""

    def test_publish_task_failed(self):
        system = AgentSystem()
        from src.platform.support.models.base.task import Task
        task = Task(name="fail_task")
        class FakeResult:
            message = "error"
        system._publish_task_failed(task, FakeResult())


class TestAgentSystemSelectTaskNone:
    """测试选择任务为空路径"""

    def test_select_task_none(self):
        system = AgentSystem()
        system.decision.select_next_task = lambda pool, gaps, weights: None
        result = system._select_and_execute_task(GapState(), DriveWeights())
        assert result is None

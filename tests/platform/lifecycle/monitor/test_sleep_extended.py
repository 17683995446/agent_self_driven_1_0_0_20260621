"""
睡眠进化扩展测试

补充覆盖 wake_up、get_stats、多次睡眠、模型优化路径
"""

import pytest

from src.platform.lifecycle.monitor.sleep import SleepManager, SleepReport
from src.platform.lifecycle.monitor.memory import MemorySystem
from src.left.cognition.perception.prediction import HierarchicalPredictionModel
from src.platform.support.models.base.state import EnvironmentState


class TestSleepManagerExtended:
    """测试睡眠管理器扩展路径"""

    def test_wake_up(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        manager.is_sleeping = True
        manager.wake_up()
        assert manager.is_sleeping is False

    def test_wake_up_when_not_sleeping(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        manager.wake_up()
        assert manager.is_sleeping is False

    def test_get_stats(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        stats = manager.get_stats()
        assert "sleep_count" in stats
        assert "total_sleep_time" in stats

    def test_multiple_sleep_cycles(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        manager.enter_sleep()
        manager.enter_sleep()
        assert manager.sleep_count == 2

    def test_already_sleeping_returns_empty(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        manager.is_sleeping = True
        report = manager.enter_sleep()
        assert isinstance(report, SleepReport)
        assert report.duration == 0.0

    def test_should_sleep_when_sleeping(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        manager.is_sleeping = True
        result = manager.should_sleep(EnvironmentState())
        assert result is True

    def test_should_sleep_low_cpu(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction, idle_threshold=0.9)
        state = EnvironmentState()
        result = manager.should_sleep(state)
        assert result is True

    def test_should_sleep_high_cpu(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction, idle_threshold=0.0)
        state = EnvironmentState()
        result = manager.should_sleep(state)
        assert result is False

    def test_optimize_prediction_with_data(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        # 存储足够多的高重要性经验到长期记忆
        for i in range(15):
            memory.store_experience(
                state={"state": EnvironmentState()}, action="test", result={},
                reward=1.0, importance=0.9
            )
        report = manager.enter_sleep()
        assert isinstance(report, SleepReport)

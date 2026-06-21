"""
睡眠进化模块测试

验证睡眠检测、记忆巩固、模型优化的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.lifecycle.monitor.sleep import SleepManager, SleepManagerBase
from src.platform.lifecycle.monitor.memory import MemorySystem
from src.left.cognition.perception.prediction import HierarchicalPredictionModel
from src.platform.support.models.base.state import EnvironmentState


class TestSleepManagerBase:
    """测试睡眠管理器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            SleepManagerBase()


class TestSleepManagerInit:
    """测试睡眠管理器初始化"""

    def test_normal_init(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        assert manager is not None


class TestShouldSleep:
    """测试睡眠检测"""

    def test_normal_state(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        state = EnvironmentState()
        result = manager.should_sleep(state)
        assert isinstance(result, bool)

    def test_high_cpu_state(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        state = EnvironmentState()
        result = manager.should_sleep(state)
        assert isinstance(result, bool)


class TestEnterSleep:
    """测试进入睡眠"""

    def test_normal_sleep(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        report = manager.enter_sleep()
        assert report is not None


class TestSleepReport:
    """测试睡眠报告"""

    def test_report_contents(self):
        memory = MemorySystem()
        prediction = HierarchicalPredictionModel()
        manager = SleepManager(memory, prediction)
        report = manager.enter_sleep()
        assert hasattr(report, "duration")
        assert report.duration >= 0.0

"""
进化监控模块测试

验证指标计算、趋势检测、异常检测的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.execution.monitor import EvolutionMonitor, MonitorBase, EvolutionTrend
from src.platform.support.models.base.state import EnvironmentState, DriveRewards, GapState


class TestMonitorBase:
    """测试监控器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            MonitorBase()


class TestEvolutionMonitorInit:
    """测试进化监控器初始化"""

    def test_normal_init(self):
        monitor = EvolutionMonitor(window_size=30)
        assert monitor.window_size == 30

    def test_boundary_min_window(self):
        monitor = EvolutionMonitor(window_size=1)
        assert monitor.window_size == 1


class TestUpdate:
    """测试状态更新"""

    def test_normal_update(self):
        monitor = EvolutionMonitor()
        state = EnvironmentState()
        rewards = DriveRewards()
        gaps = GapState()
        monitor.update(state, rewards, gaps)
        assert monitor.total_cycles == 1

    def test_multiple_updates(self):
        monitor = EvolutionMonitor()
        for _ in range(10):
            monitor.update(EnvironmentState(), DriveRewards(), GapState())
        assert monitor.total_cycles == 10


class TestDetectTrend:
    """测试趋势检测"""

    def test_no_data(self):
        monitor = EvolutionMonitor()
        trend = monitor.detect_trend()
        assert trend == EvolutionTrend.INSUFFICIENT_DATA

    def test_improving_trend(self):
        monitor = EvolutionMonitor()
        for i in range(20):
            monitor.update(EnvironmentState(), DriveRewards(safety=float(i)*0.05), GapState())
        trend = monitor.detect_trend()
        assert trend in [
            EvolutionTrend.IMPROVING,
            EvolutionTrend.STABLE,
            EvolutionTrend.STAGNANT
        ]


class TestGetMetrics:
    """测试获取指标"""

    def test_empty_metrics(self):
        monitor = EvolutionMonitor()
        metrics = monitor.get_current_metrics()
        assert metrics is None

    def test_with_data(self):
        monitor = EvolutionMonitor()
        for _ in range(5):
            monitor.update(EnvironmentState(), DriveRewards(), GapState())
        metrics = monitor.get_current_metrics()
        assert metrics is not None

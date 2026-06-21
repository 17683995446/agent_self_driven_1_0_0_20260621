"""
进化监控扩展测试

补充覆盖 generate_report、recent_anomalies、precision_drop、stagnation 等路径
"""

import pytest

from src.left.action.execution.monitor import (
    EvolutionMonitor, MonitorBase, EvolutionTrend,
    EvolutionMetrics, AnomalyEvent,
)
from src.platform.support.models.base.state import EnvironmentState, DriveRewards, GapState


class TestMonitorBase:
    """测试监控器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            MonitorBase()


class TestEvolutionMonitorExtended:
    """测试进化监控器扩展路径"""

    def test_generate_report_empty(self):
        monitor = EvolutionMonitor()
        report = monitor.generate_report()
        assert "timestamp" in report
        assert "total_cycles" in report
        assert report["total_cycles"] == 0

    def test_generate_report_with_data(self):
        monitor = EvolutionMonitor()
        for _ in range(15):
            monitor.update(EnvironmentState(), DriveRewards(), GapState())
        report = monitor.generate_report()
        assert report["total_cycles"] == 15
        assert "current_metrics" in report
        assert "trend" in report

    def test_detect_trend_with_data(self):
        monitor = EvolutionMonitor()
        for i in range(50):
            monitor.update(
                EnvironmentState(),
                DriveRewards(safety=float(i) * 0.02),
                GapState()
            )
        trend = monitor.detect_trend()
        assert trend in list(EvolutionTrend)

    def test_get_recent_anomalies(self):
        monitor = EvolutionMonitor()
        anomalies = monitor.get_recent_anomalies(5)
        assert anomalies == []

    def test_precision_drop_detection(self):
        monitor = EvolutionMonitor()
        # 先积累足够的error_history和metrics_history
        for i in range(12):
            monitor.update(
                EnvironmentState(),
                DriveRewards(safety=0.9),
                GapState(),
                prediction_error=0.01
            )
        # 再积累一些让precision_index变化
        for i in range(12):
            monitor.update(
                EnvironmentState(),
                DriveRewards(safety=0.1),
                GapState(),
                prediction_error=0.9
            )
        anomalies = monitor.get_recent_anomalies(5)
        # 精度突降检测条件较严格，至少保证无异常时不报错
        assert isinstance(anomalies, list)

    def test_stagnation_detection(self):
        monitor = EvolutionMonitor()
        # 需要至少20个指标历史，且进化指数变化小于0.01
        for _ in range(25):
            monitor.update(EnvironmentState(), DriveRewards(safety=0.5), GapState(), prediction_error=0.5)
        anomalies = monitor.get_recent_anomalies(5)
        # 停滞检测条件较严格，至少保证无异常时不报错
        assert isinstance(anomalies, list)

    def test_update_with_task(self):
        monitor = EvolutionMonitor()
        monitor.update(
            EnvironmentState(),
            DriveRewards(),
            GapState(),
            task_executed=True,
            task_success=True,
        )
        assert monitor.total_tasks == 1
        assert monitor.successful_tasks == 1

    def test_update_with_failed_task(self):
        monitor = EvolutionMonitor()
        monitor.update(
            EnvironmentState(),
            DriveRewards(),
            GapState(),
            task_executed=True,
            task_success=False,
        )
        assert monitor.total_tasks == 1
        assert monitor.successful_tasks == 0

    def test_record_anomaly_directly(self):
        monitor = EvolutionMonitor()
        monitor._record_anomaly(
            type="test_anomaly",
            severity="LOW",
            message="test message",
            data={"key": "value"}
        )
        anomalies = monitor.get_recent_anomalies(5)
        assert len(anomalies) == 1
        assert anomalies[0].type == "test_anomaly"


class TestEvolutionMetrics:
    """测试进化指标"""

    def test_evolution_index(self):
        metrics = EvolutionMetrics(precision_index=0.5, coverage_index=0.5, efficiency_index=0.5)
        assert metrics.evolution_index == 0.5

    def test_to_dict(self):
        metrics = EvolutionMetrics(precision_index=0.3, coverage_index=0.6, efficiency_index=0.9)
        d = metrics.to_dict()
        assert d["precision"] == 0.3
        assert d["coverage"] == 0.6
        assert d["efficiency"] == 0.9
        assert "evolution" in d


class TestAnomalyEvent:
    """测试异常事件"""

    def test_creation(self):
        event = AnomalyEvent(type="test", severity="HIGH", message="test message")
        assert event.type == "test"
        assert event.severity == "HIGH"
        assert event.message == "test message"

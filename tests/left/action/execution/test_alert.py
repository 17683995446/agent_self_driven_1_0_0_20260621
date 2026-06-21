"""
异常检测与预警系统测试

验证指标窗口、异常检测、预警管理的正确性
"""

import pytest
import time

from src.left.action.execution.alert import (
    Alert, AlertLevel, AlertType,
    MetricWindow, AnomalyDetector, AlertManager, SystemAnomalyMonitor,
)


class TestMetricWindow:
    """测试指标窗口"""

    def test_add_and_stats(self):
        window = MetricWindow(window_size=5)
        for i in range(5):
            window.add(float(i))

        assert window.mean == 2.0
        assert window.latest == 4.0
        assert window.is_full is True

    def test_std(self):
        window = MetricWindow(window_size=5)
        window.add(1.0)
        window.add(2.0)
        window.add(3.0)
        assert window.std > 0

    def test_std_single_value(self):
        window = MetricWindow(window_size=5)
        window.add(1.0)
        assert window.std == 0.0

    def test_trend_rising(self):
        window = MetricWindow(window_size=10)
        for i in range(10):
            window.add(float(i))
        assert window.trend() > 0

    def test_trend_falling(self):
        window = MetricWindow(window_size=10)
        for i in range(10):
            window.add(10.0 - float(i))
        assert window.trend() < 0

    def test_trend_flat(self):
        window = MetricWindow(window_size=10)
        for _ in range(10):
            window.add(5.0)
        assert window.trend() == 0.0


class TestAnomalyDetector:
    """测试异常检测器"""

    def setup_method(self):
        self.detector = AnomalyDetector(window_size=10, z_score_threshold=2.0)

    def test_update(self):
        self.detector.update("cpu", 0.5)
        stats = self.detector.get_metric_stats("cpu")
        assert stats["latest"] == 0.5

    def test_z_score_normal(self):
        for _ in range(10):
            self.detector.update("cpu", 0.5)
        is_anomaly, z_score, direction = self.detector.check_z_score("cpu")
        assert is_anomaly is False

    def test_z_score_anomaly_high(self):
        for _ in range(10):
            self.detector.update("cpu", 0.1)
        self.detector.update("cpu", 0.9)
        is_anomaly, z_score, direction = self.detector.check_z_score("cpu")
        assert is_anomaly is True
        assert direction == 1
        assert z_score > 2.0

    def test_z_score_anomaly_low(self):
        for _ in range(10):
            self.detector.update("cpu", 0.9)
        self.detector.update("cpu", 0.1)
        is_anomaly, z_score, direction = self.detector.check_z_score("cpu")
        assert is_anomaly is True
        assert direction == -1

    def test_z_score_not_full(self):
        for _ in range(5):
            self.detector.update("cpu", 0.5)
        is_anomaly, _, _ = self.detector.check_z_score("cpu")
        assert is_anomaly is False

    def test_trend_detection(self):
        for i in range(15):
            self.detector.update("cpu", float(i) * 0.1)
        is_anomaly, trend, direction = self.detector.check_trend("cpu")
        assert is_anomaly is True
        assert direction == 1

    def test_threshold_violation(self):
        self.detector.update("cpu", 0.95)
        is_violation, direction = self.detector.check_threshold("cpu", max_val=0.9)
        assert is_violation is True
        assert direction == 1

    def test_threshold_normal(self):
        self.detector.update("cpu", 0.5)
        is_violation, _ = self.detector.check_threshold("cpu", max_val=0.9)
        assert is_violation is False

    def test_threshold_min(self):
        self.detector.update("cpu", 0.05)
        is_violation, direction = self.detector.check_threshold("cpu", min_val=0.1)
        assert is_violation is True
        assert direction == -1


class TestAlertManager:
    """测试预警管理器"""

    def setup_method(self):
        self.manager = AlertManager(debounce_count=2, cooldown_seconds=0.1)

    def test_check_and_alert_force(self):
        alert = self.manager.check_and_alert(
            AlertType.ERROR_RATE_SPIKE,
            AlertLevel.WARNING,
            "test alert",
            force=True,
        )
        assert alert is not None
        assert alert.alert_type == AlertType.ERROR_RATE_SPIKE

    def test_debounce(self):
        # 第一次不应触发（去抖动）
        a1 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg1")
        assert a1 is None

        # 第二次应触发
        a2 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg2")
        assert a2 is not None

    def test_cooldown(self):
        # 强制触发第一个
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg1", force=True)

        # 冷却期内非强制调用不应触发（去抖动+冷却）
        a2 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg2", force=False)
        assert a2 is None

    def test_cooldown_expired(self):
        # 强制触发第一个
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg1", force=True)

        time.sleep(0.15)

        # 冷却期过后可以触发
        a2 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg2", force=True)
        assert a2 is not None

    def test_register_handler(self):
        received = []
        def handler(alert):
            received.append(alert)

        self.manager.register_handler(AlertLevel.WARNING, handler)
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "test", force=True)

        assert len(received) == 1
        assert received[0].message == "test"

    def test_acknowledge(self):
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "test", force=True)
        assert self.manager.acknowledge(0) is True
        assert self.manager._alerts[0].acknowledged is True

    def test_acknowledge_invalid(self):
        assert self.manager.acknowledge(100) is False

    def test_get_active_alerts(self):
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "w1", force=True)
        self.manager.check_and_alert(AlertType.HIGH_LATENCY, AlertLevel.CRITICAL, "c1", force=True)
        self.manager.acknowledge(0)

        active = self.manager.get_active_alerts()
        assert len(active) == 1
        assert active[0].level == AlertLevel.CRITICAL

    def test_get_alert_stats(self):
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "w1", force=True)
        self.manager.check_and_alert(AlertType.HIGH_LATENCY, AlertLevel.CRITICAL, "c1", force=True)

        stats = self.manager.get_alert_stats()
        assert stats["warning"] == 1
        assert stats["critical"] == 1
        assert stats["total"] == 2
        assert stats["active"] == 2

    def test_reset_debounce(self):
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg1")
        self.manager.reset_debounce(AlertType.ERROR_RATE_SPIKE)
        a2 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg2")
        assert a2 is None  # 重置后仍需debounce_count次

    def test_reset_debounce_all(self):
        self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg1")
        self.manager.reset_debounce()
        a2 = self.manager.check_and_alert(AlertType.ERROR_RATE_SPIKE, AlertLevel.WARNING, "msg2")
        assert a2 is None


class TestSystemAnomalyMonitor:
    """测试系统异常监控器"""

    def setup_method(self):
        self.monitor = SystemAnomalyMonitor(
            detector_window_size=10,
            alert_debounce=1,
            alert_cooldown=0.1,
        )

    def test_update_metric(self):
        for _ in range(15):
            self.monitor.update_metric("cpu_usage", 0.5)
        status = self.monitor.get_status()
        assert "cpu_usage" in status["detector_windows"]

    def test_threshold_alert(self):
        self.monitor.update_metric("cpu_usage", 0.95)
        alerts = self.monitor.alert_manager.get_recent_alerts(10)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == AlertType.RESOURCE_EXHAUSTION

    def test_z_score_alert(self):
        # 填充正常值
        for _ in range(10):
            self.monitor.update_metric("error_rate", 0.05)
        # 异常值
        self.monitor.update_metric("error_rate", 0.9)

        alerts = self.monitor.alert_manager.get_recent_alerts(10)
        # 可能触发阈值和Z-Score两个预警
        assert len(alerts) >= 1

    def test_get_status(self):
        status = self.monitor.get_status()
        assert "detector_windows" in status
        assert "alert_stats" in status
        assert "active_alerts" in status

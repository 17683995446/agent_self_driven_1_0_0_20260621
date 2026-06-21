"""
异常检测与预警系统

第一性原理：系统必须能感知自身异常，并在恶化前发出预警
- 多维度检测：错误率、延迟、资源、行为模式
- 分级预警：信息/警告/严重/紧急
- 去抖动：避免短暂波动触发误报
- 趋势预测：基于历史数据预测未来异常

类比：生物的"痛觉系统"——感知伤害、触发保护反应
"""

import time
import logging
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from collections import deque


logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """预警级别"""
    INFO = "info"           # 提示信息
    WARNING = "warning"     # 警告，需要关注
    CRITICAL = "critical"   # 严重，需要立即处理
    EMERGENCY = "emergency" # 紧急，系统可能不可用


class AlertType(Enum):
    """预警类型"""
    ERROR_RATE_SPIKE = "error_rate_spike"
    HIGH_LATENCY = "high_latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    BEHAVIOR_ANOMALY = "behavior_anomaly"
    STAGNATION = "stagnation"
    DEGRADATION = "degradation"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class Alert:
    """预警记录"""
    alert_type: AlertType
    level: AlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "source": self.source,
            "details": self.details,
            "acknowledged": self.acknowledged,
        }


class MetricWindow:
    """
    指标滑动窗口

    第一性原理：异常检测需要基于近期数据，而非瞬时快照
    """

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size
        self.values: deque = deque(maxlen=window_size)
        self.timestamps: deque = deque(maxlen=window_size)

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        """添加数据点"""
        self.values.append(value)
        self.timestamps.append(timestamp or time.time())

    @property
    def mean(self) -> float:
        """均值"""
        if not self.values:
            return 0.0
        return statistics.mean(self.values)

    @property
    def std(self) -> float:
        """标准差"""
        if len(self.values) < 2:
            return 0.0
        return statistics.stdev(self.values)

    @property
    def latest(self) -> float:
        """最新值"""
        return self.values[-1] if self.values else 0.0

    @property
    def is_full(self) -> bool:
        """窗口是否已满"""
        return len(self.values) >= self.window_size

    def _compute_trend_components(self, x: List[int], y: List[float]) -> Tuple[float, float]:
        """计算趋势的分量"""
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(len(x)))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(len(x)))
        return numerator, denominator

    def _prepare_trend_data(self) -> Tuple[List[int], List[float]]:
        x = list(range(len(self.values)))
        y = list(self.values)
        return x, y

    def trend(self) -> float:
        """
        计算趋势（线性回归斜率）
        正值表示上升，负值表示下降
        """
        if len(self.values) < 3:
            return 0.0
        x, y = self._prepare_trend_data()
        numerator, denominator = self._compute_trend_components(x, y)
        if denominator == 0:
            return 0.0
        return numerator / denominator


class AnomalyDetectorBase(ABC):
    """异常检测器抽象基类"""

    @abstractmethod
    def update(self, metric_name: str, value: float) -> None:
        """更新指标数据"""
        pass

    @abstractmethod
    def check_z_score(self, metric_name: str) -> tuple:
        """Z-Score异常检测"""
        pass


class AnomalyDetector(AnomalyDetectorBase):
    """
    异常检测器

    第一性原理：异常 = 偏离正常模式，必须量化检测
    - Z-Score：基于统计分布检测离群值
    - 趋势检测：检测持续上升/下降
    - 阈值检测：简单但有效的硬边界
    """

    def __init__(
        self,
        window_size: int = 30,
        z_score_threshold: float = 2.5,
        trend_threshold: float = 0.01,
    ) -> None:
        self.window_size = window_size
        self.z_score_threshold = z_score_threshold
        self.trend_threshold = trend_threshold
        self._windows: Dict[str, MetricWindow] = {}

    def _get_window(self, metric_name: str) -> MetricWindow:
        """获取或创建指标窗口"""
        if metric_name not in self._windows:
            self._windows[metric_name] = MetricWindow(self.window_size)
        return self._windows[metric_name]

    def update(self, metric_name: str, value: float) -> None:
        """更新指标数据"""
        window = self._get_window(metric_name)
        window.add(value)

    def _compute_z_direction(self, z_score: float) -> int:
        """根据z分数计算方向"""
        return 1 if z_score > 0 else -1

    def _compute_z_score(self, window: MetricWindow) -> float:
        std = window.std
        if std == 0:
            return 0.0
        return (window.latest - window.mean) / std

    def _z_score_result(self, z_score: float) -> tuple:
        if abs(z_score) > self.z_score_threshold:
            return True, z_score, self._compute_z_direction(z_score)
        return False, z_score, 0

    def check_z_score(self, metric_name: str) -> tuple:
        """
        Z-Score异常检测

        Returns:
            (is_anomaly, z_score, direction)
            direction: 1=偏高, -1=偏低, 0=正常
        """
        window = self._get_window(metric_name)
        if not window.is_full:
            return False, 0.0, 0
        z_score = self._compute_z_score(window)
        return self._z_score_result(z_score)

    def _trend_direction(self, trend_value: float) -> int:
        return 1 if trend_value > 0 else -1

    def _trend_result(self, trend_value: float) -> tuple:
        if abs(trend_value) > self.trend_threshold:
            return True, trend_value, self._trend_direction(trend_value)
        return False, trend_value, 0

    def check_trend(self, metric_name: str) -> tuple:
        """
        趋势异常检测

        Returns:
            (is_anomaly, trend_value, direction)
        """
        window = self._get_window(metric_name)
        if len(window.values) < 10:
            return False, 0.0, 0
        return self._trend_result(window.trend())

    def check_threshold(
        self,
        metric_name: str,
        min_val: float = None,
        max_val: float = None
    ) -> tuple:
        """
        阈值检测

        Returns:
            (is_violation, direction)
        """
        window = self._get_window(metric_name)
        latest = window.latest
        if max_val is not None and latest > max_val:
            return True, 1
        if min_val is not None and latest < min_val:
            return True, -1
        return False, 0

    def _make_stats(self, window: MetricWindow) -> Dict[str, float]:
        return {
            "mean": window.mean,
            "std": window.std,
            "latest": window.latest,
            "count": len(window.values),
            "trend": window.trend(),
        }

    def get_metric_stats(self, metric_name: str) -> Dict[str, float]:
        """获取指标统计"""
        window = self._get_window(metric_name)
        return self._make_stats(window)


class AlertManagerBase(ABC):
    """预警管理器抽象基类"""

    @abstractmethod
    def check_and_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        source: str = "system",
        details: Dict[str, Any] = None,
        force: bool = False,
    ) -> Optional[Alert]:
        """检查并触发预警"""
        pass


class AlertManager(AlertManagerBase):
    """
    预警管理器

    第一性原理：预警必须分级、去抖动、可追踪
    - 分级：不同级别不同处理策略
    - 去抖动：连续异常才触发，避免误报
    - 冷却期：同一类型预警有最小间隔
    """

    def __init__(
        self,
        debounce_count: int = 3,
        cooldown_seconds: float = 60.0,
        max_alerts: int = 1000,
    ) -> None:
        self.debounce_count = debounce_count
        self.cooldown_seconds = cooldown_seconds
        self.max_alerts = max_alerts
        self._alerts: List[Alert] = []
        self._debounce_counters: Dict[str, int] = {}
        self._last_alert_time: Dict[str, float] = {}
        self._handlers: Dict[AlertLevel, List[Callable[[Alert], None]]] = {
            level: [] for level in AlertLevel
        }

    def register_handler(self, level: AlertLevel, handler: Callable[[Alert], None]) -> None:
        """注册预警处理器"""
        self._handlers[level].append(handler)

    def _is_in_cooldown(self, type_key: str) -> bool:
        """检查是否在冷却期"""
        last_time = self._last_alert_time.get(type_key, 0)
        return time.time() - last_time < self.cooldown_seconds

    def _should_debounce(self, type_key: str) -> bool:
        """检查是否需要去抖动"""
        self._debounce_counters[type_key] = self._debounce_counters.get(type_key, 0) + 1
        return self._debounce_counters[type_key] < self.debounce_count

    def _reset_counters(self, type_key: str) -> None:
        """重置计数器"""
        self._debounce_counters[type_key] = 0
        self._last_alert_time[type_key] = time.time()

    def _create_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        source: str,
        details: Dict[str, Any]
    ) -> Alert:
        """创建预警对象"""
        return Alert(
            alert_type=alert_type,
            level=level,
            message=message,
            source=source,
            details=details,
        )

    def _should_suppress(self, type_key: str, force: bool) -> bool:
        """判断是否应该抑制预警"""
        if force:
            return False
        if self._is_in_cooldown(type_key):
            return True
        if self._should_debounce(type_key):
            return True
        return False

    def _trigger_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        source: str,
        details: Dict[str, Any]
    ) -> Alert:
        """触发预警并分发"""
        alert = self._create_alert(alert_type, level, message, source, details)
        self._add_alert(alert)
        self._dispatch_alert(alert)
        logger.warning(f"Alert triggered: [{level.value}] {message}")
        return alert

    def _prepare_details(self, details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return details or {}

    def check_and_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        source: str = "system",
        details: Dict[str, Any] = None,
        force: bool = False,
    ) -> Optional[Alert]:
        """
        检查并触发预警

        Args:
            alert_type: 预警类型
            level: 预警级别
            message: 预警消息
            source: 来源
            details: 详细信息
            force: 强制触发（忽略去抖动和冷却）

        Returns:
            Alert对象（如果触发）或None
        """
        type_key = alert_type.value
        if self._should_suppress(type_key, force):
            return None
        self._reset_counters(type_key)
        return self._trigger_alert(alert_type, level, message, source, self._prepare_details(details))

    def _add_alert(self, alert: Alert) -> None:
        """添加预警记录"""
        self._alerts.append(alert)
        if len(self._alerts) > self.max_alerts:
            self._alerts = self._alerts[-self.max_alerts:]

    def _dispatch_alert(self, alert: Alert) -> None:
        """分发预警到处理器"""
        for handler in self._handlers.get(alert.level, []):
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def acknowledge(self, alert_index: int) -> bool:
        """确认预警"""
        if 0 <= alert_index < len(self._alerts):
            self._alerts[alert_index].acknowledged = True
            return True
        return False

    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取未确认的有效预警"""
        alerts = [a for a in self._alerts if not a.acknowledged]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def get_recent_alerts(self, n: int = 50) -> List[Alert]:
        """获取最近预警"""
        return self._alerts[-n:]

    def _count_level(self, level: AlertLevel) -> int:
        return sum(1 for a in self._alerts if a.level == level)

    def get_alert_stats(self) -> Dict[str, Any]:
        """获取预警统计"""
        stats = {level.value: self._count_level(level) for level in AlertLevel}
        stats["total"] = len(self._alerts)
        stats["active"] = len(self.get_active_alerts())
        return stats

    def reset_debounce(self, alert_type: Optional[AlertType] = None) -> None:
        """重置去抖动计数器"""
        if alert_type:
            self._debounce_counters.pop(alert_type.value, None)
        else:
            self._debounce_counters.clear()


class SystemAnomalyMonitor:
    """
    系统异常监控器

    整合异常检测和预警管理，提供统一接口
    """

    def __init__(
        self,
        detector_window_size: int = 30,
        alert_debounce: int = 3,
        alert_cooldown: float = 60.0,
    ) -> None:
        self.detector = AnomalyDetector(window_size=detector_window_size)
        self.alert_manager = AlertManager(
            debounce_count=alert_debounce,
            cooldown_seconds=alert_cooldown,
        )
        self.thresholds = {
            "error_rate": {"max": 0.5, "warning": 0.2},
            "latency_ms": {"max": 5000, "warning": 1000},
            "cpu_usage": {"max": 0.9, "warning": 0.7},
            "memory_usage": {"max": 0.9, "warning": 0.8},
        }

    def _resolve_alert_type(self, metric_name: str) -> AlertType:
        """根据指标名解析预警类型"""
        if "usage" in metric_name:
            return AlertType.RESOURCE_EXHAUSTION
        return AlertType.ERROR_RATE_SPIKE

    def _threshold_alert_details(self, metric_name: str, value: float, threshold: float) -> Dict:
        return {"metric": metric_name, "value": value, "threshold": threshold}

    def _check_threshold_violation(self, metric_name: str, value: float) -> None:
        """检查阈值违规"""
        threshold = self.thresholds.get(metric_name)
        if not threshold:
            return
        is_violation, _ = self.detector.check_threshold(
            metric_name, max_val=threshold.get("max")
        )
        if not is_violation:
            return
        alert_type = self._resolve_alert_type(metric_name)
        self.alert_manager.check_and_alert(
            alert_type=alert_type,
            level=AlertLevel.CRITICAL,
            message=f"{metric_name} exceeded threshold: {value:.3f}",
            details=self._threshold_alert_details(metric_name, value, threshold["max"]),
        )

    def _z_alert_level(self, z_score: float) -> AlertLevel:
        return AlertLevel.WARNING if abs(z_score) < 3.5 else AlertLevel.CRITICAL

    def _z_alert_details(self, metric_name: str, z_score: float, value: float) -> Dict:
        return {"metric": metric_name, "z_score": z_score, "latest": value}

    def _check_z_score_anomaly(self, metric_name: str, value: float) -> None:
        """检查Z-Score异常"""
        is_anomaly, z_score, direction = self.detector.check_z_score(metric_name)
        if not is_anomaly:
            return
        self.alert_manager.check_and_alert(
            alert_type=AlertType.BEHAVIOR_ANOMALY,
            level=self._z_alert_level(z_score),
            message=f"{metric_name} anomaly detected (z={z_score:.2f})",
            details=self._z_alert_details(metric_name, z_score, value),
        )

    def _trend_alert_details(self, metric_name: str, trend_value: float) -> Dict:
        return {"metric": metric_name, "trend": trend_value}

    def _check_trend_anomaly(self, metric_name: str, value: float) -> None:
        """检查趋势异常"""
        is_trend, trend_value, trend_dir = self.detector.check_trend(metric_name)
        if not is_trend or trend_dir <= 0:
            return
        self.alert_manager.check_and_alert(
            alert_type=AlertType.DEGRADATION,
            level=AlertLevel.WARNING,
            message=f"{metric_name} showing degradation trend",
            details=self._trend_alert_details(metric_name, trend_value),
        )

    def update_metric(self, metric_name: str, value: float) -> None:
        """更新指标并检测异常"""
        self.detector.update(metric_name, value)
        self._check_threshold_violation(metric_name, value)
        self._check_z_score_anomaly(metric_name, value)
        self._check_trend_anomaly(metric_name, value)

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            "detector_windows": list(self.detector._windows.keys()),
            "alert_stats": self.alert_manager.get_alert_stats(),
            "active_alerts": len(self.alert_manager.get_active_alerts()),
        }

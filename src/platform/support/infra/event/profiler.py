"""
性能剖析与瓶颈优化系统

第一性原理：无法度量就无法优化
- 持续收集关键性能指标
- 自动检测瓶颈和异常趋势
- 生成可操作的优化建议

类比：生物的"代谢监测"——持续测量能量消耗和效率，
自动调节资源分配以维持最优状态
"""

import time
import threading
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from collections import deque


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: float
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """性能报告"""
    period_start: float
    period_end: float
    metrics: Dict[str, Dict[str, float]]
    bottlenecks: List[Dict[str, Any]]
    recommendations: List[str]


class ProfilerBase(ABC):
    """性能剖析器抽象基类"""

    @abstractmethod
    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录性能指标"""
        pass

    @abstractmethod
    def get_report(self, duration: float = 60.0) -> PerformanceReport:
        """生成性能报告"""
        pass


class PerformanceProfiler(ProfilerBase):
    """
    性能剖析器

    职责：
    1. 收集和存储性能指标（延迟、吞吐量、错误率）
    2. 计算统计值（均值、P50、P95、P99）
    3. 检测瓶颈和异常趋势
    4. 生成优化建议

    第一性原理：
    - 指标必须持续收集，不能采样丢失
    - 瓶颈必须量化，不能凭感觉
    - 建议必须可操作，不能泛泛而谈
    """

    def _init_thresholds(self, p99: float, error_rate: float) -> None:
        self.bottleneck_threshold_p99 = p99
        self.bottleneck_threshold_error_rate = error_rate

    def _init_metrics(self) -> None:
        self._metrics: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._error_counts: Dict[str, int] = {}
        self._total_counts: Dict[str, int] = {}

    def __init__(
        self,
        max_history: int = 10000,
        bottleneck_threshold_p99: float = 1.0,
        bottleneck_threshold_error_rate: float = 0.05,
    ) -> None:
        self.max_history = max_history
        self._init_thresholds(bottleneck_threshold_p99, bottleneck_threshold_error_rate)
        self._init_metrics()

    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        记录性能指标

        Args:
            name: 指标名称（如 latency_ms, throughput_qps）
            value: 指标值
            labels: 标签（如 {"module": "decision"}）
        """
        if not name:
            raise ValueError("name must not be empty")

        snapshot = MetricSnapshot(
            timestamp=time.time(),
            name=name,
            value=value,
            labels=labels or {},
        )

        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=self.max_history)
            self._metrics[name].append(snapshot)

    def record_error(self, name: str) -> None:
        """记录错误计数"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=self.max_history)
            self._error_counts[name] = self._error_counts.get(name, 0) + 1
            self._total_counts[name] = self._total_counts.get(name, 0) + 1

    def record_success(self, name: str) -> None:
        """记录成功计数"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=self.max_history)
            self._total_counts[name] = self._total_counts.get(name, 0) + 1

    def _compute_percentile(self, durations: List[float], percentile: float) -> float:
        """计算百分位数"""
        threshold = int(len(durations) * percentile)
        return sorted(durations)[threshold] if threshold > 0 else max(durations)

    def _compute_module_stats(self, records: List[MetricSnapshot]) -> Dict[str, Any]:
        """计算单个模块的统计信息"""
        durations = [r.value for r in records]
        avg = sum(durations) / len(durations)
        p95 = self._compute_percentile(durations, 0.95) if len(durations) >= 20 else max(durations)
        p99 = self._compute_percentile(durations, 0.99) if len(durations) >= 100 else max(durations)
        return {
            "count": len(records),
            "avg_ms": round(avg, 2),
            "min_ms": round(min(durations), 2),
            "max_ms": round(max(durations), 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
        }

    def get_stats(self, name: str) -> Dict[str, float]:
        """
        获取指定指标的统计值

        Returns:
            {
                "count": float,
                "mean": float,
                "min": float,
                "max": float,
                "p50": float,
                "p95": float,
                "p99": float,
                "error_rate": float,
            }
        """
        with self._lock:
            queue = self._metrics.get(name)
            total = self._total_counts.get(name, 0)
            errors = self._error_counts.get(name, 0)
            error_rate = errors / max(total, 1)

            if not queue:
                return {
                    "count": 0.0,
                    "mean": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                    "error_rate": error_rate,
                }

            values = [s.value for s in queue]
            values.sort()
            count = len(values)

            return {
                "count": float(count),
                "mean": statistics.mean(values),
                "min": values[0],
                "max": values[-1],
                "p50": self._percentile(values, 0.5),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99),
                "error_rate": error_rate,
            }

    def _percentile(self, sorted_values: List[float], p: float) -> float:
        """计算百分位数"""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f
        if f == c:
            return sorted_values[f]
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """获取所有指标的统计值"""
        with self._lock:
            names = list(self._metrics.keys())
        return {name: self.get_stats(name) for name in names}

    def _check_latency_bottleneck(self, name: str, stat: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """检查延迟瓶颈"""
        if stat["p99"] > self.bottleneck_threshold_p99:
            return {
                "type": "high_latency",
                "metric": name,
                "p99": stat["p99"],
                "threshold": self.bottleneck_threshold_p99,
                "severity": "high" if stat["p99"] > self.bottleneck_threshold_p99 * 2 else "medium",
            }
        return None

    def _check_error_bottleneck(self, name: str, stat: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """检查错误率瓶颈"""
        if stat["error_rate"] > self.bottleneck_threshold_error_rate:
            return {
                "type": "high_error_rate",
                "metric": name,
                "error_rate": stat["error_rate"],
                "threshold": self.bottleneck_threshold_error_rate,
                "severity": "high" if stat["error_rate"] > 0.1 else "medium",
            }
        return None

    def _detect_trend(self, name: str) -> Optional[Dict[str, Any]]:
        """检测指标恶化趋势（线性回归斜率）"""
        recent = self.get_recent_values(name, n=50)
        if len(recent) < 20:
            return None
        slope = self._compute_slope(recent)
        if slope is None or slope <= 0.1:
            return None
        return self._build_trend_result(name, slope)

    def _compute_slope(self, values: List[float]) -> Optional[float]:
        """计算线性回归斜率"""
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return None
        return numerator / denominator

    def _build_trend_result(self, name: str, slope: float) -> Dict[str, Any]:
        """构建趋势结果"""
        return {
            "type": "worsening_trend",
            "metric": name,
            "slope": round(slope, 4),
            "severity": "high" if slope > 0.5 else "medium",
        }

    def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        检测性能瓶颈

        检测规则：
        1. P99延迟超过阈值
        2. 错误率超过阈值
        3. 指标值持续上升（趋势检测）
        """
        bottlenecks = []
        stats = self.get_all_stats()

        for name, stat in stats.items():
            if stat["count"] < 10:
                continue
            latency = self._check_latency_bottleneck(name, stat)
            if latency:
                bottlenecks.append(latency)
            error = self._check_error_bottleneck(name, stat)
            if error:
                bottlenecks.append(error)
            trend = self._detect_trend(name)
            if trend:
                bottlenecks.append(trend)

        return bottlenecks

    def _generate_latency_recommendation(self, bottleneck: Dict[str, Any]) -> str:
        """生成延迟优化建议"""
        metric = bottleneck["metric"]
        return (
            f"[{metric}] P99延迟过高({bottleneck['p99']:.2f})，"
            f"建议优化算法复杂度或增加并发"
        )

    def _generate_error_recommendation(self, bottleneck: Dict[str, Any]) -> str:
        """生成错误率优化建议"""
        metric = bottleneck["metric"]
        return (
            f"[{metric}] 错误率过高({bottleneck['error_rate']:.2%})，"
            f"建议检查异常处理和重试机制"
        )

    def _generate_trend_recommendation(self, bottleneck: Dict[str, Any]) -> str:
        """生成趋势恶化优化建议"""
        metric = bottleneck["metric"]
        return (
            f"[{metric}] 指标持续恶化(斜率={bottleneck['slope']:.4f})，"
            f"建议排查近期变更或资源泄漏"
        )

    def generate_recommendations(self, bottlenecks: List[Dict[str, Any]]) -> List[str]:
        """根据瓶颈生成优化建议"""
        recommendations = []
        for bottleneck in bottlenecks:
            btype = bottleneck["type"]
            if btype == "high_latency":
                recommendations.append(self._generate_latency_recommendation(bottleneck))
            elif btype == "high_error_rate":
                recommendations.append(self._generate_error_recommendation(bottleneck))
            elif btype == "worsening_trend":
                recommendations.append(self._generate_trend_recommendation(bottleneck))
        return recommendations

    def _build_report(self, now: float, duration: float, stats: Dict[str, Dict[str, float]], bottlenecks: List[Dict[str, Any]], recommendations: List[str]) -> PerformanceReport:
        """构建性能报告"""
        return PerformanceReport(
            period_start=now - duration,
            period_end=now,
            metrics=stats,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
        )

    def get_report(self, duration: float = 60.0) -> PerformanceReport:
        """
        生成性能报告

        Args:
            duration: 报告时间窗口（秒）
        """
        now = time.time()
        stats = self.get_all_stats()
        bottlenecks = self.detect_bottlenecks()
        recommendations = self.generate_recommendations(bottlenecks)
        return self._build_report(now, duration, stats, bottlenecks, recommendations)

    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._metrics.clear()
            self._error_counts.clear()
            self._total_counts.clear()
            self._start_time = time.time()

    def get_metric_names(self) -> List[str]:
        """获取所有指标名称"""
        with self._lock:
            return list(self._metrics.keys())

    def get_recent_values(self, name: str, n: int = 100) -> List[float]:
        """获取最近n个指标值"""
        with self._lock:
            queue = self._metrics.get(name)
            if not queue:
                return []
            return [s.value for s in list(queue)[-n:]]

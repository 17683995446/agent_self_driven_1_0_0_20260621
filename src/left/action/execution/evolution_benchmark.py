"""
进化监控性能基准

第一性原理：监控系统的开销不能超过被监控系统收益的1%
- 指标计算必须在10ms内完成
- 趋势检测必须在5ms内完成
- 报告生成必须在20ms内完成

类比：生物的"反射弧"——感知必须足够快，否则无法及时反应
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from ....platform.support.models.base.state import (
    EnvironmentState, DriveRewards, GapState,
)
from .monitor import EvolutionMonitor, EvolutionMetrics, EvolutionTrend


@dataclass
class BenchmarkResult:
    """基准测试结果"""

    name: str
    iterations: int
    total_time: float
    avg_time: float
    max_time: float
    min_time: float
    threshold: float
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "avg_time": self.avg_time,
            "max_time": self.max_time,
            "min_time": self.min_time,
            "threshold": self.threshold,
            "passed": self.passed,
        }


class EvolutionMonitorBenchmark:
    """
    进化监控性能基准测试

    第一性原理：监控开销必须可度量且受控
    """

    METRICS_THRESHOLD: float = 0.01
    TREND_THRESHOLD: float = 0.005
    REPORT_THRESHOLD: float = 0.02
    UPDATE_THRESHOLD: float = 0.001

    def __init__(self, monitor: Optional[EvolutionMonitor] = None) -> None:
        self.monitor = monitor or EvolutionMonitor()

    def benchmark_metrics_computation(self, iterations: int = 1000) -> BenchmarkResult:
        """基准测试指标计算速度"""
        self._prepare_monitor(iterations)
        times = self._measure(self._compute_metrics_once, iterations)
        return self._build_result("metrics_computation", iterations, times, self.METRICS_THRESHOLD)

    def _prepare_monitor(self, iterations: int) -> None:
        """准备监控器数据"""
        for _ in range(max(iterations, 100)):
            self.monitor.update(
                EnvironmentState(), DriveRewards(), GapState(),
                prediction_error=0.1,
            )

    def _compute_metrics_once(self) -> None:
        """单次指标计算"""
        self.monitor._compute_metrics(EnvironmentState())

    def benchmark_trend_detection(self, iterations: int = 100) -> BenchmarkResult:
        """基准测试趋势检测速度"""
        self._prepare_monitor(200)
        times = self._measure(self.monitor.detect_trend, iterations)
        return self._build_result("trend_detection", iterations, times, self.TREND_THRESHOLD)

    def benchmark_report_generation(self, iterations: int = 100) -> BenchmarkResult:
        """基准测试报告生成速度"""
        self._prepare_monitor(100)
        times = self._measure(self.monitor.generate_report, iterations)
        return self._build_result("report_generation", iterations, times, self.REPORT_THRESHOLD)

    def benchmark_update(self, iterations: int = 1000) -> BenchmarkResult:
        """基准测试单次更新速度"""
        times = self._measure(self._update_once, iterations)
        return self._build_result("update", iterations, times, self.UPDATE_THRESHOLD)

    def _update_once(self) -> None:
        """单次更新"""
        self.monitor.update(
            EnvironmentState(), DriveRewards(), GapState(),
            prediction_error=0.1,
        )

    def _measure(self, func: Callable[[], Any], iterations: int) -> List[float]:
        """测量函数执行时间"""
        times: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            times.append(time.perf_counter() - start)
        return times

    def _build_result(
        self,
        name: str,
        iterations: int,
        times: List[float],
        threshold: float,
    ) -> BenchmarkResult:
        """构建基准测试结果"""
        total = sum(times)
        avg = total / max(len(times), 1)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total,
            avg_time=avg,
            max_time=max(times) if times else 0.0,
            min_time=min(times) if times else 0.0,
            threshold=threshold,
            passed=avg < threshold,
        )

    def run_all(self) -> List[BenchmarkResult]:
        """运行全部基准测试"""
        return [
            self.benchmark_update(500),
            self.benchmark_metrics_computation(500),
            self.benchmark_trend_detection(50),
            self.benchmark_report_generation(50),
        ]

    def summary(self) -> Dict[str, Any]:
        """生成基准测试摘要"""
        results = self.run_all()
        return {
            "total_benchmarks": len(results),
            "all_passed": all(r.passed for r in results),
            "results": [r.to_dict() for r in results],
        }

"""
进化监控性能基准测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.execution.evolution_benchmark import (
    EvolutionMonitorBenchmark,
    BenchmarkResult,
)
from src.left.action.execution.monitor import EvolutionMonitor
from src.platform.support.models.base.state import (
    EnvironmentState, DriveRewards, GapState,
)


class TestBenchmarkResult:
    """测试基准测试结果"""

    def test_normal_creation(self):
        """测试正常创建"""
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time=0.5,
            avg_time=0.005,
            max_time=0.01,
            min_time=0.001,
            threshold=0.01,
            passed=True,
        )
        assert result.name == "test"
        assert result.passed is True

    def test_to_dict(self):
        """测试序列化"""
        result = BenchmarkResult(
            name="test",
            iterations=10,
            total_time=0.1,
            avg_time=0.01,
            max_time=0.02,
            min_time=0.005,
            threshold=0.05,
            passed=False,
        )
        data = result.to_dict()
        assert data["name"] == "test"
        assert data["passed"] is False
        assert data["iterations"] == 10

    def test_boundary_zero_iterations(self):
        """测试零迭代边界"""
        result = BenchmarkResult(
            name="empty",
            iterations=0,
            total_time=0.0,
            avg_time=0.0,
            max_time=0.0,
            min_time=0.0,
            threshold=0.01,
            passed=True,
        )
        assert result.iterations == 0


class TestEvolutionMonitorBenchmark:
    """测试进化监控基准测试"""

    def setup_method(self):
        self.benchmark = EvolutionMonitorBenchmark()

    def test_benchmark_update(self):
        """测试更新基准"""
        result = self.benchmark.benchmark_update(10)
        assert result.name == "update"
        assert result.iterations == 10
        assert result.total_time >= 0.0

    def test_benchmark_metrics_computation(self):
        """测试指标计算基准"""
        result = self.benchmark.benchmark_metrics_computation(10)
        assert result.name == "metrics_computation"
        assert result.iterations == 10
        assert result.avg_time >= 0.0

    def test_benchmark_trend_detection(self):
        """测试趋势检测基准"""
        result = self.benchmark.benchmark_trend_detection(10)
        assert result.name == "trend_detection"
        assert result.iterations == 10

    def test_benchmark_report_generation(self):
        """测试报告生成基准"""
        result = self.benchmark.benchmark_report_generation(10)
        assert result.name == "report_generation"
        assert result.iterations == 10

    def test_run_all(self):
        """测试运行全部基准"""
        results = self.benchmark.run_all()
        assert len(results) == 4
        names = [r.name for r in results]
        assert "update" in names
        assert "metrics_computation" in names

    def test_summary(self):
        """测试摘要生成"""
        summary = self.benchmark.summary()
        assert summary["total_benchmarks"] == 4
        assert "all_passed" in summary
        assert len(summary["results"]) == 4

    def test_with_custom_monitor(self):
        """测试自定义监控器"""
        monitor = EvolutionMonitor(window_size=50)
        benchmark = EvolutionMonitorBenchmark(monitor=monitor)
        result = benchmark.benchmark_update(5)
        assert result.iterations == 5

    def test_empty_measure(self):
        """测试空测量"""
        times = self.benchmark._measure(lambda: None, 0)
        assert times == []

    def test_build_result_with_empty_times(self):
        """测试空时间列表构建结果"""
        result = self.benchmark._build_result("empty", 0, [], 0.01)
        assert result.iterations == 0
        assert result.max_time == 0.0
        assert result.min_time == 0.0
        assert result.passed is True

    def test_thresholds_are_positive(self):
        """测试阈值为正"""
        assert EvolutionMonitorBenchmark.METRICS_THRESHOLD > 0
        assert EvolutionMonitorBenchmark.TREND_THRESHOLD > 0
        assert EvolutionMonitorBenchmark.REPORT_THRESHOLD > 0
        assert EvolutionMonitorBenchmark.UPDATE_THRESHOLD > 0


class TestBenchmarkPerformance:
    """性能验证测试（宽松阈值，避免环境波动）"""

    def test_update_meets_relaxed_threshold(self):
        """测试更新满足宽松阈值（10ms）"""
        benchmark = EvolutionMonitorBenchmark()
        result = benchmark.benchmark_update(100)
        assert result.avg_time < 0.01

    def test_metrics_computation_meets_relaxed_threshold(self):
        """测试指标计算满足宽松阈值（50ms）"""
        benchmark = EvolutionMonitorBenchmark()
        result = benchmark.benchmark_metrics_computation(50)
        assert result.avg_time < 0.05

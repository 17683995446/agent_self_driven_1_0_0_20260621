"""
性能剖析器测试

验证指标记录、统计计算、瓶颈检测、报告生成
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.support.infra.event.profiler import (
    PerformanceProfiler, ProfilerBase,
    MetricSnapshot, PerformanceReport,
)


class TestProfilerBase:
    """测试抽象基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            ProfilerBase()


class TestProfilerInit:
    """测试初始化"""

    def test_normal_init(self):
        profiler = PerformanceProfiler()
        assert profiler.max_history == 10000

    def test_custom_thresholds(self):
        profiler = PerformanceProfiler(
            bottleneck_threshold_p99=0.5,
            bottleneck_threshold_error_rate=0.01,
        )
        assert profiler.bottleneck_threshold_p99 == 0.5


class TestRecordMetrics:
    """测试记录指标"""

    def test_record_single(self):
        profiler = PerformanceProfiler()
        profiler.record("latency_ms", 10.0)
        assert "latency_ms" in profiler.get_metric_names()

    def test_record_with_labels(self):
        profiler = PerformanceProfiler()
        profiler.record("latency_ms", 10.0, labels={"module": "decision"})
        stats = profiler.get_stats("latency_ms")
        assert stats["count"] == 1.0

    def test_record_multiple(self):
        profiler = PerformanceProfiler()
        for i in range(5):
            profiler.record("latency_ms", float(i))
        stats = profiler.get_stats("latency_ms")
        assert stats["count"] == 5.0

    def test_record_empty_name(self):
        profiler = PerformanceProfiler()
        with pytest.raises(ValueError):
            profiler.record("", 1.0)

    def test_record_different_metrics(self):
        profiler = PerformanceProfiler()
        profiler.record("latency_ms", 10.0)
        profiler.record("throughput_qps", 100.0)
        assert len(profiler.get_metric_names()) == 2


class TestRecordErrors:
    """测试错误记录"""

    def test_record_error_and_success(self):
        profiler = PerformanceProfiler()
        profiler.record_success("api_call")
        profiler.record_success("api_call")
        profiler.record_error("api_call")
        stats = profiler.get_stats("api_call")
        assert stats["error_rate"] == 1 / 3

    def test_error_rate_zero(self):
        profiler = PerformanceProfiler()
        profiler.record_success("api_call")
        stats = profiler.get_stats("api_call")
        assert stats["error_rate"] == 0.0


class TestGetStats:
    """测试统计计算"""

    def test_empty_metric(self):
        profiler = PerformanceProfiler()
        stats = profiler.get_stats("nonexistent")
        assert stats["count"] == 0.0
        assert stats["mean"] == 0.0

    def test_mean_calculation(self):
        profiler = PerformanceProfiler()
        profiler.record("x", 10.0)
        profiler.record("x", 20.0)
        stats = profiler.get_stats("x")
        assert stats["mean"] == 15.0

    def test_min_max(self):
        profiler = PerformanceProfiler()
        profiler.record("x", 5.0)
        profiler.record("x", 15.0)
        profiler.record("x", 10.0)
        stats = profiler.get_stats("x")
        assert stats["min"] == 5.0
        assert stats["max"] == 15.0

    def test_percentiles(self):
        profiler = PerformanceProfiler()
        for i in range(100):
            profiler.record("x", float(i))
        stats = profiler.get_stats("x")
        assert stats["p50"] == 49.5
        assert stats["p95"] == 94.05
        assert stats["p99"] == 98.01

    def test_single_value_percentiles(self):
        profiler = PerformanceProfiler()
        profiler.record("x", 42.0)
        stats = profiler.get_stats("x")
        assert stats["p50"] == 42.0
        assert stats["p99"] == 42.0


class TestDetectBottlenecks:
    """测试瓶颈检测"""

    def test_no_bottlenecks(self):
        profiler = PerformanceProfiler()
        for i in range(20):
            profiler.record("latency_ms", 0.1)
        bottlenecks = profiler.detect_bottlenecks()
        assert len(bottlenecks) == 0

    def test_high_latency_bottleneck(self):
        profiler = PerformanceProfiler(bottleneck_threshold_p99=1.0)
        for i in range(20):
            profiler.record("latency_ms", 2.0)
        bottlenecks = profiler.detect_bottlenecks()
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["type"] == "high_latency"

    def test_high_error_rate_bottleneck(self):
        profiler = PerformanceProfiler(bottleneck_threshold_error_rate=0.05)
        for i in range(20):
            profiler.record("api_call", 0.1)
            if i % 2 == 0:
                profiler.record_error("api_call")
            else:
                profiler.record_success("api_call")
        bottlenecks = profiler.detect_bottlenecks()
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["type"] == "high_error_rate"

    def test_bottleneck_severity_high(self):
        profiler = PerformanceProfiler(bottleneck_threshold_p99=1.0)
        for i in range(20):
            profiler.record("latency_ms", 5.0)
        bottlenecks = profiler.detect_bottlenecks()
        assert bottlenecks[0]["severity"] == "high"

    def test_insufficient_data(self):
        profiler = PerformanceProfiler()
        for i in range(5):
            profiler.record("latency_ms", 10.0)
        bottlenecks = profiler.detect_bottlenecks()
        assert len(bottlenecks) == 0


class TestRecommendations:
    """测试优化建议"""

    def test_latency_recommendation(self):
        profiler = PerformanceProfiler()
        bottlenecks = [{
            "type": "high_latency",
            "metric": "db_query",
            "p99": 2.5,
        }]
        recs = profiler.generate_recommendations(bottlenecks)
        assert len(recs) == 1
        assert "db_query" in recs[0]

    def test_error_rate_recommendation(self):
        profiler = PerformanceProfiler()
        bottlenecks = [{
            "type": "high_error_rate",
            "metric": "api_call",
            "error_rate": 0.08,
        }]
        recs = profiler.generate_recommendations(bottlenecks)
        assert len(recs) == 1
        assert "api_call" in recs[0]

    def test_empty_bottlenecks(self):
        profiler = PerformanceProfiler()
        recs = profiler.generate_recommendations([])
        assert recs == []


class TestGetReport:
    """测试报告生成"""

    def test_report_structure(self):
        profiler = PerformanceProfiler()
        profiler.record("latency_ms", 0.5)
        report = profiler.get_report(duration=60.0)
        assert isinstance(report, PerformanceReport)
        assert "latency_ms" in report.metrics
        assert isinstance(report.bottlenecks, list)
        assert isinstance(report.recommendations, list)

    def test_report_time_range(self):
        profiler = PerformanceProfiler()
        report = profiler.get_report(duration=30.0)
        assert report.period_end > report.period_start
        assert report.period_end - report.period_start == pytest.approx(30.0, abs=1.0)


class TestReset:
    """测试重置"""

    def test_reset_clears_metrics(self):
        profiler = PerformanceProfiler()
        profiler.record("x", 1.0)
        profiler.reset()
        assert profiler.get_metric_names() == []
        stats = profiler.get_stats("x")
        assert stats["count"] == 0.0

    def test_reset_clears_errors(self):
        profiler = PerformanceProfiler()
        profiler.record_error("x")
        profiler.reset()
        stats = profiler.get_stats("x")
        assert stats["error_rate"] == 0.0


class TestGetRecentValues:
    """测试获取最近值"""

    def test_get_recent(self):
        profiler = PerformanceProfiler()
        for i in range(10):
            profiler.record("x", float(i))
        recent = profiler.get_recent_values("x", n=3)
        assert recent == [7.0, 8.0, 9.0]

    def test_get_recent_empty(self):
        profiler = PerformanceProfiler()
        recent = profiler.get_recent_values("x", n=3)
        assert recent == []

    def test_get_recent_more_than_available(self):
        profiler = PerformanceProfiler()
        profiler.record("x", 1.0)
        recent = profiler.get_recent_values("x", n=10)
        assert recent == [1.0]


class TestMaxHistory:
    """测试最大历史限制"""

    def test_max_history_enforced(self):
        profiler = PerformanceProfiler(max_history=5)
        for i in range(10):
            profiler.record("x", float(i))
        stats = profiler.get_stats("x")
        assert stats["count"] == 5.0
        assert stats["min"] == 5.0


class TestTrendDetection:
    """测试趋势检测"""

    def test_no_trend_stable(self):
        profiler = PerformanceProfiler()
        for _ in range(25):
            profiler.record("latency", 1.0)
        bottlenecks = profiler.detect_bottlenecks()
        trend_bottlenecks = [b for b in bottlenecks if b["type"] == "worsening_trend"]
        assert len(trend_bottlenecks) == 0

    def test_worsening_trend_detected(self):
        profiler = PerformanceProfiler()
        for i in range(25):
            profiler.record("latency", float(i))
        bottlenecks = profiler.detect_bottlenecks()
        trend_bottlenecks = [b for b in bottlenecks if b["type"] == "worsening_trend"]
        assert len(trend_bottlenecks) == 1
        assert trend_bottlenecks[0]["metric"] == "latency"
        assert trend_bottlenecks[0]["slope"] > 0.1

    def test_trend_severity_high(self):
        profiler = PerformanceProfiler()
        for i in range(25):
            profiler.record("latency", float(i * 2))
        bottlenecks = profiler.detect_bottlenecks()
        trend_bottlenecks = [b for b in bottlenecks if b["type"] == "worsening_trend"]
        assert trend_bottlenecks[0]["severity"] == "high"

    def test_trend_insufficient_data(self):
        profiler = PerformanceProfiler()
        for i in range(5):
            profiler.record("latency", float(i))
        result = profiler._detect_trend("latency")
        assert result is None

    def test_trend_recommendation(self):
        profiler = PerformanceProfiler()
        bottlenecks = [{
            "type": "worsening_trend",
            "metric": "latency",
            "slope": 0.25,
        }]
        recs = profiler.generate_recommendations(bottlenecks)
        assert len(recs) == 1
        assert "持续恶化" in recs[0]

    def test_boundary_flat_trend(self):
        profiler = PerformanceProfiler()
        for i in range(25):
            profiler.record("latency", 1.0 + i * 0.005)
        result = profiler._detect_trend("latency")
        assert result is None or result["severity"] == "medium"


class TestAllStats:
    """测试获取所有统计"""

    def test_get_all_stats(self):
        profiler = PerformanceProfiler()
        profiler.record("a", 1.0)
        profiler.record("b", 2.0)
        all_stats = profiler.get_all_stats()
        assert "a" in all_stats
        assert "b" in all_stats

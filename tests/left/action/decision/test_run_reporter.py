"""
运行报告生成器测试

第一性原理：测试覆盖四类用例
1. 正常值：典型执行记录生成报告
2. 空入参：无记录、空快照
3. 边界极值：大量记录、所有任务失败/成功
4. 非法格式：异常数据、无效路径
"""

import os
import tempfile
import time
import pytest
from typing import List

from src.left.action.decision.run_reporter import (
    FeedbackLearnerMetricsCollector,
    ImprovementSuggestion,
    ReportMetrics,
    RunReporter,
    SuggestionGenerator,
    TaskExecutionRecord,
    TextReportFormatter,
    TrendAnalysis,
    TrendAnalyzer,
)
from src.left.action.decision.task_feedback_learner import (
    DefaultFeedbackPolicy,
    TaskFeedbackLearner,
)
from src.platform.support.models.base.task import TaskResult


def _make_result(success: bool = True, message: str = "", data: dict = None) -> TaskResult:
    return TaskResult(
        success=success,
        message=message,
        data=data or {},
    )


def _add_records(reporter: RunReporter, count: int, success_rate: float = 1.0) -> None:
    """添加测试记录"""
    for i in range(count):
        success = (i / max(count - 1, 1)) < success_rate
        reporter.record_execution(
            task_name=f"task_{i % 3}",
            result=_make_result(success, f"task {i}"),
            execution_time=0.1 + i * 0.01,
        )


# ===== TaskExecutionRecord 测试 =====


class TestTaskExecutionRecord:
    """任务执行记录测试"""

    def test_to_dict(self) -> None:
        record = TaskExecutionRecord(
            task_name="test",
            success=True,
            timestamp=1000.0,
            execution_time=0.5,
            message="ok",
        )
        d = record.to_dict()
        assert d["task_name"] == "test"
        assert d["success"] is True
        assert d["timestamp"] == 1000.0
        assert d["execution_time"] == 0.5
        assert d["message"] == "ok"

    def test_default_data(self) -> None:
        record = TaskExecutionRecord(
            task_name="x", success=False, timestamp=0.0,
        )
        assert record.data == {}


# ===== ReportMetrics 测试 =====


class TestReportMetrics:
    """报告指标测试"""

    def test_to_dict(self) -> None:
        metrics = ReportMetrics(
            total_tasks=5,
            successful_tasks=4,
            failed_tasks=1,
            total_executions=10,
            success_rate=0.9,
            avg_execution_time=0.5,
            unique_task_types=3,
            suspended_tasks=1,
            degraded_tasks=2,
            promoted_tasks=1,
        )
        d = metrics.to_dict()
        assert d["total_tasks"] == 5
        assert d["success_rate"] == 0.9
        assert d["unique_task_types"] == 3

    def test_defaults(self) -> None:
        metrics = ReportMetrics()
        assert metrics.total_tasks == 0
        assert metrics.success_rate == 0.0


# ===== TrendAnalysis 测试 =====


class TestTrendAnalysis:
    """趋势分析测试"""

    def test_to_dict(self) -> None:
        trend = TrendAnalysis(
            success_trend="rising",
            recent_success_rate=0.9,
            overall_success_rate=0.7,
            improvement=0.2,
        )
        d = trend.to_dict()
        assert d["success_trend"] == "rising"
        assert d["improvement"] == 0.2

    def test_defaults(self) -> None:
        trend = TrendAnalysis()
        assert trend.success_trend == "stable"


# ===== TrendAnalyzer 测试 =====


class TestTrendAnalyzer:
    """趋势分析器测试"""

    def test_empty_records(self) -> None:
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze([], ReportMetrics())
        assert trend.success_trend == "stable"
        assert trend.recent_success_rate == 0.0

    def test_rising_trend(self) -> None:
        """近期成功率高于整体→rising"""
        analyzer = TrendAnalyzer()
        records: List[TaskExecutionRecord] = []
        # 前20条：50%成功
        for i in range(20):
            records.append(TaskExecutionRecord(
                task_name="t", success=(i % 2 == 0), timestamp=float(i),
            ))
        # 后10条：100%成功
        for i in range(10):
            records.append(TaskExecutionRecord(
                task_name="t", success=True, timestamp=float(i + 20),
            ))
        metrics = ReportMetrics(
            total_executions=30,
            successful_tasks=20,
            success_rate=20 / 30,
        )
        trend = analyzer.analyze(records, metrics)
        assert trend.recent_success_rate == 1.0
        assert trend.success_trend == "rising"

    def test_falling_trend(self) -> None:
        """近期成功率低于整体→falling"""
        analyzer = TrendAnalyzer()
        records: List[TaskExecutionRecord] = []
        # 前20条：100%成功
        for i in range(20):
            records.append(TaskExecutionRecord(
                task_name="t", success=True, timestamp=float(i),
            ))
        # 后10条：0%成功
        for i in range(10):
            records.append(TaskExecutionRecord(
                task_name="t", success=False, timestamp=float(i + 20),
            ))
        metrics = ReportMetrics(
            total_executions=30,
            successful_tasks=20,
            success_rate=20 / 30,
        )
        trend = analyzer.analyze(records, metrics)
        assert trend.recent_success_rate == 0.0
        assert trend.success_trend == "falling"

    def test_stable_trend(self) -> None:
        """成功率一致→stable"""
        analyzer = TrendAnalyzer()
        records: List[TaskExecutionRecord] = []
        for i in range(30):
            records.append(TaskExecutionRecord(
                task_name="t", success=True, timestamp=float(i),
            ))
        metrics = ReportMetrics(
            total_executions=30,
            successful_tasks=30,
            success_rate=1.0,
        )
        trend = analyzer.analyze(records, metrics)
        assert trend.success_trend == "stable"


# ===== SuggestionGenerator 测试 =====


class TestSuggestionGenerator:
    """改进建议生成器测试"""

    def test_no_suggestions_when_healthy(self) -> None:
        """健康状态无建议"""
        gen = SuggestionGenerator()
        metrics = ReportMetrics(
            unique_task_types=5,
            success_rate=0.95,
            avg_execution_time=0.5,
            suspended_tasks=0,
        )
        trend = TrendAnalysis(success_trend="stable")
        suggestions = gen.generate(metrics, trend, {})
        # 趋势稳定且健康，应无建议或仅有少量低优先级建议
        high_priority = [s for s in suggestions if s.priority == "high"]
        assert len(high_priority) == 0

    def test_low_diversity_suggestion(self) -> None:
        """任务多样性不足建议"""
        gen = SuggestionGenerator()
        metrics = ReportMetrics(unique_task_types=2)
        suggestions = gen.generate(metrics, TrendAnalysis(), {})
        diversity_suggestions = [s for s in suggestions if s.category == "diversity"]
        assert len(diversity_suggestions) >= 1
        assert diversity_suggestions[0].priority == "high"

    def test_low_success_rate_suggestion(self) -> None:
        """成功率过低建议"""
        gen = SuggestionGenerator()
        metrics = ReportMetrics(success_rate=0.3)
        suggestions = gen.generate(metrics, TrendAnalysis(), {})
        reliability_suggestions = [s for s in suggestions if s.category == "reliability"]
        assert any(s.title == "成功率过低" for s in reliability_suggestions)

    def test_suspended_tasks_suggestion(self) -> None:
        """暂停任务建议"""
        gen = SuggestionGenerator()
        metrics = ReportMetrics(suspended_tasks=2)
        task_stats = {
            "task_a": {"status": "suspended"},
            "task_b": {"status": "suspended"},
        }
        suggestions = gen.generate(metrics, TrendAnalysis(), task_stats)
        suspended_suggestions = [s for s in suggestions if "暂停" in s.title]
        assert len(suspended_suggestions) >= 1

    def test_slow_execution_suggestion(self) -> None:
        """执行时间过长建议"""
        gen = SuggestionGenerator()
        metrics = ReportMetrics(avg_execution_time=10.0)
        suggestions = gen.generate(metrics, TrendAnalysis(), {})
        perf_suggestions = [s for s in suggestions if s.category == "performance"]
        assert any("执行时间" in s.title for s in perf_suggestions)

    def test_falling_trend_suggestion(self) -> None:
        """下降趋势建议"""
        gen = SuggestionGenerator()
        trend = TrendAnalysis(
            success_trend="falling",
            recent_success_rate=0.4,
            overall_success_rate=0.8,
        )
        suggestions = gen.generate(ReportMetrics(), trend, {})
        trend_suggestions = [s for s in suggestions if "下降" in s.title]
        assert len(trend_suggestions) >= 1
        assert trend_suggestions[0].priority == "high"

    def test_rising_trend_suggestion(self) -> None:
        """上升趋势建议"""
        gen = SuggestionGenerator()
        trend = TrendAnalysis(
            success_trend="rising",
            recent_success_rate=0.9,
            overall_success_rate=0.6,
        )
        suggestions = gen.generate(ReportMetrics(), trend, {})
        trend_suggestions = [s for s in suggestions if "上升" in s.title]
        assert len(trend_suggestions) >= 1
        assert trend_suggestions[0].priority == "low"


# ===== TextReportFormatter 测试 =====


class TestTextReportFormatter:
    """文本报告格式化器测试"""

    def test_format_contains_header(self) -> None:
        fmt = TextReportFormatter()
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), [], {}, 1000.0, 1005.0,
        )
        assert "运行报告" in report
        assert "运行时长" in report

    def test_format_contains_summary(self) -> None:
        fmt = TextReportFormatter()
        metrics = ReportMetrics(
            total_executions=10,
            successful_tasks=8,
            success_rate=0.8,
            unique_task_types=3,
        )
        report = fmt.format(metrics, TrendAnalysis(), [], {}, 1000.0, 1005.0)
        assert "运行摘要" in report
        assert "10" in report
        assert "80.0%" in report

    def test_format_contains_trend(self) -> None:
        fmt = TextReportFormatter()
        trend = TrendAnalysis(success_trend="rising", recent_success_rate=0.9)
        report = fmt.format(
            ReportMetrics(), trend, [], {}, 1000.0, 1005.0,
        )
        assert "趋势分析" in report
        assert "rising" in report

    def test_format_contains_task_details(self) -> None:
        fmt = TextReportFormatter()
        task_stats = {
            "task_a": {
                "total_executions": 5,
                "success_count": 4,
                "failure_count": 1,
                "success_rate": 0.8,
                "status": "active",
                "priority_multiplier": 1.0,
            },
        }
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), [], task_stats, 1000.0, 1005.0,
        )
        assert "任务详情" in report
        assert "task_a" in report

    def test_format_contains_suggestions(self) -> None:
        fmt = TextReportFormatter()
        suggestions = [
            ImprovementSuggestion(
                category="reliability",
                priority="high",
                title="测试建议",
                description="测试描述",
                action="测试行动",
            ),
        ]
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), suggestions, {}, 1000.0, 1005.0,
        )
        assert "改进建议" in report
        assert "测试建议" in report
        assert "HIGH" in report

    def test_format_empty_task_stats(self) -> None:
        """空任务统计"""
        fmt = TextReportFormatter()
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), [], {}, 1000.0, 1005.0,
        )
        assert "无任务记录" in report

    def test_format_empty_suggestions(self) -> None:
        """空建议"""
        fmt = TextReportFormatter()
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), [], {}, 1000.0, 1005.0,
        )
        assert "系统运行良好" in report

    def test_format_contains_footer(self) -> None:
        fmt = TextReportFormatter()
        report = fmt.format(
            ReportMetrics(), TrendAnalysis(), [], {}, 1000.0, 1005.0,
        )
        assert "报告结束" in report


# ===== RunReporter 测试 =====


class TestRunReporter:
    """运行报告生成器测试"""

    def test_record_execution(self) -> None:
        reporter = RunReporter()
        reporter.record_execution("task_a", _make_result(True, "ok"), 0.5)
        records = reporter.get_records()
        assert len(records) == 1
        assert records[0].task_name == "task_a"
        assert records[0].success is True

    def test_record_multiple_executions(self) -> None:
        reporter = RunReporter()
        for i in range(5):
            reporter.record_execution(
                f"task_{i % 2}", _make_result(True), 0.1,
            )
        records = reporter.get_records()
        assert len(records) == 5

    def test_get_metrics_empty(self) -> None:
        reporter = RunReporter()
        metrics = reporter.get_metrics()
        assert metrics.total_executions == 0
        assert metrics.success_rate == 0.0

    def test_get_metrics_with_records(self) -> None:
        reporter = RunReporter()
        reporter.record_execution("a", _make_result(True), 0.1)
        reporter.record_execution("a", _make_result(False), 0.2)
        reporter.record_execution("b", _make_result(True), 0.3)
        metrics = reporter.get_metrics()
        assert metrics.total_executions == 3
        assert metrics.successful_tasks == 2
        assert metrics.failed_tasks == 1
        assert metrics.success_rate == 2 / 3
        assert metrics.unique_task_types == 2
        assert metrics.avg_execution_time > 0

    def test_generate_report_empty(self) -> None:
        reporter = RunReporter()
        report = reporter.generate_report()
        assert "运行报告" in report
        assert "运行摘要" in report

    def test_generate_report_with_data(self) -> None:
        reporter = RunReporter()
        _add_records(reporter, 10, success_rate=0.8)
        report = reporter.generate_report()
        assert "运行报告" in report
        assert "运行摘要" in report
        assert "趋势分析" in report
        assert "改进建议" in report

    def test_save_report(self) -> None:
        reporter = RunReporter()
        _add_records(reporter, 5)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "report.txt")
            saved_path = reporter.save_report(path)
            assert saved_path == path
            assert os.path.isfile(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "运行报告" in content

    def test_save_report_creates_directory(self) -> None:
        reporter = RunReporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "deep", "nested", "dir", "report.txt")
            reporter.save_report(path)
            assert os.path.isfile(path)

    def test_collect_from_learner(self) -> None:
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        for _ in range(3):
            learner.record_result("task_x", _make_result(True))
        reporter.collect_from_learner(learner)
        metrics = reporter.get_metrics()
        assert metrics.total_tasks == 1

    def test_collect_from_learner_with_failures(self) -> None:
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        # 连续失败3次→暂停
        for _ in range(3):
            learner.record_result("task_fail", _make_result(False))
        reporter.collect_from_learner(learner)
        metrics = reporter.get_metrics()
        assert metrics.suspended_tasks >= 1

    def test_reset(self) -> None:
        reporter = RunReporter()
        reporter.record_execution("a", _make_result(True), 0.1)
        reporter.reset()
        assert len(reporter.get_records()) == 0

    def test_report_includes_suspended_in_metrics(self) -> None:
        """报告指标包含暂停任务数"""
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        for _ in range(3):
            learner.record_result("task_s", _make_result(False))
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "暂停任务数" in report

    def test_report_includes_suggestions(self) -> None:
        """报告包含改进建议"""
        reporter = RunReporter()
        # 只记录1种任务，触发多样性建议
        reporter.record_execution("only_task", _make_result(True), 0.1)
        report = reporter.generate_report()
        assert "改进建议" in report

    def test_full_workflow(self) -> None:
        """完整工作流测试"""
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        # 模拟执行
        for i in range(10):
            success = i % 3 != 0  # 67%成功率
            result = _make_result(success, f"task {i}")
            reporter.record_execution(f"task_{i % 3}", result, 0.1 + i * 0.01)
            learner.record_result(f"task_{i % 3}", result)
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        # 验证报告结构完整
        assert "运行报告" in report
        assert "运行摘要" in report
        assert "趋势分析" in report
        assert "任务详情" in report
        assert "改进建议" in report
        assert "报告结束" in report

    def test_metrics_reflect_records(self) -> None:
        """指标反映记录"""
        reporter = RunReporter()
        reporter.record_execution("a", _make_result(True), 0.5)
        reporter.record_execution("a", _make_result(True), 0.3)
        reporter.record_execution("b", _make_result(False), 0.2)
        metrics = reporter.get_metrics()
        assert metrics.total_executions == 3
        assert metrics.successful_tasks == 2
        assert metrics.failed_tasks == 1
        assert abs(metrics.success_rate - 2 / 3) < 0.01
        assert metrics.unique_task_types == 2


# ===== FeedbackLearnerMetricsCollector 测试 =====


class TestFeedbackLearnerMetricsCollector:
    """反馈学习器指标收集器测试"""

    def test_collect_empty(self) -> None:
        learner = TaskFeedbackLearner()
        collector = FeedbackLearnerMetricsCollector(learner)
        data = collector.collect()
        assert data["task_stats"] == {}
        assert data["history_count"] == 0

    def test_collect_with_data(self) -> None:
        learner = TaskFeedbackLearner()
        learner.record_result("task_a", _make_result(True))
        learner.record_result("task_a", _make_result(False))
        collector = FeedbackLearnerMetricsCollector(learner)
        data = collector.collect()
        assert "task_a" in data["task_stats"]
        stats = data["task_stats"]["task_a"]
        assert stats["total_executions"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert data["history_count"] == 2


# ===== 端到端场景测试 =====


class TestEndToEndScenarios:
    """端到端场景测试"""

    def test_scenario_all_success(self) -> None:
        """场景：全部成功"""
        reporter = RunReporter()
        for i in range(10):
            reporter.record_execution(f"task_{i % 3}", _make_result(True), 0.1)
        report = reporter.generate_report()
        metrics = reporter.get_metrics()
        assert metrics.success_rate == 1.0
        assert "100.0%" in report

    def test_scenario_all_failure(self) -> None:
        """场景：全部失败"""
        reporter = RunReporter()
        for i in range(10):
            reporter.record_execution(f"task_{i % 3}", _make_result(False), 0.1)
        report = reporter.generate_report()
        metrics = reporter.get_metrics()
        assert metrics.success_rate == 0.0
        assert "成功率过低" in report

    def test_scenario_mixed_with_suspended(self) -> None:
        """场景：混合结果+暂停任务"""
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        # task_a连续失败3次
        for _ in range(3):
            result = _make_result(False)
            reporter.record_execution("task_a", result, 0.1)
            learner.record_result("task_a", result)
        # task_b成功
        for _ in range(5):
            result = _make_result(True)
            reporter.record_execution("task_b", result, 0.1)
            learner.record_result("task_b", result)
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "暂停" in report
        assert "task_a" in report

    def test_scenario_save_and_read(self) -> None:
        """场景：保存并读取报告"""
        reporter = RunReporter()
        _add_records(reporter, 20, success_rate=0.7)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.txt")
            reporter.save_report(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 100
            assert "运行报告" in content
            assert "任务详情" in content

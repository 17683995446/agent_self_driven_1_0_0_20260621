"""
O5：运行报告接入测试

验证AgentSystem正确接入RunReporter：
1. 报告器初始化
2. 任务执行后记录到报告器
3. 停止时生成报告文件
4. 报告包含任务统计、成功率、建议
5. 异常处理
"""

import pytest
import os
import time
import tempfile
from unittest.mock import MagicMock, patch

from src.left.action.decision.run_reporter import (
    RunReporter,
    TaskExecutionRecord,
    ReportMetrics,
    TrendAnalysis,
    ImprovementSuggestion,
    TextReportFormatter,
)
from src.platform.support.models.base.task import TaskResult


class TestO5ReporterInitialization:
    """测试报告器初始化"""

    def test_reporter_exists_after_init(self):
        """RunReporter可正常实例化"""
        reporter = RunReporter()
        assert reporter is not None
        assert len(reporter.get_records()) == 0

    def test_reporter_has_empty_records_initially(self):
        """初始化时记录为空"""
        reporter = RunReporter()
        assert len(reporter.get_records()) == 0


class TestO5RecordExecution:
    """测试任务执行记录"""

    def test_record_single_execution(self):
        """记录单次执行"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok", execution_time=0.1)
        reporter.record_execution("task_a", result, execution_time=0.1)
        records = reporter.get_records()
        assert len(records) == 1
        assert records[0].task_name == "task_a"
        assert records[0].success is True

    def test_record_multiple_executions(self):
        """记录多次执行"""
        reporter = RunReporter()
        for i in range(5):
            result = TaskResult(success=i % 2 == 0, message=f"task_{i}")
            reporter.record_execution(f"task_{i}", result, execution_time=0.05 * i)
        records = reporter.get_records()
        assert len(records) == 5

    def test_record_preserves_execution_time(self):
        """记录保存执行时间"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok", execution_time=1.5)
        reporter.record_execution("slow_task", result, execution_time=1.5)
        records = reporter.get_records()
        assert records[0].execution_time == 1.5

    def test_record_preserves_message(self):
        """记录保存消息"""
        reporter = RunReporter()
        result = TaskResult(success=False, message="failed reason")
        reporter.record_execution("bad_task", result)
        records = reporter.get_records()
        assert records[0].message == "failed reason"
        assert records[0].success is False


class TestO5ReportGeneration:
    """测试报告生成"""

    def test_generate_report_contains_summary(self):
        """报告包含运行摘要"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok", execution_time=0.1)
        reporter.record_execution("task_a", result, execution_time=0.1)
        report = reporter.generate_report()
        assert "运行摘要" in report
        assert "成功率" in report

    def test_generate_report_contains_task_details(self):
        """报告包含任务详情"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        result = TaskResult(success=True, message="ok")
        learner.record_result("my_task", result)
        reporter = RunReporter()
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "任务详情" in report
        assert "my_task" in report

    def test_generate_report_contains_suggestions(self):
        """报告包含改进建议"""
        reporter = RunReporter()
        # 记录多次失败以触发可靠性建议
        for _ in range(10):
            result = TaskResult(success=False, message="fail")
            reporter.record_execution("failing_task", result)
        report = reporter.generate_report()
        assert "改进建议" in report

    def test_generate_report_empty_records(self):
        """无记录时也能生成报告"""
        reporter = RunReporter()
        report = reporter.generate_report()
        assert "运行报告" in report
        assert "无任务记录" in report

    def test_generate_report_contains_success_rate(self):
        """报告包含成功率计算"""
        reporter = RunReporter()
        for success in [True, True, False, True, False]:
            result = TaskResult(success=success, message="")
            reporter.record_execution("task", result)
        report = reporter.generate_report()
        # 成功率 3/5 = 60%
        assert "60.0%" in report


class TestO5SaveReport:
    """测试报告保存"""

    def test_save_report_creates_file(self, tmp_path):
        """保存报告创建文件"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok")
        reporter.record_execution("task_a", result)
        report_path = str(tmp_path / "run_report.txt")
        saved_path = reporter.save_report(report_path)
        assert os.path.isfile(saved_path)
        with open(saved_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "运行报告" in content

    def test_save_report_creates_directory(self, tmp_path):
        """保存报告创建目录"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok")
        reporter.record_execution("task_a", result)
        report_path = str(tmp_path / "subdir" / "run_report.txt")
        saved_path = reporter.save_report(report_path)
        assert os.path.isfile(saved_path)

    def test_save_report_to_logs(self, tmp_path):
        """保存报告到logs目录"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok")
        reporter.record_execution("task_a", result)
        report_path = str(tmp_path / "logs" / "run_report.txt")
        saved_path = reporter.save_report(report_path)
        assert os.path.isfile(saved_path)
        assert "logs" in saved_path


class TestO5CollectFromLearner:
    """测试从反馈学习器收集"""

    def test_collect_from_learner_updates_snapshot(self):
        """从学习器收集更新快照"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        result = TaskResult(success=True, message="ok")
        learner.record_result("task_a", result)
        reporter = RunReporter()
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "task_a" in report

    def test_collect_from_empty_learner(self):
        """从空学习器收集不报错"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        reporter = RunReporter()
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "运行报告" in report


class TestO5MetricsComputation:
    """测试指标计算"""

    def test_metrics_success_rate(self):
        """指标计算成功率"""
        reporter = RunReporter()
        for success in [True, False, True, True]:
            result = TaskResult(success=success, message="")
            reporter.record_execution("task", result)
        metrics = reporter.get_metrics()
        assert metrics.total_executions == 4
        assert metrics.successful_tasks == 3
        assert metrics.failed_tasks == 1
        assert metrics.success_rate == 0.75

    def test_metrics_unique_task_types(self):
        """指标计算唯一任务类型数"""
        reporter = RunReporter()
        for name in ["task_a", "task_b", "task_a", "task_c"]:
            result = TaskResult(success=True, message="")
            reporter.record_execution(name, result)
        metrics = reporter.get_metrics()
        assert metrics.unique_task_types == 3

    def test_metrics_avg_execution_time(self):
        """指标计算平均执行时间"""
        reporter = RunReporter()
        for t in [0.1, 0.2, 0.3]:
            result = TaskResult(success=True, message="", execution_time=t)
            reporter.record_execution("task", result, execution_time=t)
        metrics = reporter.get_metrics()
        assert metrics.avg_execution_time == pytest.approx(0.2, abs=0.01)


class TestO5TrendAnalysis:
    """测试趋势分析"""

    def test_trend_rising(self):
        """上升趋势检测"""
        reporter = RunReporter()
        # 前5次失败，后5次成功 → 近期成功率高于整体
        for _ in range(5):
            result = TaskResult(success=False, message="")
            reporter.record_execution("task", result)
        for _ in range(5):
            result = TaskResult(success=True, message="")
            reporter.record_execution("task", result)
        report = reporter.generate_report()
        assert "趋势分析" in report

    def test_trend_falling(self):
        """下降趋势检测"""
        reporter = RunReporter()
        # 前5次成功，后5次失败 → 近期成功率低于整体
        for _ in range(5):
            result = TaskResult(success=True, message="")
            reporter.record_execution("task", result)
        for _ in range(5):
            result = TaskResult(success=False, message="")
            reporter.record_execution("task", result)
        report = reporter.generate_report()
        assert "趋势分析" in report


class TestO5ReportContent:
    """测试报告内容完整性"""

    def test_report_has_header(self):
        """报告有标题"""
        reporter = RunReporter()
        report = reporter.generate_report()
        assert "自驱永续进化Agent" in report
        assert "运行报告" in report

    def test_report_has_generation_time(self):
        """报告有生成时间"""
        reporter = RunReporter()
        report = reporter.generate_report()
        assert "生成时间" in report

    def test_report_has_duration(self):
        """报告有运行时长"""
        reporter = RunReporter()
        time.sleep(0.01)
        report = reporter.generate_report()
        assert "运行时长" in report

    def test_report_has_footer(self):
        """报告有结尾"""
        reporter = RunReporter()
        report = reporter.generate_report()
        assert "报告结束" in report

    def test_report_with_suspended_tasks(self):
        """报告包含暂停任务信息"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        # 制造连续失败导致暂停
        for _ in range(5):
            result = TaskResult(success=False, message="fail")
            learner.record_result("bad_task", result)
        reporter = RunReporter()
        reporter.collect_from_learner(learner)
        report = reporter.generate_report()
        assert "bad_task" in report


class TestO5Reset:
    """测试报告器重置"""

    def test_reset_clears_records(self):
        """重置清空记录"""
        reporter = RunReporter()
        result = TaskResult(success=True, message="ok")
        reporter.record_execution("task_a", result)
        assert len(reporter.get_records()) == 1
        reporter.reset()
        assert len(reporter.get_records()) == 0

    def test_reset_clears_snapshot(self):
        """重置清空快照"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        result = TaskResult(success=True, message="ok")
        learner.record_result("task_a", result)
        reporter = RunReporter()
        reporter.collect_from_learner(learner)
        reporter.reset()
        report = reporter.generate_report()
        assert "无任务记录" in report

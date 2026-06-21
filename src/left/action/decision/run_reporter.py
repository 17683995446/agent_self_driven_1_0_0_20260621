"""
运行报告生成器

第一性原理：报告 = 数据 × 结构 × 可读性
- 数据：从TaskFeedbackLearner、DynamicTaskGenerator等收集
- 结构：标题、摘要、统计、趋势、建议
- 可读性：文本格式，便于人类阅读

类比：生物的"记忆整理"——将散乱的感知整合为可回忆的叙事

核心功能：
1. 收集任务执行统计
2. 计算成功率和趋势
3. 生成改进建议
4. 输出文本格式报告
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.task import TaskResult
from .task_feedback_learner import TaskFeedbackLearner, TaskStatistics, TaskStatus


logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionRecord:
    """任务执行记录"""

    task_name: str
    success: bool
    timestamp: float
    execution_time: float = 0.0
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "success": self.success,
            "timestamp": self.timestamp,
            "execution_time": self.execution_time,
            "message": self.message,
        }


@dataclass
class ReportMetrics:
    """报告指标"""

    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_executions: int = 0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    unique_task_types: int = 0
    suspended_tasks: int = 0
    degraded_tasks: int = 0
    promoted_tasks: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_executions": self.total_executions,
            "success_rate": round(self.success_rate, 4),
            "avg_execution_time": round(self.avg_execution_time, 4),
            "unique_task_types": self.unique_task_types,
            "suspended_tasks": self.suspended_tasks,
            "degraded_tasks": self.degraded_tasks,
            "promoted_tasks": self.promoted_tasks,
        }


@dataclass
class TrendAnalysis:
    """趋势分析"""

    success_trend: str = "stable"  # rising | falling | stable
    recent_success_rate: float = 0.0
    overall_success_rate: float = 0.0
    improvement: float = 0.0  # 近期-整体

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_trend": self.success_trend,
            "recent_success_rate": round(self.recent_success_rate, 4),
            "overall_success_rate": round(self.overall_success_rate, 4),
            "improvement": round(self.improvement, 4),
        }


@dataclass
class ImprovementSuggestion:
    """改进建议"""

    category: str  # performance | reliability | diversity | resource
    priority: str  # high | medium | low
    title: str
    description: str
    action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "action": self.action,
        }


class MetricsCollector(ABC):
    """指标收集器抽象基类"""

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """收集指标"""
        pass


class FeedbackLearnerMetricsCollector(MetricsCollector):
    """从TaskFeedbackLearner收集指标"""

    def __init__(self, learner: TaskFeedbackLearner) -> None:
        self._learner = learner

    def collect(self) -> Dict[str, Any]:
        all_stats = self._learner.get_all_statistics()
        return {
            "task_stats": {name: self._stats_to_dict(s) for name, s in all_stats.items()},
            "history_count": len(self._learner.get_history()),
        }

    def _stats_to_dict(self, stats: TaskStatistics) -> Dict[str, Any]:
        return {
            "total_executions": stats.total_executions,
            "success_count": stats.success_count,
            "failure_count": stats.failure_count,
            "success_rate": stats.success_rate,
            "consecutive_failures": stats.consecutive_failures,
            "status": stats.status.value,
            "priority_multiplier": stats.priority_multiplier,
            "suspension_count": stats.suspension_count,
        }


class TrendAnalyzer:
    """趋势分析器

    第一性原理：趋势 = 近期表现 vs 整体表现
    """

    RECENT_WINDOW: int = 10

    def analyze(
        self,
        records: List[TaskExecutionRecord],
        metrics: ReportMetrics,
    ) -> TrendAnalysis:
        """分析趋势"""
        if not records:
            return TrendAnalysis()
        recent = records[-self.RECENT_WINDOW:]
        recent_success_rate = self._compute_success_rate(recent)
        overall_success_rate = metrics.success_rate
        improvement = recent_success_rate - overall_success_rate
        trend = self._determine_trend(improvement)
        return TrendAnalysis(
            success_trend=trend,
            recent_success_rate=recent_success_rate,
            overall_success_rate=overall_success_rate,
            improvement=improvement,
        )

    def _compute_success_rate(self, records: List[TaskExecutionRecord]) -> float:
        """计算成功率"""
        if not records:
            return 0.0
        success = sum(1 for r in records if r.success)
        return success / len(records)

    def _determine_trend(self, improvement: float) -> str:
        """确定趋势"""
        if improvement > 0.05:
            return "rising"
        if improvement < -0.05:
            return "falling"
        return "stable"


class SuggestionGenerator:
    """改进建议生成器

    第一性原理：建议 = 问题识别 × 行动方案
    """

    def generate(
        self,
        metrics: ReportMetrics,
        trend: TrendAnalysis,
        task_stats: Dict[str, Dict[str, Any]],
    ) -> List[ImprovementSuggestion]:
        """生成改进建议"""
        suggestions: List[ImprovementSuggestion] = []
        self._add_diversity_suggestion(metrics, suggestions)
        self._add_reliability_suggestion(metrics, trend, suggestions)
        self._add_suspended_suggestion(metrics, task_stats, suggestions)
        self._add_performance_suggestion(metrics, suggestions)
        self._add_trend_suggestion(trend, suggestions)
        return suggestions

    def _add_diversity_suggestion(
        self, metrics: ReportMetrics, suggestions: List[ImprovementSuggestion]
    ) -> None:
        """多样性建议"""
        if metrics.unique_task_types < 3:
            suggestions.append(ImprovementSuggestion(
                category="diversity",
                priority="high",
                title="任务类型不足",
                description=f"仅发现{metrics.unique_task_types}种任务类型，建议至少3种",
                action="增加任务工厂种类，启用更多真实任务源",
            ))

    def _add_reliability_suggestion(
        self,
        metrics: ReportMetrics,
        trend: TrendAnalysis,
        suggestions: List[ImprovementSuggestion],
    ) -> None:
        """可靠性建议"""
        if metrics.success_rate < 0.5:
            suggestions.append(ImprovementSuggestion(
                category="reliability",
                priority="high",
                title="成功率过低",
                description=f"整体成功率仅{metrics.success_rate:.1%}，低于50%",
                action="检查失败任务的根因，调整任务参数或降级低成功率任务",
            ))

    def _add_suspended_suggestion(
        self,
        metrics: ReportMetrics,
        task_stats: Dict[str, Dict[str, Any]],
        suggestions: List[ImprovementSuggestion],
    ) -> None:
        """暂停任务建议"""
        if metrics.suspended_tasks > 0:
            suspended_names = [
                name for name, stats in task_stats.items()
                if stats.get("status") == TaskStatus.SUSPENDED.value
            ]
            suggestions.append(ImprovementSuggestion(
                category="reliability",
                priority="medium",
                title="存在被暂停的任务",
                description=f"{metrics.suspended_tasks}个任务被暂停: {', '.join(suspended_names[:3])}",
                action="检查暂停原因，修复后手动恢复或等待冷却",
            ))

    def _add_performance_suggestion(
        self, metrics: ReportMetrics, suggestions: List[ImprovementSuggestion]
    ) -> None:
        """性能建议"""
        if metrics.avg_execution_time > 5.0:
            suggestions.append(ImprovementSuggestion(
                category="performance",
                priority="medium",
                title="平均执行时间过长",
                description=f"平均执行时间{metrics.avg_execution_time:.2f}秒，超过5秒",
                action="优化慢任务，增加超时限制或拆分大任务",
            ))

    def _add_trend_suggestion(
        self, trend: TrendAnalysis, suggestions: List[ImprovementSuggestion]
    ) -> None:
        """趋势建议"""
        if trend.success_trend == "falling":
            suggestions.append(ImprovementSuggestion(
                category="reliability",
                priority="high",
                title="成功率下降趋势",
                description=f"近期成功率{trend.recent_success_rate:.1%}低于整体{trend.overall_success_rate:.1%}",
                action="检查近期环境变化，回滚可能引起退化的改动",
            ))
        elif trend.success_trend == "rising":
            suggestions.append(ImprovementSuggestion(
                category="performance",
                priority="low",
                title="成功率上升趋势",
                description=f"近期成功率{trend.recent_success_rate:.1%}高于整体{trend.overall_success_rate:.1%}",
                action="保持当前策略，可考虑增加任务频率",
            ))


class ReportFormatter(ABC):
    """报告格式化器抽象基类"""

    @abstractmethod
    def format(
        self,
        metrics: ReportMetrics,
        trend: TrendAnalysis,
        suggestions: List[ImprovementSuggestion],
        task_stats: Dict[str, Dict[str, Any]],
        start_time: float,
        end_time: float,
    ) -> str:
        """格式化报告"""
        pass


class TextReportFormatter(ReportFormatter):
    """文本格式报告"""

    def format(
        self,
        metrics: ReportMetrics,
        trend: TrendAnalysis,
        suggestions: List[ImprovementSuggestion],
        task_stats: Dict[str, Dict[str, Any]],
        start_time: float,
        end_time: float,
    ) -> str:
        """格式化为文本报告"""
        lines: List[str] = []
        self._add_header(lines, start_time, end_time)
        self._add_summary(lines, metrics)
        self._add_trend(lines, trend)
        self._add_task_details(lines, task_stats)
        self._add_suggestions(lines, suggestions)
        self._add_footer(lines)
        return "\n".join(lines)

    def _add_header(self, lines: List[str], start: float, end: float) -> None:
        """添加报告头"""
        duration = end - start
        lines.append("=" * 60)
        lines.append("自驱永续进化Agent - 运行报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end))}")
        lines.append(f"运行时长: {duration:.1f}秒")
        lines.append("")

    def _add_summary(self, lines: List[str], metrics: ReportMetrics) -> None:
        """添加摘要"""
        lines.append("-" * 60)
        lines.append("【运行摘要】")
        lines.append("-" * 60)
        lines.append(f"任务种类数: {metrics.unique_task_types}")
        lines.append(f"总执行次数: {metrics.total_executions}")
        lines.append(f"成功次数: {metrics.successful_tasks}")
        lines.append(f"失败次数: {metrics.failed_tasks}")
        lines.append(f"成功率: {metrics.success_rate:.1%}")
        lines.append(f"平均执行时间: {metrics.avg_execution_time:.3f}秒")
        lines.append(f"暂停任务数: {metrics.suspended_tasks}")
        lines.append(f"降级任务数: {metrics.degraded_tasks}")
        lines.append(f"提升任务数: {metrics.promoted_tasks}")
        lines.append("")

    def _add_trend(self, lines: List[str], trend: TrendAnalysis) -> None:
        """添加趋势"""
        lines.append("-" * 60)
        lines.append("【趋势分析】")
        lines.append("-" * 60)
        lines.append(f"成功率趋势: {trend.success_trend}")
        lines.append(f"近期成功率: {trend.recent_success_rate:.1%}")
        lines.append(f"整体成功率: {trend.overall_success_rate:.1%}")
        lines.append(f"改进幅度: {trend.improvement:+.1%}")
        lines.append("")

    def _add_task_details(
        self, lines: List[str], task_stats: Dict[str, Dict[str, Any]]
    ) -> None:
        """添加任务详情"""
        lines.append("-" * 60)
        lines.append("【任务详情】")
        lines.append("-" * 60)
        if not task_stats:
            lines.append("(无任务记录)")
            lines.append("")
            return
        sorted_stats = sorted(
            task_stats.items(),
            key=lambda x: x[1].get("total_executions", 0),
            reverse=True,
        )
        for name, stats in sorted_stats:
            lines.append(f"  {name}:")
            lines.append(f"    执行次数: {stats.get('total_executions', 0)}")
            lines.append(f"    成功: {stats.get('success_count', 0)}, "
                         f"失败: {stats.get('failure_count', 0)}")
            lines.append(f"    成功率: {stats.get('success_rate', 0):.1%}")
            lines.append(f"    状态: {stats.get('status', 'unknown')}")
            lines.append(f"    优先级倍数: {stats.get('priority_multiplier', 1.0):.2f}")
        lines.append("")

    def _add_suggestions(
        self, lines: List[str], suggestions: List[ImprovementSuggestion]
    ) -> None:
        """添加建议"""
        lines.append("-" * 60)
        lines.append("【改进建议】")
        lines.append("-" * 60)
        if not suggestions:
            lines.append("(系统运行良好，暂无紧急建议)")
            lines.append("")
            return
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_suggestions = sorted(
            suggestions, key=lambda s: priority_order.get(s.priority, 99)
        )
        for i, sug in enumerate(sorted_suggestions, 1):
            lines.append(f"{i}. [{sug.priority.upper()}] {sug.title}")
            lines.append(f"   类别: {sug.category}")
            lines.append(f"   描述: {sug.description}")
            lines.append(f"   行动: {sug.action}")
            lines.append("")

    def _add_footer(self, lines: List[str]) -> None:
        """添加报告尾"""
        lines.append("=" * 60)
        lines.append("报告结束")
        lines.append("=" * 60)


class RunReporter:
    """
    运行报告生成器

    第一性原理：报告 = 数据收集 × 趋势分析 × 建议生成 × 格式化输出

    类比：生物的"记忆整理"——将散乱的感知整合为可回忆的叙事
    """

    def __init__(
        self,
        formatter: Optional[ReportFormatter] = None,
        trend_analyzer: Optional[TrendAnalyzer] = None,
        suggestion_generator: Optional[SuggestionGenerator] = None,
    ) -> None:
        self._formatter = formatter or TextReportFormatter()
        self._trend_analyzer = trend_analyzer or TrendAnalyzer()
        self._suggestion_generator = suggestion_generator or SuggestionGenerator()
        self._records: List[TaskExecutionRecord] = []
        self._start_time: float = time.time()
        self._end_time: float = 0.0
        self._task_stats_snapshot: Dict[str, Dict[str, Any]] = {}

    def record_execution(
        self,
        task_name: str,
        result: TaskResult,
        execution_time: float = 0.0,
    ) -> None:
        """记录任务执行"""
        self._records.append(TaskExecutionRecord(
            task_name=task_name,
            success=result.success,
            timestamp=time.time(),
            execution_time=execution_time,
            message=result.message,
            data=result.data,
        ))

    def collect_from_learner(self, learner: TaskFeedbackLearner) -> None:
        """从TaskFeedbackLearner收集统计"""
        collector = FeedbackLearnerMetricsCollector(learner)
        data = collector.collect()
        self._task_stats_snapshot = data.get("task_stats", {})

    def _compute_metrics(self) -> ReportMetrics:
        """计算指标"""
        metrics = ReportMetrics()
        metrics.total_executions = len(self._records)
        metrics.successful_tasks = sum(1 for r in self._records if r.success)
        metrics.failed_tasks = metrics.total_executions - metrics.successful_tasks
        metrics.success_rate = (
            metrics.successful_tasks / max(metrics.total_executions, 1)
        )
        times = [r.execution_time for r in self._records if r.execution_time > 0]
        metrics.avg_execution_time = sum(times) / max(len(times), 1)
        metrics.unique_task_types = len({r.task_name for r in self._records})
        self._enrich_from_snapshot(metrics)
        return metrics

    def _enrich_from_snapshot(self, metrics: ReportMetrics) -> None:
        """从快照补充指标"""
        if not self._task_stats_snapshot:
            return
        metrics.total_tasks = len(self._task_stats_snapshot)
        for stats in self._task_stats_snapshot.values():
            status = stats.get("status", "")
            if status == TaskStatus.SUSPENDED.value:
                metrics.suspended_tasks += 1
            elif stats.get("priority_multiplier", 1.0) < 1.0:
                metrics.degraded_tasks += 1
            elif stats.get("priority_multiplier", 1.0) > 1.0:
                metrics.promoted_tasks += 1

    def generate_report(self) -> str:
        """生成报告"""
        self._end_time = time.time()
        metrics = self._compute_metrics()
        trend = self._trend_analyzer.analyze(self._records, metrics)
        suggestions = self._suggestion_generator.generate(
            metrics, trend, self._task_stats_snapshot
        )
        return self._formatter.format(
            metrics, trend, suggestions,
            self._task_stats_snapshot, self._start_time, self._end_time,
        )

    def save_report(self, path: str) -> str:
        """保存报告到文件"""
        report = self.generate_report()
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        return path

    def get_metrics(self) -> ReportMetrics:
        """获取当前指标"""
        return self._compute_metrics()

    def get_records(self) -> List[TaskExecutionRecord]:
        """获取执行记录"""
        return list(self._records)

    def reset(self) -> None:
        """重置报告器"""
        self._records.clear()
        self._task_stats_snapshot.clear()
        self._start_time = time.time()
        self._end_time = 0.0

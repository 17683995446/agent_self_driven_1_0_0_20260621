"""
U10 实用性验收

第一性原理：实用性 = 真实任务多样性 × 真实交互 × 真实产出价值

验收维度：
1. 任务多样性：≥3种不同任务类型
2. 真实交互：HTTP/文件/日志中至少2种真实交互
3. 产出价值：生成可读运行报告
4. 状态适应：任务类型随环境状态变化
5. 反馈学习：任务结果影响未来决策

综合实用度评分：≥7/10 通过验收
"""

import os
import time
import tempfile
import pytest
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.left.action.decision.dynamic_task_generator import DynamicTaskGenerator
from src.left.action.decision.file_processing_factory import (
    FileProcessingTaskFactory,
    StandardFileAnalyzer,
)
from src.left.action.decision.health_check_factory import (
    HealthCheckExecutor,
    HealthCheckRecord,
    HealthCheckTarget,
    HealthCheckTaskFactory,
)
from src.left.action.decision.log_analysis_factory import LogAnalysisTaskFactory
from src.left.action.decision.real_task_factory import RealTaskFactory
from src.left.action.decision.run_reporter import RunReporter
from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
from src.platform.support.models.base.state import (
    EnvironmentState,
    GapState,
    LogState,
    SelfState,
    SystemState,
)
from src.platform.support.models.base.task import Task, TaskPriority, TaskResult


# ===== 验收指标数据类 =====


@dataclass
class AcceptanceCriterion:
    """验收标准"""

    name: str
    description: str
    passed: bool
    score: float  # [0.0, 1.0]
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "score": round(self.score, 4),
            "evidence": self.evidence,
        }


@dataclass
class AcceptanceReport:
    """验收报告"""

    timestamp: float
    duration_seconds: float
    criteria: List[AcceptanceCriterion] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
            "criteria": [c.to_dict() for c in self.criteria],
            "overall_score": round(self.overall_score, 2),
            "passed": self.passed,
        }


# ===== 验收器 =====


class UtilityAcceptanceRunner:
    """
    实用性验收运行器

    第一性原理：验收 = 运行系统 × 收集证据 × 评分
    - 运行系统：执行多轮任务生成和执行
    - 收集证据：记录任务类型、交互类型、产出
    - 评分：按5个维度评分，综合≥7/10通过

    类比：生物的"能力测试"——通过实际行为验证生存能力
    """

    PASS_THRESHOLD: float = 7.0
    MIN_TASK_DIVERSITY: int = 3
    MIN_INTERACTION_TYPES: int = 2

    def __init__(
        self,
        task_factory: Optional[RealTaskFactory] = None,
        dynamic_generator: Optional[DynamicTaskGenerator] = None,
        feedback_learner: Optional[TaskFeedbackLearner] = None,
        reporter: Optional[RunReporter] = None,
    ) -> None:
        self._factory = task_factory or RealTaskFactory()
        self._generator = dynamic_generator or DynamicTaskGenerator()
        self._learner = feedback_learner or TaskFeedbackLearner()
        self._reporter = reporter or RunReporter()
        self._executed_task_types: set = set()
        self._interaction_types: set = set()
        self._reports_generated: List[str] = []

    def run_acceptance(
        self,
        rounds: int = 5,
        work_dir: Optional[str] = None,
    ) -> AcceptanceReport:
        """运行实用性验收"""
        start_time = time.time()
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="acceptance_")
        self._run_all_rounds(rounds, work_dir)
        report = self._build_report(start_time)
        return report

    def _run_all_rounds(self, rounds: int, work_dir: str) -> None:
        """运行所有轮次"""
        states = self._build_test_states()
        for round_idx in range(rounds):
            state = states[round_idx % len(states)]
            self._run_one_round(state, work_dir)

    def _build_test_states(self) -> List[EnvironmentState]:
        """构建测试状态序列"""
        return [
            # 空闲状态
            EnvironmentState(
                system=SystemState(cpu_overall=0.05, memory_usage=0.05, disk_usage=0.05),
                logs=LogState(error_rate=0.01, warning_rate=0.01),
                self=SelfState(prediction_error=0.01),
            ),
            # CPU高
            EnvironmentState(
                system=SystemState(cpu_overall=0.9, memory_usage=0.3, disk_usage=0.3),
                logs=LogState(error_rate=0.01, warning_rate=0.01),
                self=SelfState(prediction_error=0.01),
            ),
            # 错误率高
            EnvironmentState(
                system=SystemState(cpu_overall=0.3, memory_usage=0.3, disk_usage=0.3),
                logs=LogState(error_rate=0.2, warning_rate=0.1),
                self=SelfState(prediction_error=0.01),
            ),
            # 磁盘满
            EnvironmentState(
                system=SystemState(cpu_overall=0.3, memory_usage=0.3, disk_usage=0.95),
                logs=LogState(error_rate=0.01, warning_rate=0.01),
                self=SelfState(prediction_error=0.01),
            ),
        ]

    def _run_one_round(self, state: EnvironmentState, work_dir: str) -> None:
        """运行一轮"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        # 从RealTaskFactory获取任务
        tasks = self._factory.create_tasks(gaps, state)
        for task in tasks:
            self._execute_and_record(task)
        # 从DynamicTaskGenerator获取任务
        dynamic_tasks = self._generator.generate_tasks(gaps, state)
        for task in dynamic_tasks:
            self._execute_and_record(task)

    def _execute_and_record(self, task: Task) -> None:
        """执行任务并记录"""
        if task.execute_fn is None:
            return
        try:
            result = task.execute_fn()
        except Exception as e:
            result = TaskResult(success=False, message=f"Exception: {e}")
        self._executed_task_types.add(task.name)
        self._classify_interaction(task, result)
        self._learner.record_result(task.name, result)
        self._reporter.record_execution(task.name, result, 0.1)

    def _classify_interaction(self, task: Task, result: TaskResult) -> None:
        """分类交互类型"""
        name = task.name.lower()
        data = result.data if isinstance(result.data, dict) else {}
        if "http" in name or "health_check" in name or "url" in str(data):
            self._interaction_types.add("http")
        if "log" in name or "error_rate" in data or "level_counts" in data:
            self._interaction_types.add("log")
        if "file" in name or "type_distribution" in data or "files" in data:
            self._interaction_types.add("file")
        if "disk" in name or "disk_percent" in data:
            self._interaction_types.add("disk")
        if "process" in name or "processes" in data:
            self._interaction_types.add("process")
        if "cpu" in name or "memory" in name:
            self._interaction_types.add("system")

    def _build_report(self, start_time: float) -> AcceptanceReport:
        """构建验收报告"""
        duration = time.time() - start_time
        # 生成运行报告
        self._reporter.collect_from_learner(self._learner)
        run_report = self._reporter.generate_report()
        self._reports_generated.append(run_report)
        # 评估各维度
        criteria = [
            self._eval_task_diversity(),
            self._eval_real_interaction(),
            self._eval_output_value(),
            self._eval_state_adaptation(),
            self._eval_feedback_learning(),
        ]
        overall = sum(c.score for c in criteria) / len(criteria) * 10
        passed = overall >= self.PASS_THRESHOLD
        return AcceptanceReport(
            timestamp=time.time(),
            duration_seconds=duration,
            criteria=criteria,
            overall_score=overall,
            passed=passed,
        )

    def _eval_task_diversity(self) -> AcceptanceCriterion:
        """评估任务多样性"""
        count = len(self._executed_task_types)
        score = min(count / 5.0, 1.0)  # 5种为满分
        passed = count >= self.MIN_TASK_DIVERSITY
        return AcceptanceCriterion(
            name="task_diversity",
            description=f"任务种类≥{self.MIN_TASK_DIVERSITY}",
            passed=passed,
            score=score,
            evidence=f"执行了{count}种任务: {sorted(self._executed_task_types)}",
        )

    def _eval_real_interaction(self) -> AcceptanceCriterion:
        """评估真实交互"""
        count = len(self._interaction_types)
        score = min(count / 4.0, 1.0)  # 4种为满分
        passed = count >= self.MIN_INTERACTION_TYPES
        return AcceptanceCriterion(
            name="real_interaction",
            description=f"真实交互类型≥{self.MIN_INTERACTION_TYPES}",
            passed=passed,
            score=score,
            evidence=f"涉及{count}种交互: {sorted(self._interaction_types)}",
        )

    def _eval_output_value(self) -> AcceptanceCriterion:
        """评估产出价值"""
        report_count = len(self._reports_generated)
        has_report = report_count >= 1
        report_content = self._reports_generated[0] if self._reports_generated else ""
        has_metrics = "运行摘要" in report_content
        has_suggestions = "改进建议" in report_content
        score = 0.0
        if has_report:
            score += 0.4
        if has_metrics:
            score += 0.3
        if has_suggestions:
            score += 0.3
        return AcceptanceCriterion(
            name="output_value",
            description="生成可读运行报告",
            passed=has_report and has_metrics,
            score=score,
            evidence=f"生成{report_count}份报告，包含指标:{has_metrics}，建议:{has_suggestions}",
        )

    def _eval_state_adaptation(self) -> AcceptanceCriterion:
        """评估状态适应"""
        history = self._generator.get_decision_history()
        if len(history) < 2:
            return AcceptanceCriterion(
                name="state_adaptation",
                description="任务类型随状态变化",
                passed=False,
                score=0.0,
                evidence="决策历史不足",
            )
        # 检查不同状态是否产生不同任务
        task_sets: List[frozenset] = []
        for decision in history:
            triggers = [t.dimension for t in decision.triggers if t.triggered]
            task_sets.append(frozenset(triggers))
        unique_sets = len(set(task_sets))
        score = min(unique_sets / 3.0, 1.0)
        passed = unique_sets >= 2
        return AcceptanceCriterion(
            name="state_adaptation",
            description="任务类型随状态变化",
            passed=passed,
            score=score,
            evidence=f"决策历史{len(history)}条，{unique_sets}种不同触发模式",
        )

    def _eval_feedback_learning(self) -> AcceptanceCriterion:
        """评估反馈学习"""
        all_stats = self._learner.get_all_statistics()
        if not all_stats:
            return AcceptanceCriterion(
                name="feedback_learning",
                description="任务结果影响未来决策",
                passed=False,
                score=0.0,
                evidence="无反馈数据",
            )
        total_executions = sum(s.total_executions for s in all_stats.values())
        has_adjustments = any(
            s.priority_multiplier != 1.0 or s.status.value != "active"
            for s in all_stats.values()
        )
        score = min(total_executions / 20.0, 1.0)  # 20次执行为满分
        if has_adjustments:
            score = min(score + 0.2, 1.0)
        passed = total_executions >= 5
        return AcceptanceCriterion(
            name="feedback_learning",
            description="任务结果影响未来决策",
            passed=passed,
            score=score,
            evidence=f"记录{total_executions}次执行，{len(all_stats)}种任务，"
                     f"有调整:{has_adjustments}",
        )

    def get_run_report(self) -> str:
        """获取运行报告"""
        if not self._reports_generated:
            return ""
        return self._reports_generated[-1]

    def get_executed_task_types(self) -> List[str]:
        """获取执行的任务类型"""
        return sorted(self._executed_task_types)

    def get_interaction_types(self) -> List[str]:
        """获取交互类型"""
        return sorted(self._interaction_types)


# ===== 验收测试 =====


class TestUtilityAcceptance:
    """实用性验收测试"""

    def test_full_acceptance_run(self) -> None:
        """完整验收运行"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        assert report.duration_seconds >= 0
        assert len(report.criteria) == 5
        assert 0 <= report.overall_score <= 10

    def test_task_diversity_meets_minimum(self) -> None:
        """任务多样性达到最低要求"""
        runner = UtilityAcceptanceRunner()
        runner.run_acceptance(rounds=5)
        task_types = runner.get_executed_task_types()
        assert len(task_types) >= 3, f"仅{len(task_types)}种任务: {task_types}"

    def test_real_interaction_present(self) -> None:
        """存在真实交互"""
        runner = UtilityAcceptanceRunner()
        runner.run_acceptance(rounds=5)
        interactions = runner.get_interaction_types()
        assert len(interactions) >= 2, f"仅{len(interactions)}种交互: {interactions}"

    def test_run_report_generated(self) -> None:
        """生成运行报告"""
        runner = UtilityAcceptanceRunner()
        runner.run_acceptance(rounds=3)
        report = runner.get_run_report()
        assert len(report) > 100
        assert "运行报告" in report
        assert "运行摘要" in report

    def test_overall_score_passes_threshold(self) -> None:
        """综合实用度≥7/10"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        assert report.overall_score >= 7.0, (
            f"实用度{report.overall_score:.2f}低于阈值7.0; "
            f"criteria: {[c.to_dict() for c in report.criteria]}"
        )

    def test_state_adaptation_works(self) -> None:
        """状态适应有效"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        adaptation = next(
            c for c in report.criteria if c.name == "state_adaptation"
        )
        assert adaptation.passed, f"状态适应未通过: {adaptation.evidence}"

    def test_feedback_learning_works(self) -> None:
        """反馈学习有效"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        feedback = next(
            c for c in report.criteria if c.name == "feedback_learning"
        )
        assert feedback.passed, f"反馈学习未通过: {feedback.evidence}"

    def test_acceptance_report_structure(self) -> None:
        """验收报告结构完整"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=2)
        d = report.to_dict()
        assert "timestamp" in d
        assert "duration_seconds" in d
        assert "criteria" in d
        assert "overall_score" in d
        assert "passed" in d
        assert len(d["criteria"]) == 5

    def test_each_criterion_has_evidence(self) -> None:
        """每个标准都有证据"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=3)
        for criterion in report.criteria:
            assert len(criterion.evidence) > 0, f"{criterion.name}无证据"

    def test_diversity_criterion(self) -> None:
        """多样性标准"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        diversity = next(c for c in report.criteria if c.name == "task_diversity")
        assert diversity.description == f"任务种类≥{runner.MIN_TASK_DIVERSITY}"
        assert diversity.score > 0

    def test_interaction_criterion(self) -> None:
        """交互标准"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        interaction = next(c for c in report.criteria if c.name == "real_interaction")
        assert interaction.description == f"真实交互类型≥{runner.MIN_INTERACTION_TYPES}"

    def test_output_value_criterion(self) -> None:
        """产出价值标准"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=3)
        output = next(c for c in report.criteria if c.name == "output_value")
        assert output.passed
        assert output.score >= 0.7

    def test_acceptance_with_custom_components(self) -> None:
        """使用自定义组件验收"""
        runner = UtilityAcceptanceRunner(
            task_factory=RealTaskFactory(),
            dynamic_generator=DynamicTaskGenerator(),
            feedback_learner=TaskFeedbackLearner(),
            reporter=RunReporter(),
        )
        report = runner.run_acceptance(rounds=3)
        assert report.overall_score > 0

    def test_long_run_stability(self) -> None:
        """长时间运行稳定性"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=10)
        # 长时间运行不应崩溃
        assert report.duration_seconds >= 0
        assert report.overall_score >= 7.0

    def test_executed_tasks_are_real(self) -> None:
        """执行的任务是真实任务（非占位）"""
        runner = UtilityAcceptanceRunner()
        runner.run_acceptance(rounds=5)
        task_types = runner.get_executed_task_types()
        # 应包含真实任务类型
        real_task_names = {
            "system_health_check", "log_scan", "file_inventory",
            "disk_usage_report", "process_audit",
        }
        overlap = set(task_types) & real_task_names
        assert len(overlap) >= 3, (
            f"真实任务不足: {overlap}; 全部任务: {task_types}"
        )


# ===== 验收报告生成测试 =====


class TestAcceptanceReportGeneration:
    """验收报告生成测试"""

    def test_save_acceptance_report(self) -> None:
        """保存验收报告"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "acceptance.txt")
            content = runner.get_run_report()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            assert os.path.isfile(path)
            with open(path, "r", encoding="utf-8") as f:
                saved = f.read()
            assert "运行报告" in saved

    def test_acceptance_criteria_serializable(self) -> None:
        """验收标准可序列化"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=2)
        for criterion in report.criteria:
            d = criterion.to_dict()
            assert isinstance(d["name"], str)
            assert isinstance(d["passed"], bool)
            assert isinstance(d["score"], float)
            assert 0 <= d["score"] <= 1

    def test_overall_score_calculation(self) -> None:
        """综合评分计算"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        expected = sum(c.score for c in report.criteria) / 5 * 10
        assert abs(report.overall_score - expected) < 0.1


# ===== 集成场景验收 =====


class TestIntegrationScenarios:
    """集成场景验收"""

    def test_scenario_full_pipeline(self) -> None:
        """场景：完整管道"""
        runner = UtilityAcceptanceRunner()
        report = runner.run_acceptance(rounds=5)
        # 验收应通过
        assert report.passed, (
            f"验收未通过: score={report.overall_score:.2f}, "
            f"criteria={[c.to_dict() for c in report.criteria]}"
        )

    def test_scenario_log_analysis_integration(self) -> None:
        """场景：日志分析集成"""
        with tempfile.TemporaryDirectory() as log_dir:
            # 准备日志
            log_path = os.path.join(log_dir, "test.log")
            with open(log_path, "w") as f:
                for i in range(20):
                    f.write(f"2024-01-01 10:00:{i:02d} - app - ERROR - error {i}\n")
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(
                GapState(safety=0.5),
                EnvironmentState(),
            )
            result = tasks[0].execute_fn()
            assert result.data["total_lines"] == 20
            assert result.data["error_rate"] > 0.5

    def test_scenario_file_processing_integration(self) -> None:
        """场景：文件处理集成"""
        with tempfile.TemporaryDirectory() as work_dir:
            # 准备文件
            for i in range(5):
                with open(os.path.join(work_dir, f"file_{i}.py"), "w") as f:
                    f.write(f"# file {i}\n")
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(
                GapState(gain=0.5),
                EnvironmentState(),
            )
            result = tasks[0].execute_fn()
            assert result.data["total_files"] == 5
            assert ".py" in result.data["type_distribution"]

    def test_scenario_dynamic_generation_integration(self) -> None:
        """场景：动态生成集成"""
        gen = DynamicTaskGenerator()
        # 空闲
        idle_tasks = gen.generate_tasks(
            GapState(),
            EnvironmentState(
                system=SystemState(cpu_overall=0.05, memory_usage=0.05, disk_usage=0.05),
                logs=LogState(error_rate=0.01, warning_rate=0.01),
                self=SelfState(prediction_error=0.01),
            ),
        )
        # CPU高
        cpu_tasks = gen.generate_tasks(
            GapState(),
            EnvironmentState(
                system=SystemState(cpu_overall=0.95, memory_usage=0.3, disk_usage=0.3),
            ),
        )
        assert any(t.is_exploration for t in idle_tasks)
        assert any("optimize" in t.name for t in cpu_tasks)
        assert not any(t.is_exploration for t in cpu_tasks)

"""
O3 秩序化测试：反馈学习接入

第一性原理：执行结果必须驱动未来决策
验证 TaskFeedbackLearner 接入 DecisionEngine
"""

import pytest
from typing import List

from src.left.action.decision.decision import DecisionEngine
from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
from src.platform.support.models.base.state import (
    EnvironmentState,
    GapState,
    DriveWeights,
)
from src.platform.support.models.base.task import (
    Task,
    TaskPool,
    TaskPriority,
    TaskResult,
    TaskStatus,
)


def _make_task(name: str = "test_task", success: bool = True) -> Task:
    def execute() -> TaskResult:
        return TaskResult(success=success, message=f"executed {name}")
    return Task(name=name, target_drive="safe", execute_fn=execute)


class TestFeedbackLearnerIntegration:
    """测试反馈学习器接入"""

    def test_no_learner_backward_compatible(self) -> None:
        """未注入学习器时向后兼容"""
        engine = DecisionEngine()
        task = _make_task()
        result = engine.execute_task(task)
        assert result.success is True

    def test_execute_records_to_learner(self) -> None:
        """执行后记录到学习器"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        task = _make_task("recorded_task")
        engine.execute_task(task)
        stats = learner.get_statistics("recorded_task")
        assert stats is not None
        assert stats.total_executions == 1

    def test_failed_task_recorded(self) -> None:
        """失败任务被记录"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        task = _make_task("fail_task", success=False)
        engine.execute_task(task)
        stats = learner.get_statistics("fail_task")
        assert stats is not None
        assert stats.failure_count == 1

    def test_suspended_task_filtered(self) -> None:
        """暂停任务被过滤"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        # 连续失败3次→暂停
        for _ in range(3):
            learner.record_result(
                "suspended_task",
                TaskResult(success=False, message="fail"),
            )
        assert not learner.is_task_available("suspended_task")
        # 创建任务池，包含暂停任务
        pool = TaskPool()
        suspended_task = Task(name="suspended_task", target_drive="safe")
        other_task = Task(name="other_task", target_drive="safe")
        pool.add_task(suspended_task)
        pool.add_task(other_task)
        # 选择任务时应过滤掉暂停任务
        selected = engine.select_next_task(
            pool, GapState(safety=0.5), DriveWeights()
        )
        assert selected is not None
        assert selected.name != "suspended_task"

    def test_priority_adjusted(self) -> None:
        """优先级被调整"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        # 成功多次→提升
        for _ in range(5):
            learner.record_result(
                "promoted_task",
                TaskResult(success=True, message="ok"),
            )
        task = Task(name="promoted_task", priority=TaskPriority.NORMAL)
        engine._adjust_priorities([task])
        stats = learner.get_statistics("promoted_task")
        assert stats is not None
        assert stats.priority_multiplier > 1.0

    def test_multiple_tasks_recorded(self) -> None:
        """多任务被记录"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        for i in range(5):
            task = _make_task(f"task_{i}")
            engine.execute_task(task)
        all_stats = learner.get_all_statistics()
        assert len(all_stats) == 5

    def test_learner_exception_handled(self) -> None:
        """学习器异常被处理"""
        class FaultyLearner:
            def record_result(self, name, result):
                raise RuntimeError("faulty")
            def is_task_available(self, name):
                return True
            def adjust_task_priority(self, task):
                pass
        engine = DecisionEngine(feedback_learner=FaultyLearner())
        task = _make_task()
        # 不应抛出异常
        result = engine.execute_task(task)
        assert result.success is True


class TestFeedbackLoopEndToEnd:
    """反馈闭环端到端测试"""

    def test_failure_leads_to_suspension(self) -> None:
        """连续失败导致暂停"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        # 执行失败任务3次
        for _ in range(3):
            task = _make_task("bad_task", success=False)
            engine.execute_task(task)
        # 任务应被暂停
        assert not learner.is_task_available("bad_task")

    def test_success_keeps_task_available(self) -> None:
        """成功保持任务可用"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        for _ in range(5):
            task = _make_task("good_task", success=True)
            engine.execute_task(task)
        assert learner.is_task_available("good_task")

    def test_mixed_results_tracked(self) -> None:
        """混合结果被跟踪"""
        learner = TaskFeedbackLearner()
        engine = DecisionEngine(feedback_learner=learner)
        # 3成功2失败
        for success in [True, True, True, False, False]:
            task = _make_task("mixed_task", success=success)
            engine.execute_task(task)
        stats = learner.get_statistics("mixed_task")
        assert stats is not None
        assert stats.success_count == 3
        assert stats.failure_count == 2
        assert abs(stats.success_rate - 0.6) < 0.01

"""
任务结果反馈学习器测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
from unittest.mock import MagicMock

from src.left.action.decision.task_feedback_learner import (
    TaskStatus,
    TaskHistoryEntry,
    TaskStatistics,
    FeedbackPolicy,
    DefaultFeedbackPolicy,
    TaskFeedbackLearner,
)
from src.platform.support.models.base.task import Task, TaskResult, TaskPriority


class TestTaskHistoryEntry:
    """测试任务历史条目"""

    def test_normal_creation(self):
        entry = TaskHistoryEntry(
            task_name="test", success=True, reward=1.0, timestamp=100.0,
        )
        assert entry.success is True
        assert entry.execution_time == 0.0

    def test_to_dict(self):
        entry = TaskHistoryEntry(
            task_name="test", success=False, reward=0.0,
            timestamp=100.0, execution_time=2.5,
        )
        data = entry.to_dict()
        assert data["success"] is False
        assert data["execution_time"] == 2.5


class TestTaskStatistics:
    """测试任务统计"""

    def test_empty(self):
        stats = TaskStatistics()
        assert stats.total_executions == 0
        assert stats.failure_rate == 0.0

    def test_failure_rate(self):
        stats = TaskStatistics(total_executions=10, failure_count=3)
        assert stats.failure_rate == 0.3

    def test_failure_rate_zero_executions(self):
        stats = TaskStatistics()
        assert stats.failure_rate == 0.0

    def test_to_dict(self):
        stats = TaskStatistics(
            total_executions=5, success_count=4, failure_count=1,
            success_rate=0.8, status=TaskStatus.PROMOTED,
        )
        data = stats.to_dict()
        assert data["success_rate"] == 0.8
        assert data["status"] == "promoted"


class TestDefaultFeedbackPolicy:
    """测试默认反馈策略"""

    def setup_method(self):
        self.policy = DefaultFeedbackPolicy()
        self.now = 1000.0

    def test_insufficient_samples(self):
        stats = TaskStatistics(total_executions=2)
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.ACTIVE
        assert mult == 1.0

    def test_high_success_promoted(self):
        stats = TaskStatistics(
            total_executions=10, success_count=9, success_rate=0.9,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.PROMOTED
        assert mult > 1.0

    def test_low_success_degraded(self):
        stats = TaskStatistics(
            total_executions=10, success_count=2, success_rate=0.2,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.DEGRADED
        assert mult < 1.0

    def test_normal_success_active(self):
        stats = TaskStatistics(
            total_executions=10, success_count=5, success_rate=0.5,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.ACTIVE
        assert mult == 1.0

    def test_consecutive_failures_suspend(self):
        stats = TaskStatistics(
            total_executions=5, consecutive_failures=3, success_rate=0.4,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.SUSPENDED
        assert mult == 0.0

    def test_cooldown_active(self):
        stats = TaskStatistics(
            status=TaskStatus.COOLDOWN, last_execution=999.0,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status == TaskStatus.COOLDOWN

    def test_cooldown_expired(self):
        stats = TaskStatistics(
            status=TaskStatus.COOLDOWN, last_execution=900.0,
            total_executions=5, success_rate=0.5,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert status != TaskStatus.COOLDOWN

    def test_degrade_multiplier_capped(self):
        stats = TaskStatistics(
            total_executions=10, success_count=0, success_rate=0.0,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert mult >= DefaultFeedbackPolicy.MIN_MULTIPLIER

    def test_promote_multiplier_capped(self):
        stats = TaskStatistics(
            total_executions=10, success_count=10, success_rate=1.0,
        )
        status, mult = self.policy.evaluate(stats, self.now)
        assert mult <= DefaultFeedbackPolicy.MAX_MULTIPLIER


class TestTaskFeedbackLearner:
    """测试任务反馈学习器"""

    def setup_method(self):
        self.clock_time = 1000.0
        self.learner = TaskFeedbackLearner(clock=lambda: self.clock_time)

    def test_record_success(self):
        result = TaskResult(success=True, message="ok", data={"reward": 1.5})
        stats = self.learner.record_result("task_a", result)
        assert stats.total_executions == 1
        assert stats.success_count == 1
        assert stats.consecutive_successes == 1

    def test_record_failure(self):
        result = TaskResult(success=False, message="fail", data={})
        stats = self.learner.record_result("task_a", result)
        assert stats.failure_count == 1
        assert stats.consecutive_failures == 1

    def test_record_multiple(self):
        for _ in range(3):
            self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        stats = self.learner.get_statistics("task_a")
        assert stats.total_executions == 3
        assert stats.success_rate == 1.0

    def test_consecutive_failures_suspend(self):
        for _ in range(3):
            result = TaskResult(False, "fail", {})
            self.learner.record_result("task_a", result)
        stats = self.learner.get_statistics("task_a")
        assert stats.status == TaskStatus.SUSPENDED
        assert stats.suspension_count == 1

    def test_success_resets_failures(self):
        self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        stats = self.learner.get_statistics("task_a")
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 1

    def test_is_task_available_no_stats(self):
        assert self.learner.is_task_available("unknown") is True

    def test_is_task_available_suspended(self):
        for _ in range(3):
            self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        assert self.learner.is_task_available("task_a") is False

    def test_is_task_available_active(self):
        self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        assert self.learner.is_task_available("task_a") is True

    def test_get_priority_multiplier_unknown(self):
        assert self.learner.get_priority_multiplier("unknown") == 1.0

    def test_get_priority_multiplier_degraded(self):
        for _ in range(5):
            self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        mult = self.learner.get_priority_multiplier("task_a")
        assert mult < 1.0

    def test_adjust_task_priority_suspended(self):
        task = Task(name="task_a", description="d", target_drive="safe")
        for _ in range(3):
            self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        adjusted = self.learner.adjust_task_priority(task)
        assert adjusted.priority == TaskPriority.LOW

    def test_adjust_task_priority_promoted(self):
        task = Task(name="task_a", description="d", target_drive="safe")
        for _ in range(10):
            self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        adjusted = self.learner.adjust_task_priority(task)
        assert adjusted.priority == TaskPriority.HIGH

    def test_adjust_task_priority_normal(self):
        task = Task(
            name="task_a", description="d", target_drive="safe",
            priority=TaskPriority.NORMAL,
        )
        self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        adjusted = self.learner.adjust_task_priority(task)
        assert adjusted.priority == TaskPriority.NORMAL

    def test_get_history_all(self):
        self.learner.record_result("a", TaskResult(True, "ok", {}))
        self.learner.record_result("b", TaskResult(False, "fail", {}))
        history = self.learner.get_history()
        assert len(history) == 2

    def test_get_history_filtered(self):
        self.learner.record_result("a", TaskResult(True, "ok", {}))
        self.learner.record_result("b", TaskResult(False, "fail", {}))
        history = self.learner.get_history("a")
        assert len(history) == 1
        assert history[0].task_name == "a"

    def test_get_summary_empty(self):
        summary = self.learner.get_summary()
        assert summary["total_tasks_tracked"] == 0
        assert summary["overall_success_rate"] == 0.0

    def test_get_summary_with_data(self):
        self.learner.record_result("a", TaskResult(True, "ok", {}))
        self.learner.record_result("b", TaskResult(False, "fail", {}))
        summary = self.learner.get_summary()
        assert summary["total_tasks_tracked"] == 2
        assert summary["overall_success_rate"] == 0.5

    def test_history_limit(self):
        for i in range(250):
            self.learner.record_result("task", TaskResult(True, "ok", {}))
        history = self.learner.get_history()
        assert len(history) <= 200

    def test_reset(self):
        self.learner.record_result("a", TaskResult(True, "ok", {}))
        self.learner.reset()
        assert self.learner.get_statistics("a") is None
        assert len(self.learner.get_history()) == 0

    def test_reward_extraction(self):
        result = TaskResult(True, "ok", data={"reward": 2.5})
        stats = self.learner.record_result("task_a", result)
        assert stats.total_reward == 2.5

    def test_reward_extraction_no_reward_key(self):
        result = TaskResult(True, "ok", data={})
        stats = self.learner.record_result("task_a", result)
        assert stats.total_reward == 1.0

    def test_reward_extraction_failure(self):
        result = TaskResult(False, "fail", data={"reward": 5.0})
        stats = self.learner.record_result("task_a", result)
        assert stats.total_reward == 0.0

    def test_get_statistics_unknown(self):
        assert self.learner.get_statistics("unknown") is None

    def test_get_all_statistics(self):
        self.learner.record_result("a", TaskResult(True, "ok", {}))
        self.learner.record_result("b", TaskResult(True, "ok", {}))
        all_stats = self.learner.get_all_statistics()
        assert len(all_stats) == 2

    def test_custom_policy(self):
        mock_policy = MagicMock(spec=FeedbackPolicy)
        mock_policy.evaluate.return_value = (TaskStatus.PROMOTED, 1.5)
        learner = TaskFeedbackLearner(policy=mock_policy, clock=lambda: 1000.0)
        result = TaskResult(True, "ok", {})
        stats = learner.record_result("task_a", result)
        assert stats.status == TaskStatus.PROMOTED
        assert stats.priority_multiplier == 1.5

    def test_cooldown_recovery(self):
        """测试冷却期恢复"""
        # 暂停任务
        for _ in range(3):
            self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        assert not self.learner.is_task_available("task_a")
        # 等待冷却期过去
        self.clock_time += 100
        # 再次记录成功
        self.learner.record_result("task_a", TaskResult(True, "ok", {}))
        stats = self.learner.get_statistics("task_a")
        assert stats.consecutive_failures == 0

    def test_degraded_task_priority(self):
        """测试降级任务优先级"""
        task = Task(
            name="task_a", description="d", target_drive="safe",
            priority=TaskPriority.HIGH,
        )
        for _ in range(5):
            self.learner.record_result("task_a", TaskResult(False, "fail", {}))
        adjusted = self.learner.adjust_task_priority(task)
        assert adjusted.priority in (TaskPriority.LOW, TaskPriority.NORMAL)

    def test_summary_suspended_list(self):
        for _ in range(3):
            self.learner.record_result("bad_task", TaskResult(False, "fail", {}))
        summary = self.learner.get_summary()
        assert "bad_task" in summary["suspended_tasks"]

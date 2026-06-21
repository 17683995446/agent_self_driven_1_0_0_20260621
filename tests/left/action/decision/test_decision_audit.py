"""
决策审计日志测试

验证审计记录、统计、边界条件
"""

import pytest

from src.left.action.decision.decision_audit import DecisionAuditLog, DecisionAuditEntry
from src.platform.support.models.base.task import Task
from src.platform.support.models.base.state import GapState, DriveWeights


class TestDecisionAuditLogNormalCases:
    """测试正常值"""

    def setup_method(self):
        self.audit = DecisionAuditLog()
        self.gaps = GapState(safety=0.5, gain=0.6, efficiency=0.3)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_log_decision(self):
        """正常值：记录决策"""
        task = Task(name="test_task", target_drive="gain")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.8)
        assert isinstance(entry, DecisionAuditEntry)
        assert entry.selected_task_id == task.id
        assert entry.selected_task_score == 0.8
        assert not entry.is_exploration

    def test_log_exploration(self):
        """正常值：记录探索决策"""
        task = Task(name="explore_task", target_drive="safe")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, True, 0.5)
        assert entry.is_exploration
        assert "探索" in entry.reasoning

    def test_entry_count(self):
        """正常值：条目计数"""
        assert self.audit.get_entry_count() == 0
        task = Task(name="t1")
        self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        assert self.audit.get_entry_count() == 1

    def test_get_entries(self):
        """正常值：获取条目"""
        for i in range(5):
            task = Task(name=f"t{i}")
            self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        entries = self.audit.get_entries(limit=3)
        assert len(entries) == 3

    def test_exploration_ratio(self):
        """正常值：探索比例"""
        task = Task(name="t")
        self.audit.log_decision(self.gaps, self.weights, [task], task, True, 0.5)
        self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        assert self.audit.get_exploration_ratio() == 0.5

    def test_dominant_drive_reasoning(self):
        """正常值：主导驱力在理由中"""
        gaps = GapState(safety=0.1, gain=0.9, efficiency=0.1)
        task = Task(name="gain_task", target_drive="gain")
        entry = self.audit.log_decision(gaps, self.weights, [task], task, False, 0.8)
        assert "gain" in entry.reasoning


class TestDecisionAuditLogBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.audit = DecisionAuditLog()
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_empty_log(self):
        """空入参：空日志"""
        assert self.audit.get_entry_count() == 0
        assert self.audit.get_exploration_ratio() == 0.0
        assert self.audit.get_entries() == []

    def test_max_entries_limit(self):
        """边界极值：最大条目限制"""
        audit = DecisionAuditLog(max_entries=5)
        for i in range(10):
            task = Task(name=f"t{i}")
            audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        assert audit.get_entry_count() == 5

    def test_cycle_tracking(self):
        """边界：周期跟踪"""
        self.audit.set_cycle(42)
        task = Task(name="t")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        assert entry.cycle == 42

    def test_alternatives_limit(self):
        """边界：备选任务最多5个"""
        tasks = [Task(name=f"t{i}") for i in range(10)]
        selected = tasks[0]
        entry = self.audit.log_decision(self.gaps, self.weights, tasks, selected, False, 0.5)
        assert len(entry.alternatives) <= 5
        assert selected.id not in entry.alternatives

    def test_entry_to_dict(self):
        """正常值：条目转字典"""
        task = Task(name="t")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        d = entry.to_dict()
        assert "entry_id" in d
        assert "timestamp" in d
        assert "reasoning" in d


class TestDecisionAuditLogInvalidInputs:
    """测试非法输入"""

    def setup_method(self):
        self.audit = DecisionAuditLog()
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_clear_log(self):
        """正常值：清空日志"""
        task = Task(name="t")
        self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        self.audit.clear()
        assert self.audit.get_entry_count() == 0

    def test_zero_score(self):
        """边界极值：分数为0"""
        task = Task(name="t")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.0)
        assert entry.selected_task_score == 0.0

    def test_single_alternative(self):
        """边界：只有一个任务"""
        task = Task(name="only")
        entry = self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.5)
        assert entry.alternatives == []

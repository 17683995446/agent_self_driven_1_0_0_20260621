"""
任务评分函数测试

验证评分公式的正确性、边界条件、非法输入
"""

import pytest

from src.left.action.decision.task_scorer import StandardTaskScorer
from src.platform.support.models.base.task import Task, TaskPriority
from src.platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class TestTaskScorerNormalCases:
    """测试正常值"""

    def setup_method(self):
        self.scorer = StandardTaskScorer()
        self.gaps = GapState(safety=0.5, gain=0.6, efficiency=0.3)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        self.state = EnvironmentState()

    def test_safe_task_scoring(self):
        """正常值：安全任务评分"""
        task = Task(name="safe_task", target_drive="safe", priority=TaskPriority.HIGH)
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0
        assert score > 0.0

    def test_gain_task_scoring(self):
        """正常值：收益任务评分"""
        task = Task(name="gain_task", target_drive="gain", priority=TaskPriority.NORMAL)
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_eff_task_scoring(self):
        """正常值：能效任务评分"""
        task = Task(name="eff_task", target_drive="eff", priority=TaskPriority.LOW)
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_exploration_task_bonus(self):
        """正常值：探索任务有新颖性加分"""
        normal_task = Task(name="normal", target_drive="gain")
        explore_task = Task(name="explore", target_drive="gain", is_exploration=True)
        normal_score = self.scorer.score(normal_task, self.gaps, self.weights, self.state)
        explore_score = self.scorer.score(explore_task, self.gaps, self.weights, self.state)
        assert explore_score > normal_score

    def test_high_success_rate_boost(self):
        """正常值：高成功率提升分数"""
        task = Task(name="high_success", target_drive="gain")
        task.execution_count = 10
        task.success_count = 9
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert score > 0.0


class TestTaskScorerBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.scorer = StandardTaskScorer()
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        self.state = EnvironmentState()

    def test_zero_gaps(self):
        """边界极值：所有缺口为零"""
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        task = Task(name="task", target_drive="safe")
        score = self.scorer.score(task, gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_max_gaps(self):
        """边界极值：所有缺口为1.0"""
        gaps = GapState(safety=1.0, gain=1.0, efficiency=1.0)
        task = Task(name="task", target_drive="safe")
        score = self.scorer.score(task, gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0
        assert score > 0.4

    def test_zero_execution_count(self):
        """边界：execution_count=0时使用默认成功率0.5"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        task = Task(name="new_task", target_drive="gain")
        assert task.execution_count == 0
        score = self.scorer.score(task, gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_perfect_success_rate(self):
        """边界极值：100%成功率"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        task = Task(name="perfect", target_drive="gain")
        task.execution_count = 100
        task.success_count = 100
        score = self.scorer.score(task, gaps, self.weights, self.state)
        assert score > 0.0

    def test_zero_success_rate(self):
        """边界极值：0%成功率"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        task = Task(name="failure", target_drive="gain")
        task.execution_count = 10
        task.success_count = 0
        score = self.scorer.score(task, gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_critical_priority_urgency(self):
        """边界：CRITICAL优先级紧急程度最高"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        critical = Task(name="crit", target_drive="gain", priority=TaskPriority.CRITICAL)
        low = Task(name="low", target_drive="gain", priority=TaskPriority.LOW)
        crit_score = self.scorer.score(critical, gaps, self.weights, self.state)
        low_score = self.scorer.score(low, gaps, self.weights, self.state)
        assert crit_score >= low_score

    def test_expired_task_bonus(self):
        """边界：过期任务有额外奖励"""
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        expired = Task(name="expired", target_drive="gain")
        expired.deadline = 0.0
        normal = Task(name="normal", target_drive="gain")
        normal.deadline = 9999999999.0
        expired_score = self.scorer.score(expired, gaps, self.weights, self.state)
        normal_score = self.scorer.score(normal, gaps, self.weights, self.state)
        assert expired_score > normal_score


class TestTaskScorerInvalidInputs:
    """测试非法格式输入"""

    def setup_method(self):
        self.scorer = StandardTaskScorer()
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        self.state = EnvironmentState()

    def test_unknown_drive(self):
        """非法格式：未知驱力类型返回0.0匹配度"""
        task = Task(name="unknown", target_drive="unknown")
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_negative_gap_values(self):
        """非法格式：负缺口值（虽然GapState会限制，但评分器应能处理）"""
        task = Task(name="task", target_drive="safe")
        score = self.scorer.score(task, self.gaps, self.weights, self.state)
        assert 0.0 <= score <= 1.0

    def test_score_always_bounded(self):
        """边界：分数始终在 [0.0, 1.0] 内"""
        for drive in ["safe", "gain", "eff", "unknown"]:
            for priority in TaskPriority:
                task = Task(name="t", target_drive=drive, priority=priority)
                task.is_exploration = True
                score = self.scorer.score(task, self.gaps, self.weights, self.state)
                assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for drive={drive}"


class TestTaskScorerWeights:
    """测试权重配置"""

    def test_weights_sum_consistency(self):
        """验证权重和的一致性"""
        weights = (
            StandardTaskScorer.WEIGHT_GAP_MATCH +
            StandardTaskScorer.WEIGHT_URGENCY +
            StandardTaskScorer.WEIGHT_SUCCESS_RATE +
            StandardTaskScorer.WEIGHT_NOVELTY +
            StandardTaskScorer.WEIGHT_COST +
            StandardTaskScorer.WEIGHT_EXPIRED
        )
        assert abs(weights - 1.0) < 1e-6

"""
探索-利用决策策略测试

验证UCB和Epsilon-Greedy策略的正确性
"""

import pytest

from src.left.action.decision.exploration_policy import UCBExplorationPolicy, EpsilonGreedyPolicy
from src.platform.support.models.base.task import Task
from src.platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class TestUCBExplorationPolicy:
    """测试UCB策略"""

    def setup_method(self):
        self.policy = UCBExplorationPolicy()
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_select_untried_first(self):
        """正常值：优先选择未尝试过的任务"""
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.5, task1), (0.6, task2)]
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None
        assert selected.id in ["t1", "t2"]

    def test_ucb_computation(self):
        """正常值：UCB值计算"""
        task = Task(id="t1", name="task1")
        self.policy._counts["t1"] = 5
        self.policy._values["t1"] = 0.5
        self.policy._total_pulls = 10
        ucb = self.policy._compute_ucb("t1", 0.5)
        assert ucb > 0.5

    def test_update_reward(self):
        """正常值：奖励更新"""
        self.policy.update_reward("t1", 1.0)
        assert self.policy._counts["t1"] == 1
        assert self.policy._values["t1"] == 1.0
        self.policy.update_reward("t1", 0.0)
        assert self.policy._counts["t1"] == 2
        assert self.policy._values["t1"] == 0.5

    def test_empty_tasks(self):
        """空入参：空任务列表"""
        selected = self.policy.select_task([], self.gaps, self.weights)
        assert selected is None

    def test_stats_format(self):
        """正常值：统计信息格式"""
        self.policy.update_reward("t1", 1.0)
        stats = self.policy.get_stats()
        assert "t1" in stats
        assert "count" in stats["t1"]
        assert "average_reward" in stats["t1"]


class TestEpsilonGreedyPolicy:
    """测试Epsilon-Greedy策略"""

    def setup_method(self):
        self.policy = EpsilonGreedyPolicy(epsilon=1.0)
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_always_explore_when_epsilon_one(self):
        """正常值：epsilon=1.0时总是探索"""
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.9, task1), (0.1, task2)]
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None
        assert self.policy._exploration_count > 0

    def test_always_exploit_when_epsilon_zero(self):
        """边界极值：epsilon=0.0时总是利用"""
        policy = EpsilonGreedyPolicy(epsilon=0.0)
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.9, task1), (0.1, task2)]
        selected = policy.select_task(scored, self.gaps, self.weights)
        assert selected == task1
        assert policy._exploitation_count == 1

    def test_explore_marks_task(self):
        """正常值：探索时标记任务"""
        task = Task(id="t1", name="task1")
        scored = [(0.5, task)]
        self.policy._explore(scored)
        assert task.is_exploration

    def test_exploit_selects_best(self):
        """正常值：利用选择最高分"""
        best = Task(id="best", name="best")
        worst = Task(id="worst", name="worst")
        scored = [(0.9, best), (0.1, worst)]
        selected = self.policy._exploit(scored)
        assert selected == best

    def test_epsilon_decay(self):
        """正常值：epsilon衰减"""
        policy = EpsilonGreedyPolicy(epsilon=0.5, min_epsilon=0.1)
        policy.decay_epsilon(decay_rate=0.5)
        assert policy.epsilon == 0.25
        policy.decay_epsilon(decay_rate=0.1)
        assert policy.epsilon == 0.1

    def test_empty_tasks(self):
        """空入参：空任务列表"""
        selected = self.policy.select_task([], self.gaps, self.weights)
        assert selected is None

    def test_stats_tracking(self):
        """正常值：统计跟踪"""
        task = Task(id="t1", name="task1")
        scored = [(0.5, task)]
        self.policy.select_task(scored, self.gaps, self.weights)
        stats = self.policy.get_stats()
        assert "exploration_count" in stats
        assert "exploitation_count" in stats
        assert "current_epsilon" in stats


class TestExplorationPolicyBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_ucb_with_single_task(self):
        """边界：单个任务"""
        policy = UCBExplorationPolicy()
        task = Task(id="t1", name="task1")
        scored = [(0.5, task)]
        selected = policy.select_task(scored, self.gaps, self.weights)
        assert selected == task

    def test_epsilon_greedy_with_single_task(self):
        """边界：单个任务"""
        policy = EpsilonGreedyPolicy(epsilon=0.5)
        task = Task(id="t1", name="task1")
        scored = [(0.5, task)]
        selected = policy.select_task(scored, self.gaps, self.weights)
        assert selected == task

    def test_ucb_with_many_tasks(self):
        """边界极值：大量任务"""
        policy = UCBExplorationPolicy()
        scored = [(i / 100.0, Task(id=f"t{i}", name=f"task{i}")) for i in range(100)]
        selected = policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None

    def test_reward_averaging(self):
        """边界：奖励平均计算"""
        policy = UCBExplorationPolicy()
        for i in range(10):
            policy.update_reward("t1", float(i) / 10.0)
        stats = policy.get_stats()
        assert stats["t1"]["count"] == 10
        expected_avg = sum(float(i) / 10.0 for i in range(10)) / 10.0
        assert abs(stats["t1"]["average_reward"] - expected_avg) < 1e-6

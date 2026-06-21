"""
探索-利用平衡R70完善测试

验证Softmax策略、Thompson采样策略
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.decision.exploration_policy import (
    SoftmaxExplorationPolicy, ThompsonSamplingPolicy,
    ExplorationPolicy, UCBExplorationPolicy, EpsilonGreedyPolicy,
)
from src.platform.support.models.base.task import Task
from src.platform.support.models.base.state import GapState, DriveWeights


class TestSoftmaxExplorationPolicy:
    """测试Softmax探索策略"""

    def setup_method(self):
        self.policy = SoftmaxExplorationPolicy(temperature=1.0)
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_select_task_normal(self):
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.5, task1), (0.6, task2)]
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None
        assert selected.id in ["t1", "t2"]

    def test_empty_tasks(self):
        selected = self.policy.select_task([], self.gaps, self.weights)
        assert selected is None

    def test_single_task(self):
        task = Task(id="t1", name="task1")
        scored = [(0.5, task)]
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected == task

    def test_probability_distribution(self):
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.0, task1), (1.0, task2)]
        probs = self.policy._compute_probabilities(scored)
        assert len(probs) == 2
        assert abs(sum(probs) - 1.0) < 1e-6
        assert probs[1] > probs[0]

    def test_high_temperature_uniform(self):
        policy = SoftmaxExplorationPolicy(temperature=100.0)
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.1, task1), (0.9, task2)]
        probs = policy._compute_probabilities(scored)
        assert abs(probs[0] - probs[1]) < 0.1

    def test_low_temperature_peaked(self):
        policy = SoftmaxExplorationPolicy(temperature=0.01)
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.1, task1), (0.9, task2)]
        probs = policy._compute_probabilities(scored)
        assert probs[1] > 0.99

    def test_stats(self):
        stats = self.policy.get_stats()
        assert stats["temperature"] == 1.0

    def test_is_subclass(self):
        assert issubclass(SoftmaxExplorationPolicy, ExplorationPolicy)


class TestThompsonSamplingPolicy:
    """测试Thompson采样策略"""

    def setup_method(self):
        self.policy = ThompsonSamplingPolicy()
        self.gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)

    def test_select_task_normal(self):
        task1 = Task(id="t1", name="task1")
        task2 = Task(id="t2", name="task2")
        scored = [(0.5, task1), (0.6, task2)]
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None
        assert selected.id in ["t1", "t2"]

    def test_empty_tasks(self):
        selected = self.policy.select_task([], self.gaps, self.weights)
        assert selected is None

    def test_update_reward_positive(self):
        self.policy.update_reward("t1", 0.8)
        assert self.policy._alpha["t1"] == 2.0
        assert self.policy._beta["t1"] == 1.0

    def test_update_reward_negative(self):
        self.policy.update_reward("t1", 0.3)
        assert self.policy._alpha["t1"] == 1.0
        assert self.policy._beta["t1"] == 2.0

    def test_update_reward_multiple(self):
        self.policy.update_reward("t1", 0.8)
        self.policy.update_reward("t1", 0.8)
        self.policy.update_reward("t1", 0.3)
        assert self.policy._alpha["t1"] == 3.0
        assert self.policy._beta["t1"] == 2.0

    def test_sample_posterior_range(self):
        for _ in range(10):
            sample = self.policy._sample_posterior("unknown")
            assert 0.0 <= sample <= 1.0

    def test_stats(self):
        self.policy.update_reward("t1", 0.8)
        stats = self.policy.get_stats()
        assert "t1" in stats
        assert "alpha" in stats["t1"]
        assert "beta" in stats["t1"]

    def test_is_subclass(self):
        assert issubclass(ThompsonSamplingPolicy, ExplorationPolicy)

    def test_biased_toward_high_reward(self):
        task1 = Task(id="good", name="good")
        task2 = Task(id="bad", name="bad")
        for _ in range(20):
            self.policy.update_reward("good", 0.9)
            self.policy.update_reward("bad", 0.1)
        counts = {"good": 0, "bad": 0}
        scored = [(0.5, task1), (0.5, task2)]
        for _ in range(100):
            selected = self.policy.select_task(scored, self.gaps, self.weights)
            counts[selected.id] += 1
        assert counts["good"] > counts["bad"]


class TestExplorationPolicyBase:
    """测试策略基类"""

    def test_ucb_is_subclass(self):
        assert issubclass(UCBExplorationPolicy, ExplorationPolicy)

    def test_epsilon_greedy_is_subclass(self):
        assert issubclass(EpsilonGreedyPolicy, ExplorationPolicy)

    def test_softmax_is_subclass(self):
        assert issubclass(SoftmaxExplorationPolicy, ExplorationPolicy)

    def test_thompson_is_subclass(self):
        assert issubclass(ThompsonSamplingPolicy, ExplorationPolicy)

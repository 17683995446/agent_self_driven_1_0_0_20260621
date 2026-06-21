"""
自适应探索-利用平衡测试

验证探索比例调整、UCB1算法、停滞检测的正确性
"""

import pytest
import time

from src.left.cognition.prediction.exploration import (
    ExplorationState, AdaptiveExplorationBalancer, MultiArmedBanditExplorer,
)


class TestExplorationState:
    """测试探索状态"""

    def test_initial_state(self):
        state = ExplorationState()
        assert state.ratio == 0.3
        assert state.total_explorations == 0
        assert state.total_exploitations == 0

    def test_exploration_success_rate(self):
        state = ExplorationState(success_count=3, failure_count=7)
        assert state.exploration_success_rate == 0.3

    def test_exploration_success_rate_empty(self):
        state = ExplorationState()
        assert state.exploration_success_rate == 0.5

    def test_overall_success_rate(self):
        state = ExplorationState(
            success_count=5, failure_count=5,
            exploitation_success=8, exploitation_failure=2,
        )
        assert state.overall_success_rate == 0.65


class TestAdaptiveExplorationBalancer:
    """测试自适应探索平衡器"""

    def setup_method(self):
        self.balancer = AdaptiveExplorationBalancer(
            base_ratio=0.3,
            min_ratio=0.05,
            max_ratio=0.7,
            adaptation_rate=0.05,
        )

    def test_should_explore_distribution(self):
        # 统计多次调用的探索率
        explore_count = sum(1 for _ in range(1000) if self.balancer.should_explore())
        ratio = explore_count / 1000
        # 应该在0.3附近，允许较大误差
        assert 0.2 < ratio < 0.4

    def test_record_exploration_success(self):
        self.balancer.record_exploration_result(True, reward=1.0)
        assert self.balancer.state.success_count == 1
        assert len(self.balancer._reward_history) == 1

    def test_record_exploration_failure(self):
        self.balancer.record_exploration_result(False, reward=0.0)
        assert self.balancer.state.failure_count == 1

    def test_record_exploitation(self):
        self.balancer.record_exploitation_result(True, reward=1.0)
        assert self.balancer.state.exploitation_success == 1

    def test_adjust_error_rising(self):
        # 模拟误差上升趋势
        for i in range(10):
            self.balancer.update_error(float(i) * 0.1)
        old_ratio = self.balancer.state.ratio
        new_ratio = self.balancer.adjust(force=True)
        # 误差上升应减少探索
        assert new_ratio < old_ratio

    def test_adjust_error_falling(self):
        # 模拟误差下降趋势
        for i in range(10):
            self.balancer.update_error(1.0 - float(i) * 0.1)
        old_ratio = self.balancer.state.ratio
        new_ratio = self.balancer.adjust(force=True)
        # 误差下降应增加探索
        assert new_ratio > old_ratio

    def test_adjust_low_exploration_success(self):
        # 探索成功率很低
        for _ in range(10):
            self.balancer.record_exploration_result(False, reward=0.0)
        old_ratio = self.balancer.state.ratio
        new_ratio = self.balancer.adjust(force=True)
        # 成功率低应减少探索
        assert new_ratio < old_ratio

    def test_adjust_high_exploration_success(self):
        # 探索成功率很高
        for _ in range(10):
            self.balancer.record_exploration_result(True, reward=1.0)
        old_ratio = self.balancer.state.ratio
        new_ratio = self.balancer.adjust(force=True)
        # 成功率高应增加探索
        assert new_ratio > old_ratio

    def test_adjust_stagnation(self):
        # 模拟长期停滞（低奖励）
        for _ in range(60):
            self.balancer._reward_history.append(0.0)
        old_ratio = self.balancer.state.ratio
        new_ratio = self.balancer.adjust(force=True)
        # 停滞应增加探索
        assert new_ratio > old_ratio

    def test_adjust_min_bound(self):
        # 强制减少到最小值以下
        self.balancer.state.ratio = 0.06
        for _ in range(20):
            self.balancer.record_exploration_result(False, reward=0.0)
            self.balancer.update_error(1.0)
        new_ratio = self.balancer.adjust(force=True)
        assert new_ratio >= self.balancer.min_ratio

    def test_adjust_max_bound(self):
        # 强制增加到最大值以上
        self.balancer.state.ratio = 0.65
        for _ in range(20):
            self.balancer.record_exploration_result(True, reward=1.0)
            self.balancer.update_error(0.0)
        new_ratio = self.balancer.adjust(force=True)
        assert new_ratio <= self.balancer.max_ratio

    def test_adjust_cooldown(self):
        old_ratio = self.balancer.state.ratio
        self.balancer.adjust(force=False)
        # 立即再次调整（在冷却期内）
        new_ratio = self.balancer.adjust(force=False)
        assert new_ratio == old_ratio

    def test_get_state(self):
        state = self.balancer.get_state()
        assert "ratio" in state
        assert "success_rate" in state
        assert "error_trend" in state

    def test_reset(self):
        self.balancer.record_exploration_result(True, reward=1.0)
        self.balancer.update_error(0.5)
        self.balancer.reset()
        assert self.balancer.state.success_count == 0
        assert len(self.balancer._error_history) == 0
        assert self.balancer.state.ratio == self.balancer.base_ratio


class TestMultiArmedBanditExplorer:
    """测试多臂老虎机探索器"""

    def setup_method(self):
        self.mab = MultiArmedBanditExplorer(exploration_constant=1.414)

    def test_register_arm(self):
        self.mab.register_arm("arm1")
        assert "arm1" in self.mab._counts
        assert self.mab._counts["arm1"] == 0

    def test_select_arm_empty(self):
        assert self.mab.select_arm() is None

    def test_select_arm_untried_first(self):
        self.mab.register_arm("arm1")
        self.mab.register_arm("arm2")
        # 有未尝试的臂，优先选择
        selected = self.mab.select_arm()
        assert selected in ["arm1", "arm2"]

    def test_select_arm_ucb(self):
        self.mab.register_arm("good")
        self.mab.register_arm("bad")
        # good臂高奖励，bad臂低奖励
        for _ in range(10):
            self.mab.update("good", 1.0)
        for _ in range(10):
            self.mab.update("bad", 0.1)

        # 多次选择，good应该被选中更多次
        selections = {"good": 0, "bad": 0}
        for _ in range(100):
            arm = self.mab.select_arm()
            selections[arm] += 1
            self.mab.update(arm, 1.0 if arm == "good" else 0.1)

        assert selections["good"] > selections["bad"]

    def test_update(self):
        self.mab.register_arm("arm1")
        self.mab.update("arm1", 1.0)
        assert self.mab._counts["arm1"] == 1
        assert self.mab._values["arm1"] == 1.0

        self.mab.update("arm1", 0.0)
        assert self.mab._counts["arm1"] == 2
        assert self.mab._values["arm1"] == 0.5

    def test_get_arm_stats(self):
        self.mab.register_arm("arm1")
        self.mab.update("arm1", 0.8)
        stats = self.mab.get_arm_stats()
        assert stats["arm1"]["count"] == 1
        assert stats["arm1"]["average_reward"] == 0.8

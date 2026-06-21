"""
探索-利用平衡扩展测试

补充覆盖 ExplorationState、adjust、stagnation、comparison 等路径
"""

import pytest

from src.left.cognition.prediction.exploration import (
    AdaptiveExplorationBalancer, ExplorationBalancerBase,
    ExplorationState, MultiArmedBanditExplorer,
)


class TestExplorationState:
    """测试探索状态"""

    def test_total_explorations(self):
        state = ExplorationState()
        state.success_count = 3
        state.failure_count = 2
        assert state.total_explorations == 5

    def test_total_exploitations(self):
        state = ExplorationState()
        state.exploitation_success = 4
        state.exploitation_failure = 1
        assert state.total_exploitations == 5

    def test_exploration_success_rate_empty(self):
        state = ExplorationState()
        assert state.exploration_success_rate == 0.5

    def test_exploitation_success_rate_empty(self):
        state = ExplorationState()
        assert state.exploitation_success_rate == 0.5

    def test_overall_success_rate_empty(self):
        state = ExplorationState()
        assert state.overall_success_rate == 0.5

    def test_exploration_success_rate_with_data(self):
        state = ExplorationState()
        state.success_count = 8
        state.failure_count = 2
        assert state.exploration_success_rate == 0.8

    def test_exploitation_success_rate_with_data(self):
        state = ExplorationState()
        state.exploitation_success = 6
        state.exploitation_failure = 4
        assert state.exploitation_success_rate == 0.6

    def test_overall_success_rate_with_data(self):
        state = ExplorationState()
        state.success_count = 5
        state.failure_count = 5
        state.exploitation_success = 8
        state.exploitation_failure = 2
        assert state.overall_success_rate == 0.65


class TestAdaptiveExplorationBalancerExtended:
    """测试自适应探索平衡器扩展路径"""

    def test_should_explore(self):
        balancer = AdaptiveExplorationBalancer(base_ratio=1.0)
        assert balancer.should_explore() is True

    def test_should_not_explore(self):
        balancer = AdaptiveExplorationBalancer(base_ratio=0.0)
        assert balancer.should_explore() is False

    def test_record_exploration_result(self):
        balancer = AdaptiveExplorationBalancer()
        balancer.record_exploration_result(True, 1.0)
        assert balancer.state.success_count == 1

    def test_record_exploitation_result(self):
        balancer = AdaptiveExplorationBalancer()
        balancer.record_exploitation_result(False, 0.0)
        assert balancer.state.exploitation_failure == 1

    def test_update_error(self):
        balancer = AdaptiveExplorationBalancer()
        balancer.update_error(0.5)
        assert len(balancer._error_history) == 1

    def test_compute_error_trend_insufficient(self):
        balancer = AdaptiveExplorationBalancer()
        assert balancer._compute_error_trend() == 0.0

    def test_compute_error_trend_with_data(self):
        balancer = AdaptiveExplorationBalancer()
        for i in range(10):
            balancer.update_error(float(i) * 0.01)
        trend = balancer._compute_error_trend()
        assert trend > 0

    def test_is_stagnating_false(self):
        balancer = AdaptiveExplorationBalancer()
        assert balancer._is_stagnating() is False

    def test_is_stagnating_true(self):
        balancer = AdaptiveExplorationBalancer(stagnation_threshold=5)
        for _ in range(5):
            balancer._reward_history.append(0.0)
        assert balancer._is_stagnating() is True

    def test_apply_error_adjustment_positive(self):
        balancer = AdaptiveExplorationBalancer()
        result = balancer._apply_error_adjustment(0.3, 0.1)
        assert result < 0.3

    def test_apply_error_adjustment_negative(self):
        balancer = AdaptiveExplorationBalancer()
        result = balancer._apply_error_adjustment(0.3, -0.1)
        assert result > 0.3

    def test_apply_success_adjustment_low_rate(self):
        balancer = AdaptiveExplorationBalancer()
        for _ in range(10):
            balancer.record_exploration_result(False)
        result = balancer._apply_success_adjustment(0.3)
        assert result < 0.3

    def test_apply_success_adjustment_high_rate(self):
        balancer = AdaptiveExplorationBalancer()
        for _ in range(10):
            balancer.record_exploration_result(True)
        result = balancer._apply_success_adjustment(0.3)
        assert result > 0.3

    def test_apply_success_adjustment_insufficient(self):
        balancer = AdaptiveExplorationBalancer()
        result = balancer._apply_success_adjustment(0.3)
        assert result == 0.3

    def test_apply_comparison_adjustment_insufficient(self):
        balancer = AdaptiveExplorationBalancer()
        result = balancer._apply_comparison_adjustment(0.3)
        assert result == 0.3

    def test_apply_comparison_adjustment_explore_better(self):
        balancer = AdaptiveExplorationBalancer()
        for _ in range(10):
            balancer.record_exploration_result(True)
            balancer.record_exploitation_result(False)
        result = balancer._apply_comparison_adjustment(0.3)
        assert result > 0.3

    def test_apply_comparison_adjustment_exploit_better(self):
        balancer = AdaptiveExplorationBalancer()
        for _ in range(10):
            balancer.record_exploration_result(False)
            balancer.record_exploitation_result(True)
        result = balancer._apply_comparison_adjustment(0.3)
        assert result < 0.3

    def test_apply_stagnation_adjustment(self):
        balancer = AdaptiveExplorationBalancer(stagnation_threshold=5)
        for _ in range(5):
            balancer._reward_history.append(0.0)
        result = balancer._apply_stagnation_adjustment(0.3)
        assert result > 0.3

    def test_clamp_ratio(self):
        balancer = AdaptiveExplorationBalancer(min_ratio=0.1, max_ratio=0.5)
        assert balancer._clamp_ratio(0.0) == 0.1
        assert balancer._clamp_ratio(1.0) == 0.5
        assert balancer._clamp_ratio(0.3) == 0.3

    def test_adjust_cooldown(self):
        balancer = AdaptiveExplorationBalancer()
        balancer.state.last_adjustment = __import__('time').time()
        result = balancer.adjust()
        assert result == balancer.state.ratio

    def test_adjust_force(self):
        balancer = AdaptiveExplorationBalancer()
        result = balancer.adjust(force=True)
        assert result == balancer.state.ratio

    def test_adjust_with_stagnation(self):
        balancer = AdaptiveExplorationBalancer(stagnation_threshold=5)
        for _ in range(5):
            balancer._reward_history.append(0.0)
        result = balancer.adjust(force=True)
        assert result > balancer.base_ratio

    def test_get_state(self):
        balancer = AdaptiveExplorationBalancer()
        state = balancer.get_state()
        assert "ratio" in state
        assert "success_rate" in state

    def test_reset(self):
        balancer = AdaptiveExplorationBalancer()
        balancer.record_exploration_result(True)
        balancer.update_error(0.5)
        balancer.reset()
        assert balancer.state.success_count == 0
        assert len(balancer._error_history) == 0


class TestMultiArmedBanditExplorerExtended:
    """测试多臂老虎机扩展路径"""

    def test_register_arm(self):
        explorer = MultiArmedBanditExplorer()
        explorer.register_arm("arm1")
        assert "arm1" in explorer._counts

    def test_select_arm_empty(self):
        explorer = MultiArmedBanditExplorer()
        assert explorer.select_arm() is None

    def test_select_arm_untried(self):
        explorer = MultiArmedBanditExplorer()
        explorer.register_arm("arm1")
        explorer.register_arm("arm2")
        assert explorer.select_arm() in ["arm1", "arm2"]

    def test_select_arm_ucb(self):
        explorer = MultiArmedBanditExplorer()
        explorer.register_arm("arm1")
        explorer.register_arm("arm2")
        explorer.update("arm1", 1.0)
        explorer.update("arm1", 1.0)
        explorer.update("arm2", 0.0)
        selected = explorer.select_arm()
        assert selected is not None

    def test_update_new_arm(self):
        explorer = MultiArmedBanditExplorer()
        explorer.update("new_arm", 0.5)
        assert "new_arm" in explorer._counts
        assert explorer._counts["new_arm"] == 1

    def test_get_arm_stats(self):
        explorer = MultiArmedBanditExplorer()
        explorer.register_arm("arm1")
        stats = explorer.get_arm_stats()
        assert "arm1" in stats

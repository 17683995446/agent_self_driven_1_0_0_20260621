"""
感知模块优化器测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.optimizer import PerceptionOptimizer


class TestPerceptionOptimizerNormal:
    """正常值测试"""

    def test_init_default(self):
        opt = PerceptionOptimizer()
        assert opt.max_cpu == 0.02
        assert opt.max_memory_mb == 100.0
        assert opt.adaptive_sampling is True

    def test_optimize_rate_normal_load(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.5, 1.0)
        assert rate == 1.0

    def test_optimize_rate_high_load(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.8, 1.0)
        assert rate == 0.5

    def test_optimize_rate_low_load(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.2, 1.0)
        assert rate == 1.5

    def test_should_sample_first_time(self):
        opt = PerceptionOptimizer()
        assert opt.should_sample(10.0, 1.0) is True

    def test_throttle_delay_normal(self):
        opt = PerceptionOptimizer()
        assert opt.get_throttle_delay(0.01) == 0.0


class TestPerceptionOptimizerBoundary:
    """边界极值测试"""

    def test_optimize_rate_exactly_high_threshold(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.7, 1.0)
        assert rate == 1.0

    def test_optimize_rate_exactly_low_threshold(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.3, 1.0)
        assert rate == 1.0

    def test_throttle_delay_exactly_max(self):
        opt = PerceptionOptimizer()
        delay = opt.get_throttle_delay(0.02)
        assert delay == 0.0

    def test_throttle_delay_capped(self):
        opt = PerceptionOptimizer()
        delay = opt.get_throttle_delay(1.0)
        assert delay == 5.0

    def test_should_sample_exact_interval(self):
        opt = PerceptionOptimizer()
        opt._last_sample_time = 9.0
        assert opt.should_sample(10.0, 1.0) is True


class TestPerceptionOptimizerInvalid:
    """非法格式测试"""

    def test_optimize_rate_negative_load(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(-0.1, 1.0)
        assert rate == 1.5

    def test_optimize_rate_over_one_load(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(1.5, 1.0)
        assert rate == 0.5

    def test_optimize_rate_zero_base(self):
        opt = PerceptionOptimizer()
        rate = opt.optimize_rate(0.5, 0.0)
        assert rate == 0.0


class TestPerceptionOptimizerAdaptiveOff:
    """自适应关闭测试"""

    def test_optimize_rate_disabled(self):
        opt = PerceptionOptimizer(adaptive_sampling=False)
        rate = opt.optimize_rate(0.8, 1.0)
        assert rate == 1.0

    def test_should_sample_respects_interval(self):
        opt = PerceptionOptimizer()
        opt._last_sample_time = 10.0
        assert opt.should_sample(10.5, 1.0) is False
        assert opt.should_sample(11.0, 1.0) is True

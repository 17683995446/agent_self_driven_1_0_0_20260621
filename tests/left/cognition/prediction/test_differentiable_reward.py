"""
可微分驱力奖励测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import numpy as np
import pytest
from src.left.cognition.prediction.differentiable_reward import (
    SmoothSafetyReward, SmoothEfficiencyReward
)


class TestSmoothSafetyRewardNormal:
    """正常值测试"""

    def test_compute_low_load(self):
        reward = SmoothSafetyReward()
        vec = np.array([0.1, 0.1] + [0.0] * 15)
        val = reward.compute(vec)
        assert 0.0 <= val <= 1.0
        assert val > 0.5

    def test_compute_high_load(self):
        reward = SmoothSafetyReward()
        vec = np.array([0.9, 0.9] + [0.0] * 15)
        val = reward.compute(vec)
        assert 0.0 <= val <= 1.0
        assert val < 0.5

    def test_gradient_shape(self):
        reward = SmoothSafetyReward()
        vec = np.array([0.5, 0.5] + [0.0] * 15)
        grad = reward.gradient(vec)
        assert grad.shape == vec.shape

    def test_gradient_finite(self):
        reward = SmoothSafetyReward()
        vec = np.array([0.5, 0.5] + [0.0] * 15)
        grad = reward.gradient(vec)
        assert np.all(np.isfinite(grad))


class TestSmoothSafetyRewardBoundary:
    """边界极值测试"""

    def test_compute_zero_load(self):
        reward = SmoothSafetyReward()
        vec = np.zeros(17)
        val = reward.compute(vec)
        assert val > 0.99

    def test_compute_max_load(self):
        reward = SmoothSafetyReward()
        vec = np.ones(17)
        val = reward.compute(vec)
        assert val < 0.01

    def test_gradient_zero(self):
        reward = SmoothSafetyReward()
        vec = np.zeros(17)
        grad = reward.gradient(vec)
        assert grad[0] < 0
        assert grad[1] < 0


class TestSmoothEfficiencyRewardNormal:
    """正常值测试"""

    def test_compute_low_agent_load(self):
        reward = SmoothEfficiencyReward()
        vec = np.array([0.0] * 13 + [0.1, 0.1] + [0.0] * 2)
        val = reward.compute(vec)
        assert 0.0 <= val <= 1.0
        assert val > 0.8

    def test_compute_high_agent_load(self):
        reward = SmoothEfficiencyReward()
        vec = np.array([0.0] * 13 + [0.9, 0.9] + [0.0] * 2)
        val = reward.compute(vec)
        assert 0.0 <= val <= 1.0
        assert val < 0.5

    def test_gradient_shape(self):
        reward = SmoothEfficiencyReward()
        vec = np.zeros(17)
        grad = reward.gradient(vec)
        assert grad.shape == vec.shape


class TestSmoothEfficiencyRewardEmpty:
    """空入参/短向量测试"""

    def test_compute_short_vector(self):
        reward = SmoothEfficiencyReward()
        vec = np.zeros(5)
        val = reward.compute(vec)
        assert val == 1.0

    def test_gradient_short_vector(self):
        reward = SmoothEfficiencyReward()
        vec = np.zeros(5)
        grad = reward.gradient(vec)
        assert grad.shape == vec.shape

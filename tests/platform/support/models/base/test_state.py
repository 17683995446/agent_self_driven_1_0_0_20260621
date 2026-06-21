"""
状态模型测试

验证核心数据模型的正确性
"""

import pytest
from src.platform.support.models.base.state import (
    SystemState, LogState, FileState, SelfState,
    EnvironmentState, DriveWeights, DriveRewards, GapState,
    ResourceUsage
)


class TestSystemState:
    """系统状态测试"""
    
    def test_valid_state(self):
        """测试有效状态"""
        state = SystemState(cpu_overall=0.5, memory_usage=0.3)
        assert state.cpu_overall == 0.5
        assert state.memory_usage == 0.3
    
    def test_invalid_cpu(self):
        """测试无效CPU值"""
        with pytest.raises(ValueError):
            SystemState(cpu_overall=1.5)
    
    def test_invalid_memory(self):
        """测试无效内存值"""
        with pytest.raises(ValueError):
            SystemState(memory_usage=-0.1)
    
    def test_default_values(self):
        """测试默认值"""
        state = SystemState()
        assert state.cpu_overall == 0.0
        assert state.memory_usage == 0.0


class TestDriveWeights:
    """驱力权重测试"""
    
    def test_valid_weights(self):
        """测试有效权重"""
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        assert weights.safe == 0.4
        assert weights.gain == 0.4
        assert weights.eff == 0.2
    
    def test_invalid_sum(self):
        """测试权重和不等于1"""
        with pytest.raises(ValueError):
            DriveWeights(safe=0.5, gain=0.5, eff=0.5)
    
    def test_default_weights(self):
        """测试默认权重"""
        weights = DriveWeights()
        assert abs(weights.safe + weights.gain + weights.eff - 1.0) < 1e-6


class TestDriveRewards:
    """驱力奖励测试"""
    
    def test_valid_rewards(self):
        """测试有效奖励"""
        rewards = DriveRewards(safety=0.8, gain=0.6, efficiency=0.9)
        assert rewards.safety == 0.8
    
    def test_invalid_reward(self):
        """测试无效奖励值"""
        with pytest.raises(ValueError):
            DriveRewards(safety=1.5)
    
    def test_weighted_sum(self):
        """测试加权求和"""
        rewards = DriveRewards(safety=1.0, gain=0.5, efficiency=0.5)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        total = rewards.weighted_sum(weights)
        expected = 0.4 * 1.0 + 0.4 * 0.5 + 0.2 * 0.5
        assert abs(total - expected) < 1e-6


class TestGapState:
    """缺口状态测试"""
    
    def test_total_gap(self):
        """测试总缺口"""
        gaps = GapState(safety=0.3, gain=0.2, efficiency=0.1)
        assert gaps.total_gap == 0.6
    
    def test_dominant_drive(self):
        """测试主导驱力"""
        gaps = GapState(safety=0.8, gain=0.2, efficiency=0.1)
        from src.platform.support.models.base.state import DriveType
        assert gaps.dominant_drive == DriveType.SAFE
    
    def test_invalid_gap(self):
        """测试无效缺口值"""
        with pytest.raises(ValueError):
            GapState(safety=-0.1)


class TestEnvironmentState:
    """环境状态测试"""
    
    def test_default_state(self):
        """测试默认状态"""
        state = EnvironmentState()
        assert state.timestamp > 0
        assert state.system is not None
        assert state.logs is not None
        assert state.files is not None
        assert state.self is not None
    
    def test_to_vector(self):
        """测试向量化"""
        state = EnvironmentState()
        vector = state.to_vector()
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)
    
    def test_dimension(self):
        """测试维度"""
        state = EnvironmentState()
        assert state.dimension == len(state.to_vector())


class TestResourceUsage:
    """资源使用测试"""
    
    def test_valid_usage(self):
        """测试有效使用"""
        usage = ResourceUsage(cpu=0.1, memory=0.2)
        assert usage.cpu == 0.1
        assert usage.memory == 0.2
    
    def test_invalid_usage(self):
        """测试无效使用"""
        with pytest.raises(ValueError):
            ResourceUsage(cpu=1.5)

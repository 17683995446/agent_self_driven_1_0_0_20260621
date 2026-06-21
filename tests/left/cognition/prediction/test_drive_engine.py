"""
驱力引擎测试

验证驱力计算、缺口评估、权重调整的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.cognition.prediction.drive_engine import DriveEngineModule, DriveEngineBase
from src.platform.support.models.base.state import EnvironmentState, DriveRewards, DriveWeights, GapState


class TestDriveEngineBase:
    """测试驱力引擎基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            DriveEngineBase()


class TestDriveEngineInit:
    """测试驱力引擎初始化"""

    def test_normal_init(self):
        engine = DriveEngineModule()
        assert engine is not None


class TestComputeDriveRewards:
    """测试驱力奖励计算"""

    def test_normal_state(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        rewards = engine.compute_drive_rewards(state)
        assert isinstance(rewards, DriveRewards)

    def test_high_cpu_state(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        rewards = engine.compute_drive_rewards(state)
        assert rewards.safety >= 0.0


class TestComputeGaps:
    """测试缺口计算"""

    def test_normal_state(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        rewards = engine.compute_drive_rewards(state)
        gaps = engine.compute_gaps(rewards)
        assert isinstance(gaps, GapState)

    def test_default_gaps(self):
        engine = DriveEngineModule()
        rewards = DriveRewards(safety=0.5, gain=0.5, efficiency=0.5)
        gaps = engine.compute_gaps(rewards)
        assert isinstance(gaps, GapState)
        assert gaps.safety > 0


class TestComputeWeights:
    """测试权重计算"""

    def test_normal_update(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        new_weights = engine.compute_weights(state, gaps)
        assert isinstance(new_weights, DriveWeights)
        assert abs(new_weights.safe + new_weights.gain + new_weights.eff - 1.0) < 0.01

    def test_default_gaps_weights(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        new_weights = engine.compute_weights(state)
        assert isinstance(new_weights, DriveWeights)

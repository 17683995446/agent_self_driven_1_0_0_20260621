"""
驱力引擎扩展测试

补充覆盖 compute_global_reward、emergency_override、weight_history 等路径
"""

import pytest

from src.left.cognition.prediction.drive_engine import DriveEngineModule, DriveEngineBase
from src.platform.support.models.base.state import EnvironmentState, DriveRewards, DriveWeights, GapState


class TestDriveEngineExtended:
    """测试驱力引擎扩展路径"""

    def test_compute_global_reward(self):
        engine = DriveEngineModule()
        rewards = DriveRewards(safety=0.5, gain=0.3, efficiency=0.2)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        global_reward = engine.compute_global_reward(rewards, weights)
        assert 0.0 <= global_reward <= 1.0

    def test_compute_global_reward_defaults(self):
        engine = DriveEngineModule()
        engine.last_rewards = DriveRewards(safety=0.5, gain=0.3, efficiency=0.2)
        engine.current_weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        global_reward = engine.compute_global_reward()
        assert 0.0 <= global_reward <= 1.0

    def test_emergency_override_safety(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        gaps = GapState(safety=0.8, gain=0.1, efficiency=0.1)
        weights = engine.compute_weights(state, gaps)
        assert weights.safe >= 0.5

    def test_emergency_override_memory(self):
        engine = DriveEngineModule()
        from dataclasses import replace
        system = replace(state.system, memory_pressure=0.95) if 'state' in dir() else None
        state = EnvironmentState()
        from dataclasses import replace
        high_mem_system = replace(state.system, memory_pressure=0.95)
        state = replace(state, system=high_mem_system)
        gaps = GapState(safety=0.1, gain=0.1, efficiency=0.1)
        weights = engine.compute_weights(state, gaps)
        assert weights.eff >= 0.5

    def test_weight_history(self):
        engine = DriveEngineModule()
        state = EnvironmentState()
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        engine.compute_weights(state, gaps)
        assert len(engine.weight_history) == 1

    def test_compute_gaps_default(self):
        engine = DriveEngineModule()
        engine.last_rewards = DriveRewards(safety=0.5, gain=0.3, efficiency=0.2)
        gaps = engine.compute_gaps()
        assert isinstance(gaps, GapState)

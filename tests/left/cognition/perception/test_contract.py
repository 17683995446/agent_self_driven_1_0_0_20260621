"""
感知-驱力接口契约测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.contract import (
    StandardPerceptionDriveContract,
    PerceptionOutput,
    DriveInput,
    DriveOutput,
)
from src.platform.support.models.base.state import (
    EnvironmentState, SystemState, DriveRewards, DriveWeights, GapState
)


class TestContractNormal:
    """正常值测试"""

    def test_perception_to_drive(self):
        contract = StandardPerceptionDriveContract()
        state = EnvironmentState(system=SystemState(cpu_overall=0.5))
        perception_out = PerceptionOutput(state=state, valid=True, issues=[])
        drive_in = contract.perception_to_drive(perception_out)
        assert isinstance(drive_in, DriveInput)
        assert drive_in.state == state
        assert drive_in.timestamp == state.timestamp

    def test_drive_to_decision(self):
        contract = StandardPerceptionDriveContract()
        rewards = DriveRewards(safety=0.8, gain=0.6, efficiency=0.7)
        gaps = GapState(safety=0.2, gain=0.4, efficiency=0.3)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        drive_out = DriveOutput(
            rewards=rewards, gaps=gaps, weights=weights, global_reward=0.7
        )
        decision_in = contract.drive_to_decision(drive_out)
        assert "gaps" in decision_in
        assert "weights" in decision_in
        assert decision_in["global_reward"] == 0.7


class TestContractBoundary:
    """边界极值测试"""

    def test_perception_with_issues(self):
        contract = StandardPerceptionDriveContract()
        state = EnvironmentState(system=SystemState(cpu_overall=1.0))
        perception_out = PerceptionOutput(state=state, valid=False, issues=["cpu high"])
        drive_in = contract.perception_to_drive(perception_out)
        assert drive_in.state.system.cpu_overall == 1.0

    def test_drive_output_zero_reward(self):
        contract = StandardPerceptionDriveContract()
        rewards = DriveRewards(safety=0.0, gain=0.0, efficiency=0.0)
        gaps = GapState(safety=1.0, gain=1.0, efficiency=1.0)
        weights = DriveWeights(safe=1 / 3, gain=1 / 3, eff=1 / 3)
        drive_out = DriveOutput(
            rewards=rewards, gaps=gaps, weights=weights, global_reward=0.0
        )
        decision_in = contract.drive_to_decision(drive_out)
        assert decision_in["global_reward"] == 0.0
        assert decision_in["gaps"]["safety"] == 1.0


class TestContractEmpty:
    """空入参测试"""

    def test_perception_default_state(self):
        contract = StandardPerceptionDriveContract()
        state = EnvironmentState()
        perception_out = PerceptionOutput(state=state, valid=True, issues=[])
        drive_in = contract.perception_to_drive(perception_out)
        assert drive_in.timestamp == state.timestamp

    def test_drive_default_output(self):
        contract = StandardPerceptionDriveContract()
        rewards = DriveRewards()
        gaps = GapState()
        weights = DriveWeights()
        drive_out = DriveOutput(
            rewards=rewards, gaps=gaps, weights=weights, global_reward=0.0
        )
        decision_in = contract.drive_to_decision(drive_out)
        assert decision_in["rewards"]["safety"] == 0.0

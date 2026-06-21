"""
驱力-决策接口契约测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.prediction.drive_decision_contract import (
    StandardDriveDecisionContract, DecisionInput, DecisionOutput
)
from src.platform.support.models.base.state import (
    EnvironmentState, SystemState, DriveRewards, DriveWeights, GapState
)


class TestDriveDecisionContractNormal:
    """正常值测试"""

    def test_drive_to_decision(self):
        contract = StandardDriveDecisionContract()
        drive_data = {
            "gaps": GapState(safety=0.2, gain=0.3, efficiency=0.1),
            "weights": DriveWeights(safe=0.4, gain=0.4, eff=0.2),
            "global_reward": 0.75,
            "rewards": DriveRewards(safety=0.8, gain=0.7, efficiency=0.6),
        }
        state = EnvironmentState(system=SystemState(cpu_overall=0.5))
        decision_in = contract.drive_to_decision(drive_data, state)
        assert isinstance(decision_in, DecisionInput)
        assert decision_in.gaps.safety == 0.2
        assert decision_in.global_reward == 0.75
        assert decision_in.state.system.cpu_overall == 0.5

    def test_decision_to_execution(self):
        contract = StandardDriveDecisionContract()
        decision_out = DecisionOutput(
            task_name="optimize_cpu",
            priority=0.8,
            drive_type="safe",
            params={"target": 0.1},
        )
        execution_in = contract.decision_to_execution(decision_out)
        assert execution_in["task"] == "optimize_cpu"
        assert execution_in["priority"] == 0.8
        assert execution_in["params"]["target"] == 0.1


class TestDriveDecisionContractEmpty:
    """空入参测试"""

    def test_drive_to_decision_defaults(self):
        contract = StandardDriveDecisionContract()
        state = EnvironmentState()
        decision_in = contract.drive_to_decision({}, state)
        assert decision_in.gaps == GapState()
        assert decision_in.weights == DriveWeights()
        assert decision_in.global_reward == 0.0
        assert decision_in.rewards == DriveRewards()

    def test_decision_empty_params(self):
        contract = StandardDriveDecisionContract()
        decision_out = DecisionOutput(
            task_name="idle", priority=0.0, drive_type="eff", params={}
        )
        execution_in = contract.decision_to_execution(decision_out)
        assert execution_in["params"] == {}


class TestDriveDecisionContractBoundary:
    """边界极值测试"""

    def test_max_priority(self):
        contract = StandardDriveDecisionContract()
        decision_out = DecisionOutput(
            task_name="critical", priority=1.0, drive_type="safe", params={}
        )
        execution_in = contract.decision_to_execution(decision_out)
        assert execution_in["priority"] == 1.0

    def test_zero_priority(self):
        contract = StandardDriveDecisionContract()
        decision_out = DecisionOutput(
            task_name="low", priority=0.0, drive_type="eff", params={}
        )
        execution_in = contract.decision_to_execution(decision_out)
        assert execution_in["priority"] == 0.0


class TestDriveDecisionContractInvalid:
    """非法格式测试"""

    def test_missing_keys_use_defaults(self):
        contract = StandardDriveDecisionContract()
        state = EnvironmentState()
        decision_in = contract.drive_to_decision({"global_reward": 0.5}, state)
        assert decision_in.global_reward == 0.5
        assert decision_in.gaps == GapState()

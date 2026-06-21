"""
驱力-决策接口契约

第一性原理：模块间通信必须有明确契约
类比：生物神经系统中，边缘系统（情绪）与额叶（决策）之间的神经投射有明确拓扑
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

from ....platform.support.models.base.state import (
    EnvironmentState, DriveRewards, DriveWeights, GapState
)


@dataclass
class DecisionInput:
    """决策引擎输入契约"""
    gaps: GapState
    weights: DriveWeights
    global_reward: float
    state: EnvironmentState
    rewards: DriveRewards


@dataclass
class DecisionOutput:
    """决策引擎输出契约"""
    task_name: str
    priority: float
    drive_type: str
    params: Dict[str, Any]


class DriveDecisionContract(ABC):
    """驱力-决策接口契约抽象基类"""

    @abstractmethod
    def drive_to_decision(self, drive_data: Dict[str, Any], state: EnvironmentState) -> DecisionInput:
        """将驱力输出转换为决策输入"""
        pass

    @abstractmethod
    def decision_to_execution(self, decision_output: DecisionOutput) -> Dict[str, Any]:
        """将决策输出转换为执行输入"""
        pass


class StandardDriveDecisionContract(DriveDecisionContract):
    """标准驱力-决策契约实现"""

    def drive_to_decision(
        self,
        drive_data: Dict[str, Any],
        state: EnvironmentState,
    ) -> DecisionInput:
        """将驱力输出转换为决策输入"""
        gaps = drive_data.get("gaps", GapState())
        weights = drive_data.get("weights", DriveWeights())
        global_reward = drive_data.get("global_reward", 0.0)
        rewards = drive_data.get("rewards", DriveRewards())
        return DecisionInput(
            gaps=gaps,
            weights=weights,
            global_reward=global_reward,
            state=state,
            rewards=rewards,
        )

    def decision_to_execution(self, decision_output: DecisionOutput) -> Dict[str, Any]:
        """将决策输出转换为执行输入"""
        return {
            "task": decision_output.task_name,
            "priority": decision_output.priority,
            "drive": decision_output.drive_type,
            "params": decision_output.params,
        }

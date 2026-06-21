"""
感知-驱力接口契约

第一性原理：模块间通信必须有明确契约，否则系统无法组合
类比：生物神经系统中，感觉神经元和运动神经元之间的突触连接有明确的神经递质协议
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List

from ....platform.support.models.base.state import EnvironmentState, DriveRewards, DriveWeights, GapState


@dataclass
class PerceptionOutput:
    """感知模块输出契约"""
    state: EnvironmentState
    valid: bool
    issues: List[str]


@dataclass
class DriveInput:
    """驱力引擎输入契约"""
    state: EnvironmentState
    timestamp: float


@dataclass
class DriveOutput:
    """驱力引擎输出契约"""
    rewards: DriveRewards
    gaps: GapState
    weights: DriveWeights
    global_reward: float


class PerceptionDriveContract(ABC):
    """
    感知-驱力接口契约

    定义感知模块和驱力引擎之间的数据交换格式
    """

    @abstractmethod
    def perception_to_drive(self, perception_output: PerceptionOutput) -> DriveInput:
        """将感知输出转换为驱力输入"""
        pass

    @abstractmethod
    def drive_to_decision(self, drive_output: DriveOutput) -> Dict[str, Any]:
        """将驱力输出转换为决策输入"""
        pass


class StandardPerceptionDriveContract(PerceptionDriveContract):
    """标准感知-驱力契约实现"""

    def perception_to_drive(self, perception_output: PerceptionOutput) -> DriveInput:
        """将感知输出转换为驱力输入"""
        return DriveInput(
            state=perception_output.state,
            timestamp=perception_output.state.timestamp,
        )

    def drive_to_decision(self, drive_output: DriveOutput) -> Dict[str, Any]:
        """将驱力输出转换为决策输入"""
        return {
            "gaps": drive_output.gaps.to_dict(),
            "weights": drive_output.weights.to_dict(),
            "global_reward": drive_output.global_reward,
            "rewards": drive_output.rewards.to_dict(),
        }

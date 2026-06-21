"""
预测-决策接口契约

第一性原理：预测结果必须可转化为决策输入，否则预测无用
类比：生物大脑中，前额叶皮层（预测）向运动皮层（决策）传递意图
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from ....platform.support.models.base.state import EnvironmentState
from .prediction_layer import LayerOutput


@dataclass
class PredictionDecisionInput:
    """预测到决策的输入"""
    predicted_state: EnvironmentState
    confidence: float
    uncertainty: Dict[str, float]
    time_scale: str
    horizon: int


@dataclass
class PredictionDecisionOutput:
    """预测到决策的输出"""
    decision_type: str
    priority: float
    predicted_risk: float
    recommended_action: str
    params: Dict[str, Any]


class PredictionDecisionContract(ABC):
    """预测-决策接口契约抽象基类"""

    @abstractmethod
    def prediction_to_decision(self, prediction: LayerOutput, time_scale: str) -> PredictionDecisionInput:
        """将预测输出转换为决策输入"""
        pass

    @abstractmethod
    def decision_to_action(self, decision_input: PredictionDecisionInput) -> PredictionDecisionOutput:
        """将决策输入转换为行动建议"""
        pass


class StandardPredictionDecisionContract(PredictionDecisionContract):
    """标准预测-决策契约实现"""

    def prediction_to_decision(self, prediction: LayerOutput, time_scale: str) -> PredictionDecisionInput:
        """将预测输出转换为决策输入"""
        return PredictionDecisionInput(
            predicted_state=prediction.prediction,
            confidence=prediction.confidence,
            uncertainty=prediction.uncertainty,
            time_scale=time_scale,
            horizon=self._get_horizon(time_scale),
        )

    def _get_horizon(self, time_scale: str) -> int:
        """根据时间尺度获取预测步数"""
        horizons = {"low": 1, "mid": 5, "high": 24}
        return horizons.get(time_scale, 1)

    def decision_to_action(self, decision_input: PredictionDecisionInput) -> PredictionDecisionOutput:
        """将决策输入转换为行动建议"""
        risk = self._calculate_risk(decision_input)
        action = self._recommend_action(decision_input, risk)
        return PredictionDecisionOutput(
            decision_type=decision_input.time_scale,
            priority=self._calculate_priority(risk, decision_input.confidence),
            predicted_risk=risk,
            recommended_action=action,
            params={"horizon": decision_input.horizon},
        )

    def _calculate_risk(self, decision_input: PredictionDecisionInput) -> float:
        """计算预测风险"""
        state = decision_input.predicted_state
        cpu_risk = state.system.cpu_overall
        mem_risk = state.system.memory_usage
        return 0.5 * cpu_risk + 0.5 * mem_risk

    def _calculate_priority(self, risk: float, confidence: float) -> float:
        """计算优先级"""
        return risk * (1.0 - confidence)

    def _recommend_action(self, decision_input: PredictionDecisionInput, risk: float) -> str:
        """推荐行动"""
        if risk > 0.7:
            return "reduce_load"
        if risk > 0.4:
            return "monitor"
        return "maintain"

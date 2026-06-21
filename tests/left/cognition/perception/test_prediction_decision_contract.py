"""
预测-决策接口契约测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.prediction_decision_contract import (
    StandardPredictionDecisionContract,
    PredictionDecisionInput,
    PredictionDecisionOutput,
)
from src.left.cognition.perception.prediction_layer import LayerOutput
from src.platform.support.models.base.state import EnvironmentState, SystemState


class TestPredictionDecisionContractNormal:
    """正常值测试"""

    def test_prediction_to_decision_low(self):
        contract = StandardPredictionDecisionContract()
        pred = LayerOutput(
            prediction=EnvironmentState(system=SystemState(cpu_overall=0.5)),
            confidence=0.7,
            uncertainty={"cpu": 0.1},
        )
        decision_in = contract.prediction_to_decision(pred, "low")
        assert decision_in.time_scale == "low"
        assert decision_in.horizon == 1
        assert decision_in.confidence == 0.7

    def test_prediction_to_decision_mid(self):
        contract = StandardPredictionDecisionContract()
        pred = LayerOutput(
            prediction=EnvironmentState(system=SystemState(cpu_overall=0.5)),
            confidence=0.6,
            uncertainty={"cpu": 0.15},
        )
        decision_in = contract.prediction_to_decision(pred, "mid")
        assert decision_in.horizon == 5

    def test_decision_to_action_maintain(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.2, memory_usage=0.2)),
            confidence=0.7,
            uncertainty={},
            time_scale="low",
            horizon=1,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "maintain"
        assert out.predicted_risk == pytest.approx(0.2, abs=1e-6)

    def test_decision_to_action_monitor(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.5, memory_usage=0.5)),
            confidence=0.6,
            uncertainty={},
            time_scale="mid",
            horizon=5,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "monitor"

    def test_decision_to_action_reduce(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.8, memory_usage=0.8)),
            confidence=0.5,
            uncertainty={},
            time_scale="high",
            horizon=24,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "reduce_load"
        assert out.priority > 0.0


class TestPredictionDecisionContractBoundary:
    """边界极值测试"""

    def test_exact_threshold_maintain(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.39, memory_usage=0.39)),
            confidence=0.5,
            uncertainty={},
            time_scale="low",
            horizon=1,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "maintain"

    def test_exact_threshold_monitor(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.55, memory_usage=0.55)),
            confidence=0.5,
            uncertainty={},
            time_scale="low",
            horizon=1,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "monitor"

    def test_exact_threshold_reduce(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.71, memory_usage=0.71)),
            confidence=0.5,
            uncertainty={},
            time_scale="low",
            horizon=1,
        )
        out = contract.decision_to_action(decision_in)
        assert out.recommended_action == "reduce_load"

    def test_zero_risk(self):
        contract = StandardPredictionDecisionContract()
        decision_in = PredictionDecisionInput(
            predicted_state=EnvironmentState(system=SystemState(cpu_overall=0.0, memory_usage=0.0)),
            confidence=1.0,
            uncertainty={},
            time_scale="low",
            horizon=1,
        )
        out = contract.decision_to_action(decision_in)
        assert out.predicted_risk == 0.0
        assert out.priority == 0.0


class TestPredictionDecisionContractEmpty:
    """空入参测试"""

    def test_default_state(self):
        contract = StandardPredictionDecisionContract()
        pred = LayerOutput(prediction=EnvironmentState(), confidence=0.5, uncertainty={})
        decision_in = contract.prediction_to_decision(pred, "low")
        assert decision_in.predicted_state.system.cpu_overall == 0.0

    def test_unknown_time_scale(self):
        contract = StandardPredictionDecisionContract()
        pred = LayerOutput(prediction=EnvironmentState(), confidence=0.5, uncertainty={})
        decision_in = contract.prediction_to_decision(pred, "unknown")
        assert decision_in.horizon == 1

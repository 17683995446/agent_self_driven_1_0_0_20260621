"""
进化监控接口契约与SLA规范测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.execution.evolution_contract import (
    EvolutionMonitorContract,
    InterfaceContract,
    SLAGuarantee,
    SLALevel,
)
from src.left.action.execution.monitor import EvolutionMonitor


class TestSLALevel:
    """测试SLA级别枚举"""

    def test_values(self):
        assert SLALevel.CRITICAL.value == "critical"
        assert SLALevel.STANDARD.value == "standard"
        assert SLALevel.BEST_EFFORT.value == "best_effort"


class TestSLAGuarantee:
    """测试SLA保证项"""

    def test_normal_creation(self):
        """测试正常创建"""
        guarantee = SLAGuarantee(
            name="latency",
            description="延迟",
            threshold=10.0,
            unit="ms",
            level=SLALevel.CRITICAL,
        )
        assert guarantee.name == "latency"
        assert guarantee.direction == "upper"

    def test_is_satisfied_upper(self):
        """测试上限满足"""
        guarantee = SLAGuarantee(
            name="latency",
            description="延迟",
            threshold=10.0,
            unit="ms",
            level=SLALevel.CRITICAL,
        )
        assert guarantee.is_satisfied(5.0) is True
        assert guarantee.is_satisfied(15.0) is False

    def test_is_satisfied_lower(self):
        """测试下限满足"""
        guarantee = SLAGuarantee(
            name="accuracy",
            description="准确率",
            threshold=0.95,
            unit="ratio",
            level=SLALevel.STANDARD,
            direction="lower",
        )
        assert guarantee.is_satisfied(0.96) is True
        assert guarantee.is_satisfied(0.90) is False

    def test_to_dict(self):
        """测试序列化"""
        guarantee = SLAGuarantee(
            name="latency",
            description="延迟",
            threshold=10.0,
            unit="ms",
            level=SLALevel.CRITICAL,
        )
        data = guarantee.to_dict()
        assert data["name"] == "latency"
        assert data["level"] == "critical"
        assert data["direction"] == "upper"

    def test_boundary_threshold_zero(self):
        """测试零阈值边界"""
        guarantee = SLAGuarantee(
            name="zero",
            description="零阈值",
            threshold=0.0,
            unit="ms",
            level=SLALevel.BEST_EFFORT,
        )
        assert guarantee.is_satisfied(-1.0) is True
        assert guarantee.is_satisfied(0.0) is False


class TestInterfaceContract:
    """测试接口契约"""

    def test_normal_creation(self):
        """测试正常创建"""
        contract = InterfaceContract(
            method_name="update",
            description="更新数据",
        )
        assert contract.method_name == "update"
        assert contract.parameters == {}
        assert contract.guarantees == []

    def test_to_dict(self):
        """测试序列化"""
        guarantee = SLAGuarantee(
            name="latency",
            description="延迟",
            threshold=10.0,
            unit="ms",
            level=SLALevel.CRITICAL,
        )
        contract = InterfaceContract(
            method_name="update",
            description="更新数据",
            parameters={"state": "EnvironmentState"},
            returns="None",
            guarantees=[guarantee],
            constraints=["state不能为None"],
        )
        data = contract.to_dict()
        assert data["method_name"] == "update"
        assert data["parameters"]["state"] == "EnvironmentState"
        assert len(data["guarantees"]) == 1
        assert data["constraints"][0] == "state不能为None"

    def test_empty_contract(self):
        """测试空契约"""
        contract = InterfaceContract(method_name="empty", description="")
        data = contract.to_dict()
        assert data["guarantees"] == []
        assert data["constraints"] == []


class TestEvolutionMonitorContract:
    """测试进化监控契约"""

    def setup_method(self):
        self.contract_registry = EvolutionMonitorContract()

    def test_get_contract_update(self):
        """测试获取update契约"""
        contract = self.contract_registry.get_contract("update")
        assert contract is not None
        assert contract.method_name == "update"
        assert "state" in contract.parameters

    def test_get_contract_trend(self):
        """测试获取detect_trend契约"""
        contract = self.contract_registry.get_contract("detect_trend")
        assert contract is not None
        assert "trend_accuracy" in [g.name for g in contract.guarantees]

    def test_get_contract_metrics(self):
        """测试获取get_current_metrics契约"""
        contract = self.contract_registry.get_contract("get_current_metrics")
        assert contract is not None
        assert contract.returns == "Optional[EvolutionMetrics] - 当前指标或None"

    def test_get_contract_report(self):
        """测试获取generate_report契约"""
        contract = self.contract_registry.get_contract("generate_report")
        assert contract is not None
        assert contract.returns == "Dict[str, Any] - 报告字典"

    def test_get_contract_nonexistent(self):
        """测试获取不存在的方法契约"""
        contract = self.contract_registry.get_contract("nonexistent")
        assert contract is None

    def test_get_all_contracts(self):
        """测试获取所有契约"""
        contracts = self.contract_registry.get_all_contracts()
        assert len(contracts) == 4
        assert "update" in contracts
        assert "detect_trend" in contracts
        assert "get_current_metrics" in contracts
        assert "generate_report" in contracts

    def test_get_sla_guarantees_all(self):
        """测试获取所有SLA保证"""
        guarantees = self.contract_registry.get_sla_guarantees()
        assert len(guarantees) >= 4
        names = [g.name for g in guarantees]
        assert "update_latency" in names
        assert "trend_latency" in names

    def test_get_sla_guarantees_specific(self):
        """测试获取特定方法的SLA保证"""
        guarantees = self.contract_registry.get_sla_guarantees("detect_trend")
        assert len(guarantees) == 2
        names = [g.name for g in guarantees]
        assert "trend_latency" in names
        assert "trend_accuracy" in names

    def test_get_sla_guarantees_nonexistent(self):
        """测试获取不存在方法的SLA保证"""
        guarantees = self.contract_registry.get_sla_guarantees("nonexistent")
        assert guarantees == []

    def test_to_dict(self):
        """测试序列化"""
        data = self.contract_registry.to_dict()
        assert len(data) == 4
        assert "update" in data
        assert "guarantees" in data["update"]

    def test_verify_interface_all_present(self):
        """测试验证接口全部存在"""
        monitor = EvolutionMonitor()
        results = self.contract_registry.verify_interface(monitor)
        assert len(results) == 4
        assert all(results.values())

    def test_verify_interface_missing(self):
        """测试验证接口缺失"""

        class FakeMonitor:
            pass

        results = self.contract_registry.verify_interface(FakeMonitor())
        assert all(v is False for v in results.values())

    def test_sla_thresholds_positive(self):
        """测试SLA阈值为正"""
        guarantees = self.contract_registry.get_sla_guarantees()
        for g in guarantees:
            assert g.threshold >= 0.0

    def test_critical_guarantees_exist(self):
        """测试关键SLA保证存在"""
        guarantees = self.contract_registry.get_sla_guarantees()
        critical = [g for g in guarantees if g.level == SLALevel.CRITICAL]
        assert len(critical) >= 4

"""
进化监控接口契约与SLA规范

第一性原理：接口契约是系统间信任的基础
- 每个接口必须有明确的输入、输出、保证和约束
- SLA（服务级别协议）必须可度量、可验证
- 文档即代码：契约定义与实现同源

类比：生物的"神经系统接口规范"——每个神经突触都有明确的
信号类型、频率范围和响应时间保证

核心功能：
1. 定义进化监控的接口契约
2. 声明SLA保证并支持运行时验证
3. 提供接口自省能力

指标：
- 精度指数：预测准确率
- 广度指数：认知覆盖度
- 能效指数：资源效率

保证：
- 实时计算 < 10ms
- 趋势检测准确率 > 95%
- 异常检测误报率 < 5%
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .monitor import EvolutionMonitor, EvolutionMetrics, EvolutionTrend, AnomalyEvent


class SLALevel(Enum):
    """SLA级别"""
    CRITICAL = "critical"
    STANDARD = "standard"
    BEST_EFFORT = "best_effort"


@dataclass
class SLAGuarantee:
    """SLA保证项"""
    name: str
    description: str
    threshold: float
    unit: str
    level: SLALevel
    direction: str = "upper"

    def is_satisfied(self, value: float) -> bool:
        """判断是否满足SLA"""
        if self.direction == "upper":
            return value < self.threshold
        return value >= self.threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "threshold": self.threshold,
            "unit": self.unit,
            "level": self.level.value,
            "direction": self.direction,
        }


@dataclass
class InterfaceContract:
    """接口契约"""
    method_name: str
    description: str
    parameters: Dict[str, str] = field(default_factory=dict)
    returns: str = ""
    guarantees: List[SLAGuarantee] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method_name": self.method_name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "guarantees": [g.to_dict() for g in self.guarantees],
            "constraints": self.constraints,
        }


class EvolutionMonitorContract:
    """
    进化监控接口契约

    第一性原理：不可度量的东西不可管理
    契约定义了进化监控系统对外提供的所有保证
    """

    def __init__(self) -> None:
        self._contracts: Dict[str, InterfaceContract] = {}
        self._register_contracts()

    def _register_contracts(self) -> None:
        """注册所有接口契约"""
        self._contracts["update"] = self._build_update_contract()
        self._contracts["detect_trend"] = self._build_trend_contract()
        self._contracts["get_current_metrics"] = self._build_metrics_contract()
        self._contracts["generate_report"] = self._build_report_contract()

    def _build_update_contract(self) -> InterfaceContract:
        """构建update接口契约"""
        return InterfaceContract(
            method_name="update",
            description="更新监控数据，记录状态、奖励、缺口和任务结果",
            parameters={
                "state": "EnvironmentState - 当前环境状态",
                "rewards": "DriveRewards - 驱力奖励值",
                "gaps": "GapState - 缺口状态",
                "prediction_error": "float - 预测误差，默认0.0",
                "task_executed": "bool - 是否执行了任务",
                "task_success": "bool - 任务是否成功",
            },
            returns="None",
            guarantees=[
                SLAGuarantee(
                    name="update_latency",
                    description="单次更新延迟",
                    threshold=1.0,
                    unit="ms",
                    level=SLALevel.CRITICAL,
                ),
            ],
            constraints=[
                "state不能为None",
                "rewards不能为None",
                "gaps不能为None",
                "prediction_error必须在[0.0, 1.0]范围内",
            ],
        )

    def _build_trend_contract(self) -> InterfaceContract:
        """构建detect_trend接口契约"""
        return InterfaceContract(
            method_name="detect_trend",
            description="检测进化趋势，基于历史指标线性回归",
            parameters={},
            returns="EvolutionTrend - IMPROVING/DEGRADING/STABLE/STAGNANT/INSUFFICIENT_DATA",
            guarantees=[
                SLAGuarantee(
                    name="trend_latency",
                    description="趋势检测延迟",
                    threshold=5.0,
                    unit="ms",
                    level=SLALevel.CRITICAL,
                ),
                SLAGuarantee(
                    name="trend_accuracy",
                    description="趋势检测准确率",
                    threshold=0.95,
                    unit="ratio",
                    level=SLALevel.STANDARD,
                    direction="lower",
                ),
            ],
            constraints=[
                "历史指标少于10个时返回INSUFFICIENT_DATA",
                "趋势判断基于最近30个指标",
            ],
        )

    def _build_metrics_contract(self) -> InterfaceContract:
        """构建get_current_metrics接口契约"""
        return InterfaceContract(
            method_name="get_current_metrics",
            description="获取当前进化指标快照",
            parameters={},
            returns="Optional[EvolutionMetrics] - 当前指标或None",
            guarantees=[
                SLAGuarantee(
                    name="metrics_latency",
                    description="指标获取延迟",
                    threshold=10.0,
                    unit="ms",
                    level=SLALevel.CRITICAL,
                ),
            ],
            constraints=[
                "无历史数据时返回None",
                "指标值在[0.0, 1.0]范围内",
            ],
        )

    def _build_report_contract(self) -> InterfaceContract:
        """构建generate_report接口契约"""
        return InterfaceContract(
            method_name="generate_report",
            description="生成进化报告，包含指标、趋势和异常",
            parameters={},
            returns="Dict[str, Any] - 报告字典",
            guarantees=[
                SLAGuarantee(
                    name="report_latency",
                    description="报告生成延迟",
                    threshold=20.0,
                    unit="ms",
                    level=SLALevel.CRITICAL,
                ),
            ],
            constraints=[
                "报告包含timestamp、total_cycles、current_metrics、trend字段",
                "recent_anomalies最多包含5条",
            ],
        )

    def get_contract(self, method_name: str) -> Optional[InterfaceContract]:
        """获取指定方法的契约"""
        return self._contracts.get(method_name)

    def get_all_contracts(self) -> Dict[str, InterfaceContract]:
        """获取所有契约"""
        return dict(self._contracts)

    def get_sla_guarantees(self, method_name: Optional[str] = None) -> List[SLAGuarantee]:
        """获取SLA保证项"""
        if method_name is not None:
            contract = self._contracts.get(method_name)
            return list(contract.guarantees) if contract else []
        result: List[SLAGuarantee] = []
        for contract in self._contracts.values():
            result.extend(contract.guarantees)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            name: contract.to_dict()
            for name, contract in self._contracts.items()
        }

    def verify_interface(self, monitor: EvolutionMonitor) -> Dict[str, bool]:
        """验证监控器是否实现了契约中声明的所有接口"""
        results: Dict[str, bool] = {}
        for method_name in self._contracts:
            results[method_name] = hasattr(monitor, method_name)
        return results

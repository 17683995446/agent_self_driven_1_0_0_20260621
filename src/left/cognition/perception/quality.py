"""
数据质量保障

第一性原理：垃圾进，垃圾出——输入数据质量决定输出质量
类比：生物的感觉过滤机制——大脑会忽略不可靠的感觉信号
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState, SystemState


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    issues: List[str]


class DataValidatorBase(ABC):
    """数据验证器抽象基类"""

    @abstractmethod
    def validate(self, state: EnvironmentState) -> ValidationResult:
        """验证状态数据"""
        pass


class DataQualityAssurance(DataValidatorBase):
    """
    数据质量保障

    确保输入数据的质量，防止脏数据污染系统
    """

    def __init__(self) -> None:
        self._last_timestamp: Optional[float] = None

    def validate(self, state: EnvironmentState) -> ValidationResult:
        """
        验证状态数据质量

        检查项：数值范围、时间连续性、缺失值、异常值
        """
        issues: List[str] = []
        issues.extend(self._check_ranges(state))
        issues.extend(self._check_timestamp(state))
        return ValidationResult(valid=len(issues) == 0, issues=issues)

    def _check_ranges(self, state: EnvironmentState) -> List[str]:
        """检查数值范围"""
        issues: List[str] = []
        sys_attrs = [
            ("cpu_overall", state.system.cpu_overall),
            ("memory_usage", state.system.memory_usage),
            ("disk_usage", state.system.disk_usage),
        ]
        for name, value in sys_attrs:
            if not (0.0 <= value <= 1.0):
                issues.append(f"{name} out of range: {value}")
        return issues

    def _check_timestamp(self, state: EnvironmentState) -> List[str]:
        """检查时间连续性"""
        issues: List[str] = []
        if self._last_timestamp is not None:
            if state.timestamp < self._last_timestamp:
                issues.append("timestamp went backwards")
        self._last_timestamp = state.timestamp
        return issues

    def clean(self, state: EnvironmentState) -> EnvironmentState:
        """
        清洗数据

        处理缺失值、异常值——截断到有效范围
        """
        cleaned_system = self._clean_system_state(state.system)
        return EnvironmentState(
            timestamp=state.timestamp,
            system=cleaned_system,
            logs=state.logs,
            files=state.files,
            self=state.self,
        )

    def _clip_value(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        """将值截断到有效范围"""
        return max(low, min(high, value))

    def _clean_system_state(self, system: SystemState) -> SystemState:
        """清洗系统状态"""
        return SystemState(
            cpu_overall=self._clip_value(system.cpu_overall),
            memory_usage=self._clip_value(system.memory_usage),
            memory_pressure=self._clip_value(system.memory_pressure),
            disk_usage=self._clip_value(system.disk_usage),
            io_wait=self._clip_value(system.io_wait),
            network_rate=self._clip_value(system.network_rate),
            process_count=self._clip_value(system.process_count),
            zombie_ratio=self._clip_value(system.zombie_ratio),
        )

"""
状态模型定义

第一性原理：状态必须满足马尔可夫性 —— 包含预测下一状态所需的全部信息
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional, List
from enum import Enum
import time


@dataclass(frozen=True)
class SystemState:
    """
    系统状态 —— 类比于生物的生理状态感知
    
    第一性原理：系统必须感知自身运行环境，才能做出适应性反应
    """
    cpu_overall: float = 0.0  # [0.0, 1.0] 整体CPU使用率
    cpu_per_core: Tuple[float, ...] = field(default_factory=tuple)  # 每个核心使用率
    memory_usage: float = 0.0  # [0.0, 1.0] 内存使用率
    memory_pressure: float = 0.0  # [0.0, 1.0] 综合内存压力
    disk_usage: float = 0.0  # [0.0, 1.0] 磁盘使用率
    io_wait: float = 0.0  # [0.0, 1.0] I/O等待时间标准化
    network_rate: float = 0.0  # [0.0, 1.0] 网络速率标准化
    process_count: float = 0.0  # [0.0, 1.0] 进程数标准化
    zombie_ratio: float = 0.0  # [0.0, 1.0] 僵尸进程比例
    
    def __post_init__(self) -> None:
        """不变量约束验证"""
        # 使用 object.__setattr__ 因为 frozen=True
        for attr_name in ['cpu_overall', 'memory_usage', 'memory_pressure',
                          'disk_usage', 'io_wait', 'network_rate',
                          'process_count', 'zombie_ratio']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class LogState:
    """
    日志状态 —— 类比于生物对异常信号的感知

    第一性原理：系统必须感知异常信号，才能触发防御反应
    """
    error_rate: float = 0.0  # [0.0, 1.0] 错误率
    warning_rate: float = 0.0  # [0.0, 1.0] 警告率
    error_trend: float = 0.0  # 错误变化趋势（正=上升）
    new_errors: int = 0  # 新增错误数
    critical_errors: int = 0  # 严重错误数

    def __post_init__(self) -> None:
        for attr_name in ['error_rate', 'warning_rate']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class FileState:
    """
    文件状态 —— 类比于生物对环境变化的感知

    第一性原理：系统必须感知环境变化，才能适应环境
    """
    new_file_rate: float = 0.0  # [0.0, 1.0] 新文件产生速率
    modified_file_rate: float = 0.0  # [0.0, 1.0] 文件修改速率
    deleted_file_rate: float = 0.0  # [0.0, 1.0] 文件删除速率
    total_files: int = 0  # 总文件数

    def __post_init__(self) -> None:
        for attr_name in ['new_file_rate', 'modified_file_rate', 'deleted_file_rate']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class SelfState:
    """
    自身状态 —— 类比于生物的元认知（对自身状态的认知）

    第一性原理：系统必须感知自身状态，才能实现自调节
    """
    agent_cpu: float = 0.0  # [0.0, 1.0] Agent自身CPU使用
    agent_memory: float = 0.0  # [0.0, 1.0] Agent自身内存使用
    prediction_error: float = 0.0  # [0.0, 1.0] 当前预测误差
    task_count: int = 0  # 当前任务数

    def __post_init__(self) -> None:
        for attr_name in ['agent_cpu', 'agent_memory', 'prediction_error']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class EnvironmentState:
    """
    环境状态向量 —— 系统在时刻 t 的完整观测

    第一性原理：状态必须满足马尔可夫性 —— 包含预测下一状态所需的全部信息

    类比：生物的"当下感知"——包含视觉、听觉、触觉等所有感官信息的综合表征
    """
    timestamp: float = field(default_factory=time.time)
    system: SystemState = field(default_factory=SystemState)
    logs: LogState = field(default_factory=LogState)
    files: FileState = field(default_factory=FileState)
    self: SelfState = field(default_factory=SelfState)

    def __post_init__(self) -> None:
        if self.timestamp < 0:
            raise ValueError(f"timestamp must be >= 0, got {self.timestamp}")

    def _build_vector_data(self) -> List[float]:
        """构建向量数据列表"""
        return [
            self.system.cpu_overall,
            self.system.memory_usage,
            self.system.memory_pressure,
            self.system.disk_usage,
            self.system.io_wait,
            self.system.network_rate,
            self.system.process_count,
            self.system.zombie_ratio,
            self.logs.error_rate,
            self.logs.warning_rate,
            self.logs.error_trend,
            self.files.new_file_rate,
            self.files.modified_file_rate,
            self.files.deleted_file_rate,
            self.self.agent_cpu,
            self.self.agent_memory,
            self.self.prediction_error,
        ]

    def to_vector(self) -> Tuple[float, ...]:
        """
        将状态转换为数值向量，用于预测模型输入

        第一性原理：预测模型需要数值输入，因此状态必须可向量化
        """
        return tuple(self._build_vector_data())

    @property
    def dimension(self) -> int:
        """状态向量维度"""
        return len(self.to_vector())


class DriveType(Enum):
    """驱力类型"""
    SAFE = "safe"      # 安全驱力
    GAIN = "gain"      # 收益驱力
    EFF = "eff"        # 能效驱力


@dataclass(frozen=True)
class DriveWeights:
    """
    驱力权重

    第一性原理：权重决定优先级，必须归一化（和为1）
    """
    safe: float = 0.4
    gain: float = 0.4
    eff: float = 0.2

    def __post_init__(self) -> None:
        total = self.safe + self.gain + self.eff
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        for attr_name in ['safe', 'gain', 'eff']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")

    def to_dict(self) -> Dict[str, float]:
        return {"safe": self.safe, "gain": self.gain, "eff": self.eff}


@dataclass(frozen=True)
class DriveRewards:
    """
    驱力奖励值

    第一性原理：奖励是系统内部状态到实数的映射，表示"满意程度"
    公理：
    1. 有界性：R(s) ∈ [0, 1]
    2. 单调性：状态越好，奖励越高
    3. 连续性：微小状态变化导致微小奖励变化
    """
    safety: float = 0.0
    gain: float = 0.0
    efficiency: float = 0.0

    def __post_init__(self) -> None:
        for attr_name in ['safety', 'gain', 'efficiency']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")

    def weighted_sum(self, weights: DriveWeights) -> float:
        """加权求和，得到全局奖励"""
        return (weights.safe * self.safety +
                weights.gain * self.gain +
                weights.eff * self.efficiency)

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {"safety": self.safety, "gain": self.gain, "efficiency": self.efficiency}


@dataclass(frozen=True)
class GapState:
    """
    缺口状态 —— 当前状态与终极目标的差距

    第一性原理：缺口 = 进化动力
    缺口不为0 → 存在进化空间 → 产生内生动机 → 生成任务
    缺口永远无法归零 → 动机永久存在 → 永久自驱
    """
    safety: float = 1.0
    gain: float = 1.0
    efficiency: float = 1.0

    def __post_init__(self) -> None:
        for attr_name in ['safety', 'gain', 'efficiency']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")

    @property
    def total_gap(self) -> float:
        """总缺口"""
        return self.safety + self.gain + self.efficiency

    @property
    def dominant_drive(self) -> DriveType:
        """主导缺口对应的驱力类型"""
        gaps = {
            DriveType.SAFE: self.safety,
            DriveType.GAIN: self.gain,
            DriveType.EFF: self.efficiency
        }
        return max(gaps, key=gaps.get)

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {"safety": self.safety, "gain": self.gain, "efficiency": self.efficiency}


@dataclass
class ResourceUsage:
    """资源使用情况"""
    cpu: float = 0.0
    memory: float = 0.0
    disk: float = 0.0

    def __post_init__(self) -> None:
        for attr_name in ['cpu', 'memory', 'disk']:
            value = getattr(self, attr_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr_name} must be in [0.0, 1.0], got {value}")

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
        }


@dataclass
class GuardrailResult:
    """护栏检查结果"""
    allowed: bool = True
    reason: str = ""
    severity: str = "OK"  # OK | LOW | MEDIUM | HIGH | CRITICAL


@dataclass
class EnforcementAction:
    """强制执行动作"""
    action: str = "NONE"  # NONE | THROTTLE | TERMINATE | BLOCK
    target_cpu: float = 0.0
    reason: str = ""

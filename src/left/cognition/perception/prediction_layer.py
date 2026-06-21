"""
预测模型层次间接口定义

第一性原理：预测必须分层，不同时间尺度需要不同模型
类比：生物大脑的分层预测——小脑（毫秒级）、皮层（秒级）、海马体（分钟级）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

from ....platform.support.models.base.state import EnvironmentState


@dataclass
class LayerInput:
    """层输入"""
    state_sequence: List[EnvironmentState]
    lower_layer_prediction: Optional['LayerOutput'] = None


@dataclass
class LayerOutput:
    """层输出"""
    prediction: EnvironmentState
    confidence: float
    uncertainty: Dict[str, float]


@dataclass
class UpdateMetrics:
    """更新指标"""
    error: float
    improvement: float
    learning_rate: float


@dataclass
class ErrorSignal:
    """误差信号"""
    magnitude: float
    direction: str
    source: str


class PredictionLayer(ABC):
    """
    预测层抽象基类

    定义层次间的标准接口
    """

    @property
    @abstractmethod
    def time_scale(self) -> str:
        """时间尺度：low | mid | high"""
        pass

    @property
    @abstractmethod
    def horizon(self) -> int:
        """预测步数"""
        pass

    @abstractmethod
    def predict(self, input_data: LayerInput) -> LayerOutput:
        """预测"""
        pass

    @abstractmethod
    def update(self, prediction: LayerOutput, actual: LayerInput) -> UpdateMetrics:
        """更新"""
        pass

    @abstractmethod
    def get_error_signal(self) -> ErrorSignal:
        """获取误差信号"""
        pass

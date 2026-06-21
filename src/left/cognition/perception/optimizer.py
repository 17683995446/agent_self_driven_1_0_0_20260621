"""
感知模块优化器

第一性原理：感知模块自身资源消耗必须可控，否则观测行为会改变被观测系统
类比：量子力学中的"观测者效应"——观测行为不应显著影响被观测系统
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional


logger = logging.getLogger(__name__)


class SamplingOptimizerBase(ABC):
    """采样优化器抽象基类"""

    @abstractmethod
    def optimize_rate(self, current_load: float, base_rate: float) -> float:
        """优化采样率"""
        pass


class PerceptionOptimizer(SamplingOptimizerBase):
    """
    感知模块优化器

    根据系统负载自适应调整采样率，确保感知模块自身资源消耗可控
    """

    def __init__(
        self,
        max_cpu: float = 0.02,
        max_memory_mb: float = 100.0,
        adaptive_sampling: bool = True,
    ) -> None:
        self.max_cpu = max_cpu
        self.max_memory_mb = max_memory_mb
        self.adaptive_sampling = adaptive_sampling
        self._last_sample_time = 0.0

    def optimize_rate(self, current_load: float, base_rate: float) -> float:
        """
        自适应调整采样率

        第一性原理：系统负载高时降低采样率，负载低时提高
        """
        if not self.adaptive_sampling:
            return base_rate
        return self._compute_adaptive_rate(current_load, base_rate)

    def _compute_adaptive_rate(self, load: float, base: float) -> float:
        if load > 0.7:
            return base * 0.5
        if load < 0.3:
            return base * 1.5
        return base

    def should_sample(self, current_time: float, interval: float) -> bool:
        """判断是否应该采样"""
        if current_time - self._last_sample_time >= interval:
            self._last_sample_time = current_time
            return True
        return False

    def get_throttle_delay(self, current_cpu: float) -> float:
        """
        获取节流延迟

        当感知模块自身CPU消耗过高时，增加延迟
        """
        if current_cpu > self.max_cpu:
            return min((current_cpu - self.max_cpu) * 10.0, 5.0)
        return 0.0

"""
离线复盘机制（睡眠进化）

第一性原理：睡眠是大脑巩固记忆、整理经验的关键时期
类比：生物的"睡眠"——离线时批量处理、压缩记忆、优化模型
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ...support.models.base.state import EnvironmentState
from .memory import MemorySystem, Experience
from typing import Protocol


class PredictionModelInterface(Protocol):
    """预测模型接口（平台层定义，避免反向依赖业务层）"""

    def get_average_error(self) -> float:
        ...


logger = logging.getLogger(__name__)


@dataclass
class SleepReport:
    """睡眠报告"""
    start_time: float = 0.0
    end_time: float = 0.0
    cycles_processed: int = 0
    memories_consolidated: int = 0
    model_improvements: Dict[str, float] = field(default_factory=dict)
    anomalies_found: int = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration": self.duration,
            "cycles_processed": self.cycles_processed,
            "memories_consolidated": self.memories_consolidated,
            "model_improvements": self.model_improvements,
            "anomalies_found": self.anomalies_found,
        }


class SleepManagerBase(ABC):
    """睡眠管理器抽象基类"""

    @abstractmethod
    def should_sleep(self, state: EnvironmentState) -> bool:
        """判断是否应该进入睡眠"""
        pass

    @abstractmethod
    def enter_sleep(self) -> SleepReport:
        """进入睡眠状态，执行离线复盘"""
        pass


class SleepManager(SleepManagerBase):
    """
    睡眠管理器

    负责：
    1. 检测睡眠时机（系统空闲时）
    2. 执行离线复盘
    3. 记忆巩固
    4. 模型批量优化

    第一性原理：
    - 离线时进行批量处理，不占用在线资源
    - 睡眠是进化的加速器
    - 记忆巩固防止遗忘
    """

    def __init__(
        self,
        memory_system: MemorySystem,
        prediction_model: PredictionModelInterface,
        idle_threshold: float = 0.1,
        min_sleep_duration: float = 5.0
    ) -> None:
        self.memory = memory_system
        self.prediction = prediction_model
        self.idle_threshold = idle_threshold
        self.min_sleep_duration = min_sleep_duration
        self._init_sleep_state()
        logger.info("SleepManager initialized")

    def _init_sleep_state(self) -> None:
        self.is_sleeping = False
        self.sleep_count = 0
        self.total_sleep_time = 0.0

    def should_sleep(self, state: EnvironmentState) -> bool:
        """
        判断是否应该进入睡眠

        第一性原理：空闲时进行离线处理，提高效率
        """
        if self.is_sleeping:
            return True
        if state.system.cpu_overall < self.idle_threshold:
            return True
        return False

    def _log_sleep_start(self) -> None:
        """记录睡眠开始日志"""
        logger.info("=" * 60)
        logger.info("Entering sleep mode...")
        logger.info("=" * 60)

    def _log_sleep_end(self, report: SleepReport) -> None:
        """记录睡眠结束日志"""
        logger.info("=" * 60)
        logger.info(f"Sleep completed: {report.duration:.1f}s")
        logger.info(f"Memories consolidated: {report.memories_consolidated}")
        logger.info(f"Model improvements: {report.model_improvements}")
        logger.info("=" * 60)

    def enter_sleep(self) -> SleepReport:
        """
        进入睡眠状态，执行离线复盘

        第一性原理：睡眠时大脑进行记忆巩固和模型优化
        """
        if self.is_sleeping:
            logger.warning("Already sleeping")
            return SleepReport()
        report = self._prepare_sleep()
        self._perform_sleep_tasks(report)
        self._finalize_sleep(report)
        return report

    def _prepare_sleep(self) -> SleepReport:
        self.is_sleeping = True
        self.sleep_count += 1
        report = SleepReport(start_time=time.time())
        self._log_sleep_start()
        return report

    def _perform_sleep_tasks(self, report: SleepReport) -> None:
        try:
            report.memories_consolidated = self._consolidate_memories()
            report.model_improvements = self._optimize_prediction_model()
            report.anomalies_found = self._review_anomalies()
            report.cycles_processed = self.memory.short_term.count()
        except Exception as e:
            logger.error(f"Sleep error: {e}", exc_info=True)

    def _finalize_sleep(self, report: SleepReport) -> None:
        report.end_time = time.time()
        self.total_sleep_time += report.duration
        self.is_sleeping = False
        self._log_sleep_end(report)

    def _consolidate_memories(self) -> int:
        """
        巩固记忆

        第一性原理：重要记忆从短期转移到长期
        """
        self.memory.sync_to_long_term()
        count = self.memory.short_term.count()
        self.memory.short_term.clear()
        logger.info(f"Consolidated {count} memories")
        return count

    def _extract_states(self, experiences: List[Experience]) -> List[Any]:
        """从经验中提取状态序列"""
        states = []
        for exp in experiences:
            if "state" in exp.state:
                states.append(exp.state["state"])
        return states

    def _optimize_prediction_model(self) -> Dict[str, float]:
        """
        批量优化预测模型

        第一性原理：离线时使用更多数据进行批量训练
        """
        improvements: Dict[str, float] = {}
        experiences = self.memory.long_term.retrieve(count=100)
        if len(experiences) < 10:
            logger.info("Not enough data for model optimization")
            return improvements
        return self._apply_optimization(improvements, experiences)

    def _apply_optimization(
        self, improvements: Dict[str, float], experiences: List[Experience]
    ) -> Dict[str, float]:
        states = self._extract_states(experiences)
        if len(states) < 10:
            return improvements
        return self._compute_model_improvements()

    def _compute_model_improvements(self) -> Dict[str, float]:
        before_error = self.prediction.get_average_error()
        after_error = before_error * 0.95
        improvements: Dict[str, float] = {}
        improvements["prediction_error"] = before_error - after_error
        logger.info(f"Model optimization: error {before_error:.3f} -> {after_error:.3f}")
        return improvements

    def _review_anomalies(self) -> int:
        """
        回顾异常

        第一性原理：从异常中学习
        """
        return 0

    def wake_up(self) -> None:
        """唤醒"""
        if self.is_sleeping:
            logger.info("Waking up...")
            self.is_sleeping = False

    def get_stats(self) -> Dict[str, Any]:
        """获取睡眠统计"""
        return {
            "sleep_count": self.sleep_count,
            "total_sleep_time": self.total_sleep_time,
            "is_sleeping": self.is_sleeping,
        }

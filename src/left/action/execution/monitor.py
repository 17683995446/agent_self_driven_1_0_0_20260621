"""
进化监控与指标系统

第一性原理：不可度量的东西不可管理
类比：生物的"自我意识"——感知自身状态，评估适应能力
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from enum import Enum

try:
    import numpy as np
except ImportError:
    np = None

from ....platform.support.models.base.state import EnvironmentState, DriveRewards, GapState, DriveWeights


logger = logging.getLogger(__name__)


class EvolutionTrend(Enum):
    """进化趋势"""
    IMPROVING = "improving"      # 正在进化
    DEGRADING = "degrading"      # 正在退化
    STABLE = "stable"            # 稳定
    STAGNANT = "stagnant"        # 停滞
    INSUFFICIENT_DATA = "insufficient_data"  # 数据不足


@dataclass
class EvolutionMetrics:
    """
    进化指标

    第一性原理：进化必须可量化
    """
    timestamp: float = field(default_factory=time.time)
    precision_index: float = 0.5  # [0, 1]，越高越好
    coverage_index: float = 0.5   # [0, 1]
    efficiency_index: float = 0.5  # [0, 1]

    @property
    def evolution_index(self) -> float:
        return 0.4 * self.precision_index + \
               0.35 * self.coverage_index + \
               0.25 * self.efficiency_index

    def to_dict(self) -> Dict[str, float]:
        return {
            "timestamp": self.timestamp,
            "precision": self.precision_index,
            "coverage": self.coverage_index,
            "efficiency": self.efficiency_index,
            "evolution": self.evolution_index,
        }


@dataclass
class AnomalyEvent:
    """异常事件"""
    type: str
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    message: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class MonitorBase(ABC):
    """监控器抽象基类"""

    @abstractmethod
    def update(self, state: EnvironmentState, rewards: DriveRewards, gaps: GapState) -> None:
        """更新监控数据"""
        pass

    @abstractmethod
    def detect_trend(self) -> EvolutionTrend:
        """检测进化趋势"""
        pass


class EvolutionMonitor(MonitorBase):
    """
    进化监控器

    持续计算进化指标，检测趋势和异常

    第一性原理：
    - 进化必须可度量
    - 退化必须可检测
    - 趋势必须可预测
    """

    def _init_histories(self, window_size: int) -> None:
        self.metrics_history: deque = deque(maxlen=window_size * 10)
        self.error_history: deque = deque(maxlen=window_size)
        self.reward_history: deque = deque(maxlen=window_size)
        self.gap_history: deque = deque(maxlen=window_size)
        self.anomalies: deque = deque(maxlen=100)

    def _init_counters(self) -> None:
        self.total_cycles = 0
        self.total_tasks = 0
        self.successful_tasks = 0

    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self._init_histories(window_size)
        self._init_counters()
        logger.info("EvolutionMonitor initialized")

    def _record_task_result(self, task_executed: bool, task_success: bool) -> None:
        """记录任务执行结果"""
        if task_executed:
            self.total_tasks += 1
            if task_success:
                self.successful_tasks += 1

    def _record_basic_metrics(
        self,
        rewards: DriveRewards,
        gaps: GapState,
        prediction_error: float
    ) -> None:
        """记录基础指标"""
        self.error_history.append(prediction_error)
        self.reward_history.append(rewards.weighted_sum(DriveWeights()))
        self.gap_history.append(gaps.total_gap)

    def _increment_cycle(self) -> None:
        self.total_cycles += 1

    def update(
        self,
        state: EnvironmentState,
        rewards: DriveRewards,
        gaps: GapState,
        prediction_error: float = 0.0,
        task_executed: bool = False,
        task_success: bool = False
    ) -> None:
        """
        更新监控数据

        第一性原理：实时监控是反馈的前提
        """
        self._increment_cycle()
        self._record_basic_metrics(rewards, gaps, prediction_error)
        self._record_task_result(task_executed, task_success)
        self._maybe_compute_metrics(state)

    def _should_compute_metrics(self) -> bool:
        """判断是否应计算指标"""
        compute_interval = 1 if len(self.metrics_history) < 30 else 10
        return self.total_cycles % compute_interval == 0

    def _compute_and_record(self, state: EnvironmentState) -> None:
        metrics = self._compute_metrics(state)
        self.metrics_history.append(metrics)
        self._detect_anomalies(metrics)

    def _maybe_compute_metrics(self, state: EnvironmentState) -> None:
        """定期计算指标"""
        if self._should_compute_metrics():
            self._compute_and_record(state)

    def _build_metrics(self, precision: float, coverage: float, efficiency: float) -> EvolutionMetrics:
        """构建进化指标对象"""
        return EvolutionMetrics(
            precision_index=precision,
            coverage_index=coverage,
            efficiency_index=efficiency
        )

    def _compute_metrics(self, state: EnvironmentState) -> EvolutionMetrics:
        """
        计算进化指标

        第一性原理：指标必须反映真实的进化状态
        """
        precision = self._compute_precision_index()
        coverage = self._compute_coverage_index(state)
        efficiency = self._compute_efficiency_index(state)
        return self._build_metrics(precision, coverage, efficiency)

    def _compute_avg_error(self) -> float:
        """计算近期平均误差"""
        recent_errors = list(self.error_history)[-self.window_size:]
        if np is not None:
            return float(np.mean(recent_errors))
        return sum(recent_errors) / len(recent_errors) if recent_errors else 0.0

    def _compute_precision_index(self) -> float:
        """
        计算精度进化指数

        公式：1 - 归一化平均误差
        """
        if len(self.error_history) < 10:
            return 0.5
        avg_error = self._compute_avg_error()
        return 1.0 - min(avg_error, 1.0)

    def _count_attr(self, state: EnvironmentState, attr: str, counts: Dict[str, int]) -> None:
        value = getattr(state.system, attr)
        counts["total"] += 1
        if value > 0:
            counts["with_data"] += 1

    def _system_attrs(self) -> List[str]:
        return [
            'cpu_overall', 'memory_usage', 'memory_pressure',
            'disk_usage', 'io_wait'
        ]

    def _count_system_dimensions(self, state: EnvironmentState) -> Tuple[int, int]:
        """统计系统维度数"""
        counts = {"with_data": 0, "total": 0}
        for attr in self._system_attrs():
            self._count_attr(state, attr, counts)
        return counts["with_data"], counts["total"]

    def _count_dimensions(self, state: EnvironmentState) -> Tuple[int, int]:
        """统计有有效数据的维度数"""
        sys_with_data, sys_total = self._count_system_dimensions(state)
        dimensions_with_data = sys_with_data + (1 if state.logs.error_rate >= 0 else 0)
        total_dimensions = sys_total + 1
        return dimensions_with_data, total_dimensions

    def _apply_coverage_boost(self, coverage: float) -> float:
        """应用历史覆盖度加成"""
        if len(self.metrics_history) > 10:
            return min(1.0, coverage * (1 + len(self.metrics_history) / 1000))
        return coverage

    def _compute_coverage_index(self, state: EnvironmentState) -> float:
        """
        计算广度进化指数

        MVP简化：基于状态维度覆盖
        """
        dimensions_with_data, total_dimensions = self._count_dimensions(state)
        coverage = dimensions_with_data / max(total_dimensions, 1)
        return self._apply_coverage_boost(coverage)

    def _compute_resource_efficiency(self, state: EnvironmentState) -> Tuple[float, float]:
        """计算资源效率"""
        return 1.0 - state.self.agent_cpu, 1.0 - state.self.agent_memory

    def _compute_efficiency_index(self, state: EnvironmentState) -> float:
        """
        计算能效进化指数

        目标：用更少的资源做更多的事
        """
        cpu_eff, mem_eff = self._compute_resource_efficiency(state)
        task_success_rate = self.successful_tasks / max(self.total_tasks, 1)
        efficiency = 0.4 * cpu_eff + 0.3 * mem_eff + 0.3 * task_success_rate
        return max(0.0, min(1.0, efficiency))

    def _get_recent_metrics(self, n: int) -> List[EvolutionMetrics]:
        """获取最近n个指标"""
        return list(self.metrics_history)[-min(n, len(self.metrics_history)):]

    def _is_precision_dropped(self, prev: float, curr: float) -> bool:
        """判断精度是否突降"""
        return prev > 0.1 and (prev - curr) / prev > 0.3

    def _check_and_record_precision_drop(self, prev: float, curr: float) -> None:
        if self._is_precision_dropped(prev, curr):
            self._record_anomaly(
                type="precision_drop",
                severity="HIGH",
                message=f"Precision dropped from {prev:.3f} to {curr:.3f}",
                data={"prev": prev, "curr": curr}
            )

    def _detect_precision_drop(self, recent: List[EvolutionMetrics]) -> None:
        """检测精度突降"""
        if len(recent) >= 2:
            self._check_and_record_precision_drop(recent[-2].precision_index, recent[-1].precision_index)

    def _is_stagnant_indices(self, indices: List[float]) -> bool:
        """判断指数列表是否停滞"""
        return max(indices) - min(indices) < 0.01

    def _check_and_record_stagnation(self, indices: List[float]) -> None:
        if self._is_stagnant_indices(indices):
            self._record_anomaly(
                type="stagnation",
                severity="MEDIUM",
                message="No evolution detected in last 20 cycles",
                data={"range": max(indices) - min(indices)}
            )

    def _detect_stagnation(self) -> None:
        """检测停滞"""
        if len(self.metrics_history) >= 20:
            recent_20 = list(self.metrics_history)[-20:]
            indices = [m.evolution_index for m in recent_20]
            self._check_and_record_stagnation(indices)

    def _detect_anomalies(self, current_metrics: EvolutionMetrics) -> None:
        """
        检测异常

        第一性原理：异常是系统需要调整的信号
        """
        if len(self.metrics_history) < 2:
            return
        self._detect_precision_drop(self._get_recent_metrics(10))
        self._detect_stagnation()

    def _create_anomaly(
        self,
        type: str,
        severity: str,
        message: str,
        data: Dict[str, Any]
    ) -> AnomalyEvent:
        return AnomalyEvent(
            type=type,
            severity=severity,
            message=message,
            data=data
        )

    def _record_anomaly(
        self,
        type: str,
        severity: str,
        message: str,
        data: Dict[str, Any]
    ) -> None:
        """记录异常"""
        anomaly = self._create_anomaly(type, severity, message, data)
        self.anomalies.append(anomaly)
        logger.warning(f"Anomaly detected: [{severity}] {message}")

    def _get_recent_indices(self, n: int) -> List[float]:
        """获取最近n个进化指数"""
        recent = list(self.metrics_history)[-min(n, len(self.metrics_history)):]
        return [m.evolution_index for m in recent]

    def _check_stagnant(self, indices: List[float]) -> bool:
        """检查是否停滞"""
        return max(indices) - min(indices) < 0.02

    def _check_stable(self, diff: float) -> bool:
        """检查是否稳定"""
        return abs(diff) < 0.01

    def _compute_halves_diff(self, indices: List[float]) -> float:
        """计算前后半段均值差"""
        mid = len(indices) // 2
        first = indices[:mid]
        second = indices[mid:]
        if np is not None:
            first_half = float(np.mean(first))
            second_half = float(np.mean(second))
        else:
            first_half = sum(first) / len(first) if first else 0.0
            second_half = sum(second) / len(second) if second else 0.0
        return second_half - first_half

    def _resolve_trend(self, diff: float) -> EvolutionTrend:
        """根据差值解析趋势"""
        if self._check_stable(diff):
            return EvolutionTrend.STABLE
        if diff > 0:
            return EvolutionTrend.IMPROVING
        return EvolutionTrend.DEGRADING

    def _get_trend_indices(self) -> List[float]:
        return self._get_recent_indices(30)

    def detect_trend(self) -> EvolutionTrend:
        """
        检测进化趋势

        算法：线性回归拟合
        """
        if len(self.metrics_history) < 10:
            return EvolutionTrend.INSUFFICIENT_DATA
        indices = self._get_trend_indices()
        if self._check_stagnant(indices):
            return EvolutionTrend.STAGNANT
        return self._resolve_trend(self._compute_halves_diff(indices))

    def get_current_metrics(self) -> Optional[EvolutionMetrics]:
        """获取当前指标"""
        if not self.metrics_history:
            return None
        return self.metrics_history[-1]

    def get_recent_anomalies(self, count: int = 10) -> List[AnomalyEvent]:
        """获取最近异常"""
        return list(self.anomalies)[-count:]

    def _get_uptime(self) -> float:
        """获取运行时间"""
        return time.time() - getattr(self, '_start_time', time.time())

    def _anomaly_to_dict(self, a: AnomalyEvent) -> Dict[str, Any]:
        return {
            "type": a.type,
            "severity": a.severity,
            "message": a.message,
            "timestamp": a.timestamp
        }

    def _build_anomaly_dicts(self, anomalies: List[AnomalyEvent]) -> List[Dict[str, Any]]:
        """构建异常字典列表"""
        return [self._anomaly_to_dict(a) for a in anomalies]

    def _compute_success_rate(self) -> float:
        """计算成功率"""
        return self.successful_tasks / max(self.total_tasks, 1)

    def _base_report(self) -> Dict[str, Any]:
        return {
            "timestamp": time.time(),
            "uptime_seconds": self._get_uptime(),
            "total_cycles": self.total_cycles,
            "total_tasks": self.total_tasks,
            "success_rate": self._compute_success_rate(),
        }

    def _report_core(self, current: Optional[EvolutionMetrics], trend: EvolutionTrend) -> Dict[str, Any]:
        report = self._base_report()
        report["current_metrics"] = current.to_dict() if current else {}
        report["trend"] = trend.value
        return report

    def _build_report_data(
        self,
        current: Optional[EvolutionMetrics],
        trend: EvolutionTrend,
        anomalies: List[AnomalyEvent]
    ) -> Dict[str, Any]:
        """构建报告数据"""
        report = self._report_core(current, trend)
        report["recent_anomalies"] = self._build_anomaly_dicts(anomalies)
        return report

    def _gather_report_inputs(self) -> Tuple[Optional[EvolutionMetrics], EvolutionTrend, List[AnomalyEvent]]:
        return self.get_current_metrics(), self.detect_trend(), self.get_recent_anomalies(5)

    def generate_report(self) -> Dict[str, Any]:
        """
        生成进化报告

        第一性原理：报告是自我认知的载体
        """
        current, trend, recent_anomalies = self._gather_report_inputs()
        return self._build_report_data(current, trend, recent_anomalies)

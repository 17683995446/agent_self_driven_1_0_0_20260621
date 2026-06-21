"""
混沌工程与容错测试系统

第一性原理：系统可靠性必须通过主动破坏来验证
- 故障注入：模拟各种故障场景
- 恢复验证：确认系统能从故障中恢复
- 边界探索：发现系统的脆弱点

类比：生物的"免疫训练"——通过接触弱化的病原体，
让免疫系统学会应对真实威胁
"""

import random
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional


class FaultType(Enum):
    """故障类型"""
    LATENCY = auto()      # 延迟注入
    EXCEPTION = auto()    # 异常注入
    CPU_SPIKE = auto()    # CPU飙升（模拟）
    MEMORY_PRESSURE = auto()  # 内存压力（模拟）
    NETWORK_PARTITION = auto()  # 网络分区（模拟）


@dataclass
class FaultResult:
    """故障注入结果"""
    fault_type: str
    target: str
    injected: bool
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class ChaosExperiment:
    """混沌实验定义"""
    name: str
    fault_type: FaultType
    target: str
    probability: float = 0.1  # 故障触发概率
    intensity: float = 1.0    # 故障强度
    duration: float = 5.0     # 实验持续时间（秒）


class FaultInjectorBase(ABC):
    """故障注入器抽象基类"""

    @abstractmethod
    def inject_latency(self, target: str, delay_ms: float) -> FaultResult:
        """注入延迟"""
        pass

    @abstractmethod
    def inject_exception(self, target: str, exception: Exception) -> FaultResult:
        """注入异常"""
        pass


class ChaosEngineer(FaultInjectorBase):
    """
    混沌工程师

    职责：
    1. 管理和执行混沌实验
    2. 注入各类故障
    3. 记录故障注入结果
    4. 验证系统恢复能力

    第一性原理：
    - 可控破坏：故障必须可控制、可恢复
    - 最小爆炸半径：故障影响范围必须受限
    - 可观测：故障注入过程必须全程可观测
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._experiments: List[ChaosExperiment] = []
        self._results: List[FaultResult] = []
        self._lock = threading.Lock()
        self._active_faults: Dict[str, bool] = {}

    def enable(self) -> None:
        """启用混沌工程"""
        self.enabled = True

    def disable(self) -> None:
        """禁用混沌工程"""
        self.enabled = False

    def add_experiment(self, experiment: ChaosExperiment) -> None:
        """添加混沌实验"""
        if not experiment.name:
            raise ValueError("experiment name must not be empty")
        if not (0.0 <= experiment.probability <= 1.0):
            raise ValueError("probability must be in [0.0, 1.0]")

        with self._lock:
            self._experiments.append(experiment)

    def remove_experiment(self, name: str) -> bool:
        """移除混沌实验"""
        with self._lock:
            for i, exp in enumerate(self._experiments):
                if exp.name == name:
                    self._experiments.pop(i)
                    return True
            return False

    def list_experiments(self) -> List[ChaosExperiment]:
        """列出所有实验"""
        with self._lock:
            return list(self._experiments)

    def should_inject(self, target: str, probability: float) -> bool:
        """判断是否应注入故障"""
        if not self.enabled:
            return False
        if self._active_faults.get(target, False):
            return False
        return random.random() < probability

    def _record_skipped_latency(self, target: str) -> FaultResult:
        """记录跳过的延迟注入"""
        result = FaultResult(
            fault_type="LATENCY",
            target=target,
            injected=False,
        )
        with self._lock:
            self._results.append(result)
        return result

    def _record_injected_latency(self, target: str, start: float) -> FaultResult:
        """记录已注入的延迟"""
        result = FaultResult(
            fault_type="LATENCY",
            target=target,
            injected=True,
            duration_ms=(time.time() - start) * 1000,
        )
        with self._lock:
            self._results.append(result)
        return result

    def inject_latency(self, target: str, delay_ms: float) -> FaultResult:
        """
        注入延迟

        Args:
            target: 目标模块
            delay_ms: 延迟毫秒数
        """
        start = time.time()
        if not self.should_inject(target, 1.0):
            return self._record_skipped_latency(target)

        self._active_faults[target] = True
        try:
            time.sleep(delay_ms / 1000.0)
            return self._record_injected_latency(target, start)
        finally:
            self._active_faults[target] = False

    def _record_skipped_exception(self, target: str) -> FaultResult:
        """记录跳过的异常注入"""
        result = FaultResult(
            fault_type="EXCEPTION",
            target=target,
            injected=False,
        )
        with self._lock:
            self._results.append(result)
        return result

    def _record_injected_exception(self, target: str, exception: Exception) -> FaultResult:
        """记录已注入的异常"""
        result = FaultResult(
            fault_type="EXCEPTION",
            target=target,
            injected=True,
            error=str(exception),
        )
        with self._lock:
            self._results.append(result)
        return result

    def inject_exception(self, target: str, exception: Exception) -> FaultResult:
        """
        注入异常

        Args:
            target: 目标模块
            exception: 要抛出的异常
        """
        if not self.should_inject(target, 1.0):
            return self._record_skipped_exception(target)
        return self._record_injected_exception(target, exception)

    def _inject_latency_fault(self, target: str, intensity: float, fn: Callable[[], Any]) -> Any:
        """注入延迟故障并执行"""
        delay_ms = 100.0 * intensity
        self.inject_latency(target, delay_ms)
        return fn()

    def _inject_exception_fault(self, target: str) -> None:
        """注入异常故障"""
        result = self.inject_exception(target, RuntimeError(f"chaos injected fault in {target}"))
        with self._lock:
            self._results.append(result)
        raise RuntimeError(result.error)

    def _simulate_cpu_spike(self, target: str, intensity: float) -> FaultResult:
        """模拟CPU飙升"""
        duration = 0.05 * intensity
        start = time.time()
        deadline = start + duration
        while time.time() < deadline:
            pass
        result = FaultResult(
            fault_type="CPU_SPIKE",
            target=target,
            injected=True,
            duration_ms=(time.time() - start) * 1000,
        )
        with self._lock:
            self._results.append(result)
        return result

    def _simulate_memory_pressure(self, target: str, intensity: float) -> FaultResult:
        """模拟内存压力"""
        size_mb = max(0, int(10 * intensity))
        start = time.time()
        if size_mb > 0:
            data = bytearray(size_mb * 1024 * 1024)
            del data
        result = FaultResult(
            fault_type="MEMORY_PRESSURE",
            target=target,
            injected=True,
            duration_ms=(time.time() - start) * 1000,
        )
        with self._lock:
            self._results.append(result)
        return result

    def _simulate_network_partition(self, target: str) -> FaultResult:
        """模拟网络分区"""
        result = FaultResult(
            fault_type="NETWORK_PARTITION",
            target=target,
            injected=True,
            error="connection refused (simulated)",
        )
        with self._lock:
            self._results.append(result)
        return result

    def _wrap_with_fault(
        self,
        target: str,
        fn: Callable[[], Any],
        fault_type: FaultType,
        probability: float,
        intensity: float,
    ) -> Any:
        """执行带故障注入的包装逻辑"""
        if not self.should_inject(target, probability):
            return fn()
        if fault_type == FaultType.LATENCY:
            return self._inject_latency_fault(target, intensity, fn)
        elif fault_type == FaultType.EXCEPTION:
            self._inject_exception_fault(target)
        elif fault_type == FaultType.CPU_SPIKE:
            self._simulate_cpu_spike(target, intensity)
        elif fault_type == FaultType.MEMORY_PRESSURE:
            self._simulate_memory_pressure(target, intensity)
        elif fault_type == FaultType.NETWORK_PARTITION:
            self._simulate_network_partition(target)
        return fn()

    def wrap_with_fault(
        self,
        target: str,
        fn: Callable[[], Any],
        fault_type: FaultType,
        probability: float = 0.1,
        intensity: float = 1.0,
    ) -> Callable[[], Any]:
        """
        为函数包装故障注入

        Args:
            target: 目标标识
            fn: 原始函数（无参数）
            fault_type: 故障类型
            probability: 触发概率
            intensity: 故障强度

        Returns:
            包装后的函数
        """
        def wrapper() -> Any:
            return self._wrap_with_fault(target, fn, fault_type, probability, intensity)

        return wrapper

    def _run_latency_experiment(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行延迟实验"""
        delay_ms = 50.0 * experiment.intensity
        result = self.inject_latency(experiment.target, delay_ms)
        if result.injected:
            results.append(result)

    def _run_exception_experiment(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行异常实验"""
        result = self.inject_exception(
            experiment.target,
            RuntimeError(f"chaos experiment: {experiment.name}"),
        )
        if result.injected:
            results.append(result)

    def _run_cpu_experiment(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行CPU飙升实验"""
        result = self._simulate_cpu_spike(experiment.target, experiment.intensity)
        results.append(result)

    def _run_memory_experiment(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行内存压力实验"""
        result = self._simulate_memory_pressure(experiment.target, experiment.intensity)
        results.append(result)

    def _run_network_experiment(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行网络分区实验"""
        result = self._simulate_network_partition(experiment.target)
        results.append(result)

    def _run_single_fault(self, experiment: ChaosExperiment, results: List[FaultResult]) -> None:
        """运行单次故障注入"""
        if experiment.fault_type == FaultType.LATENCY:
            self._run_latency_experiment(experiment, results)
        elif experiment.fault_type == FaultType.EXCEPTION:
            self._run_exception_experiment(experiment, results)
        elif experiment.fault_type == FaultType.CPU_SPIKE:
            self._run_cpu_experiment(experiment, results)
        elif experiment.fault_type == FaultType.MEMORY_PRESSURE:
            self._run_memory_experiment(experiment, results)
        elif experiment.fault_type == FaultType.NETWORK_PARTITION:
            self._run_network_experiment(experiment, results)

    def run_experiment(self, experiment: ChaosExperiment) -> List[FaultResult]:
        """
        运行混沌实验

        Args:
            experiment: 实验定义

        Returns:
            故障注入结果列表
        """
        results: List[FaultResult] = []
        if not self.enabled:
            return results

        end_time = time.time() + experiment.duration
        while time.time() < end_time:
            self._run_single_fault(experiment, results)
            time.sleep(0.1)

        with self._lock:
            self._results.extend(results)

        return results

    def get_results(self) -> List[FaultResult]:
        """获取所有故障注入结果"""
        with self._lock:
            return list(self._results)

    def get_stats(self) -> Dict[str, Any]:
        """获取混沌工程统计"""
        with self._lock:
            total = len(self._results)
            injected = sum(1 for r in self._results if r.injected)
            by_type: Dict[str, int] = {}
            for r in self._results:
                by_type[r.fault_type] = by_type.get(r.fault_type, 0) + 1

        return {
            "enabled": self.enabled,
            "total_experiments": len(self._experiments),
            "total_injections": total,
            "successful_injections": injected,
            "by_type": by_type,
        }

    def reset(self) -> None:
        """重置所有结果"""
        with self._lock:
            self._results.clear()
            self._active_faults.clear()


class ResilienceTestRunner:
    """
    弹性测试运行器

    验证系统在故障后的恢复能力
    """

    def __init__(self, chaos_engineer: ChaosEngineer) -> None:
        self.chaos = chaos_engineer
        self._test_results: List[Dict[str, Any]] = []

    def _run_fault_phase(self, target: str, fault_type: FaultType, duration: float) -> List[FaultResult]:
        """运行故障注入阶段"""
        self.chaos.enable()
        exp = ChaosExperiment(
            name=f"recovery_test_{target}",
            fault_type=fault_type,
            target=target,
            probability=1.0,
            duration=duration,
        )
        self.chaos.add_experiment(exp)
        return self.chaos.run_experiment(exp)

    def _build_test_result(
        self,
        target: str,
        normal_result: Any,
        recovery_result: Any,
        fault_results: List[FaultResult]
    ) -> Dict[str, Any]:
        """构建测试结果"""
        success = normal_result == recovery_result
        return {
            "target": target,
            "normal_result": str(normal_result),
            "recovery_result": str(recovery_result),
            "fault_injections": len(fault_results),
            "recovered": success,
        }

    def test_recovery(
        self,
        target: str,
        normal_fn: Callable[[], Any],
        fault_type: FaultType,
        duration: float = 3.0,
    ) -> Dict[str, Any]:
        """
        测试系统恢复能力

        流程：
        1. 记录正常状态
        2. 注入故障
        3. 验证故障影响
        4. 停止故障
        5. 验证恢复正常
        """
        normal_result = normal_fn()
        fault_results = self._run_fault_phase(target, fault_type, duration)
        self.chaos.disable()
        recovery_result = normal_fn()
        result = self._build_test_result(target, normal_result, recovery_result, fault_results)
        self._test_results.append(result)
        return result

    def get_test_results(self) -> List[Dict[str, Any]]:
        """获取所有测试结果"""
        return list(self._test_results)

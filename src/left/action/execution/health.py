"""
系统健康检查与自诊断

第一性原理：系统必须能感知自身健康状态，并在故障前自我修复
- 模块化检查：每个子系统独立诊断
- 分级健康：健康/亚健康/不健康/故障
- 自修复：常见问题自动恢复
- 诊断报告：结构化输出，便于分析

类比：生物的"免疫系统"——识别异常、自动修复、记忆故障模式
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthStatus
    message: str = ""
    last_check: float = field(default_factory=time.time)
    metrics: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check,
            "metrics": self.metrics,
            "response_time_ms": self.response_time_ms,
        }


class HealthCheckBase(ABC):
    """健康检查抽象基类"""

    @abstractmethod
    def check(self) -> ComponentHealth:
        """执行健康检查"""
        pass


class HealthCheck(HealthCheckBase):
    """
    健康检查基类

    第一性原理：每个组件必须有自我诊断能力
    """

    def __init__(self, name: str, timeout: float = 5.0) -> None:
        self.name = name
        self.timeout = timeout

    def _do_check(self) -> tuple:
        """实际检查逻辑（子类重写）"""
        return HealthStatus.HEALTHY, "OK", {}

    def _handle_check_exception(self, e: Exception) -> tuple:
        return HealthStatus.FAILED, f"Check failed: {e}", {}

    def _make_component(self, status, message, metrics, elapsed) -> ComponentHealth:
        return ComponentHealth(
            name=self.name,
            status=status,
            message=message,
            metrics=metrics,
            response_time_ms=elapsed,
        )

    def check(self) -> ComponentHealth:
        start = time.perf_counter()
        try:
            status, message, metrics = self._do_check()
        except Exception as e:
            status, message, metrics = self._handle_check_exception(e)
        elapsed = (time.perf_counter() - start) * 1000
        return self._make_component(status, message, metrics, elapsed)


class DiagnosticsBase(ABC):
    """自诊断系统抽象基类"""

    @abstractmethod
    def run_all_checks(self) -> Dict[str, ComponentHealth]:
        """执行所有健康检查"""
        pass

    @abstractmethod
    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        pass


class SelfDiagnostics(DiagnosticsBase):
    """
    自诊断系统

    第一性原理：系统必须定期自检，发现问题主动修复
    """

    def _init_collections(self) -> None:
        self._checks: Dict[str, HealthCheck] = {}
        self._results: Dict[str, ComponentHealth] = {}
        self._results_lock = threading.Lock()
        self._healers: Dict[str, Callable[[ComponentHealth], bool]] = {}
        self._history: List[Dict] = []
        self._max_history = 100

    def __init__(self, check_interval: float = 60.0) -> None:
        self.check_interval = check_interval
        self._init_collections()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def register_check(self, check: HealthCheck) -> None:
        self._checks[check.name] = check
        logger.info(f"Health check registered: {check.name}")

    def register_healer(self, component_name: str, healer: Callable[[ComponentHealth], bool]) -> None:
        self._healers[component_name] = healer

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, name="health_checker")
        self._thread.daemon = True
        self._thread.start()
        logger.info("SelfDiagnostics started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("SelfDiagnostics stopped")

    def _check_loop(self) -> None:
        while self._running:
            self.run_all_checks()
            for _ in range(int(self.check_interval)):
                if not self._running:
                    break
                time.sleep(1)

    def _run_single_check(self, check: HealthCheck) -> ComponentHealth:
        return check.check()

    def _log_heal_attempt(self, name: str) -> None:
        logger.info(f"Attempting to heal {name}...")

    def _log_heal_success(self, name: str) -> None:
        logger.info(f"Healed {name} successfully")

    def _log_heal_failure(self, name: str) -> None:
        logger.warning(f"Failed to heal {name}")

    def _log_heal_exception(self, name: str, e: Exception) -> None:
        logger.error(f"Healer for {name} failed: {e}")

    def _try_heal(self, health: ComponentHealth) -> None:
        healer = self._healers.get(health.name)
        if not healer:
            return
        self._log_heal_attempt(health.name)
        try:
            success = healer(health)
        except Exception as e:
            self._log_heal_exception(health.name, e)
            return
        if success:
            self._log_heal_success(health.name)
        else:
            self._log_heal_failure(health.name)

    def _needs_healing(self, status: HealthStatus) -> bool:
        """判断是否需要修复"""
        return status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.FAILED]

    def _history_entry(self, results: Dict[str, ComponentHealth]) -> Dict:
        return {
            "timestamp": time.time(),
            "results": {name: r.to_dict() for name, r in results.items()},
        }

    def _trim_history(self) -> None:
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _store_results(self, results: Dict[str, ComponentHealth]) -> None:
        """存储检查结果到历史"""
        with self._results_lock:
            self._results = results
            self._history.append(self._history_entry(results))
            self._trim_history()

    def _run_check_and_heal(self, check: HealthCheck, results: Dict[str, ComponentHealth]) -> None:
        result = self._run_single_check(check)
        results[check.name] = result
        if self._needs_healing(result.status):
            self._try_heal(result)

    def run_all_checks(self) -> Dict[str, ComponentHealth]:
        results = {}
        for check in self._checks.values():
            self._run_check_and_heal(check, results)
        self._store_results(results)
        return results

    def check_component(self, name: str) -> Optional[ComponentHealth]:
        check = self._checks.get(name)
        if not check:
            return None
        return check.check()

    def _any_status(self, statuses: List[HealthStatus], target: HealthStatus) -> bool:
        return any(s == target for s in statuses)

    def get_overall_status(self) -> HealthStatus:
        with self._results_lock:
            if not self._results:
                return HealthStatus.HEALTHY
            statuses = [r.status for r in self._results.values()]
        if self._any_status(statuses, HealthStatus.FAILED):
            return HealthStatus.FAILED
        if self._any_status(statuses, HealthStatus.UNHEALTHY):
            return HealthStatus.UNHEALTHY
        if self._any_status(statuses, HealthStatus.DEGRADED):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _count_healthy(self, results: Dict[str, ComponentHealth]) -> int:
        """统计健康组件数"""
        return sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY)

    def _report_components(self, results: Dict[str, ComponentHealth]) -> Dict:
        return {name: r.to_dict() for name, r in results.items()}

    def _build_report(
        self,
        results: Dict[str, ComponentHealth],
        overall: HealthStatus
    ) -> Dict[str, Any]:
        """构建诊断报告"""
        healthy_count = self._count_healthy(results)
        total_count = len(results)
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall.value,
            "healthy_components": healthy_count,
            "total_components": total_count,
            "components": self._report_components(results),
        }

    def _copy_results(self) -> Dict[str, ComponentHealth]:
        with self._results_lock:
            return dict(self._results)

    def get_report(self) -> Dict[str, Any]:
        results = self._copy_results()
        overall = self.get_overall_status()
        return self._build_report(results, overall)

    def get_component_status(self, name: str) -> Optional[ComponentHealth]:
        with self._results_lock:
            return self._results.get(name)

    def get_history(self, n: int = 10) -> List[Dict]:
        with self._results_lock:
            return self._history[-n:]


class MemoryHealthCheck(HealthCheck):
    """内存健康检查"""

    def __init__(self, warning_threshold: float = 0.8, critical_threshold: float = 0.95) -> None:
        super().__init__("memory")
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def _check_memory(self, usage: float) -> tuple:
        if usage > self.critical_threshold:
            return HealthStatus.FAILED, f"Memory critical: {usage:.1%}", {"usage": usage}
        if usage > self.warning_threshold:
            return HealthStatus.DEGRADED, f"Memory high: {usage:.1%}", {"usage": usage}
        return HealthStatus.HEALTHY, f"Memory OK: {usage:.1%}", {"usage": usage}

    def _do_check(self) -> tuple:
        import psutil
        mem = psutil.virtual_memory()
        usage = mem.percent / 100.0
        return self._check_memory(usage)


class CPUHealthCheck(HealthCheck):
    """CPU健康检查"""

    def __init__(self, warning_threshold: float = 0.8, critical_threshold: float = 0.95) -> None:
        super().__init__("cpu")
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def _check_cpu(self, usage: float) -> tuple:
        if usage > self.critical_threshold:
            return HealthStatus.FAILED, f"CPU critical: {usage:.1%}", {"usage": usage}
        if usage > self.warning_threshold:
            return HealthStatus.DEGRADED, f"CPU high: {usage:.1%}", {"usage": usage}
        return HealthStatus.HEALTHY, f"CPU OK: {usage:.1%}", {"usage": usage}

    def _do_check(self) -> tuple:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5) / 100.0
        return self._check_cpu(cpu)


class DiskHealthCheck(HealthCheck):
    """磁盘健康检查"""

    def __init__(self, warning_threshold: float = 0.85, critical_threshold: float = 0.95) -> None:
        super().__init__("disk")
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def _check_disk(self, usage: float) -> tuple:
        if usage > self.critical_threshold:
            return HealthStatus.FAILED, f"Disk critical: {usage:.1%}", {"usage": usage}
        if usage > self.warning_threshold:
            return HealthStatus.DEGRADED, f"Disk high: {usage:.1%}", {"usage": usage}
        return HealthStatus.HEALTHY, f"Disk OK: {usage:.1%}", {"usage": usage}

    def _do_check(self) -> tuple:
        import psutil
        disk = psutil.disk_usage("/")
        usage = disk.percent / 100.0
        return self._check_disk(usage)

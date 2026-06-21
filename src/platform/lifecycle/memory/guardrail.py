"""
安全护栏模块

第一性原理：安全约束是系统的"物理定律"，不可违反
类比：生物的"免疫系统"——识别威胁、触发防御、维持稳态
"""

import re
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum

from ...support.models.base.state import ResourceUsage, GuardrailResult, EnforcementAction


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开试探


@dataclass
class CircuitBreaker:
    """熔断器"""
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self._close()
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.failure_count >= self.failure_threshold:
            self._open()

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            return self._handle_open_state()
        if self.state == CircuitState.HALF_OPEN:
            return self._handle_half_open_state()
        return False

    def _handle_open_state(self) -> bool:
        if time.time() - self.last_failure_time >= self.recovery_timeout:
            self._half_open()
            return True
        return False

    def _handle_half_open_state(self) -> bool:
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        logger.warning(f"Circuit breaker '{self.name}' OPENED")

    def _half_open(self) -> None:
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' HALF_OPEN")

    def _close(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' CLOSED")


class GuardrailBase(ABC):
    """安全护栏抽象基类"""

    @abstractmethod
    def check_operation(self, operation: str) -> GuardrailResult:
        """检查操作是否允许"""
        pass


class SafetyGuardrail(GuardrailBase):
    """
    安全护栏系统

    核心约束（不可违反）：
    1. CPU使用 ≤ 20%
    2. 内存使用 ≤ 20%
    3. 禁止修改系统关键文件
    4. 连续5次失败自动停止探索
    5. 异常熔断机制

    第一性原理：
    - 安全约束是系统的"物理定律"
    - 任何代码路径都不能绕过护栏
    - 回滚是最后的保障
    """

    FORBIDDEN_PATTERNS: List[Tuple[str, str, str]] = [
        (r'rm\s+-rf\s+/', "CRITICAL", "Attempt to delete system files"),
        (r'mkfs', "CRITICAL", "Attempt to format filesystem"),
        (r'dd\s+if=.*of=/dev/', "CRITICAL", "Attempt to write to device"),
        (r'>\s*/etc/', "HIGH", "Attempt to modify system config"),
        (r'chmod\s+-R\s+777\s+/', "HIGH", "Attempt to change permissions"),
    ]

    def __init__(
        self,
        max_cpu: float = 0.2,
        max_memory: float = 0.2,
        max_disk: float = 0.85
    ) -> None:
        self._max_cpu = max_cpu
        self._max_memory = max_memory
        self._max_disk = max_disk
        self._init_usage_state()
        self._init_breakers()
        logger.info(f"Guardrail initialized: CPU≤{max_cpu}, Memory≤{max_memory}, Disk≤{max_disk}")

    def _init_usage_state(self) -> None:
        self.current_usage = ResourceUsage()
        self.violation_count = 0

    def _init_breakers(self) -> None:
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._init_default_breakers()

    def _init_default_breakers(self) -> None:
        """初始化默认熔断器"""
        self.circuit_breakers["exploration"] = CircuitBreaker("exploration", failure_threshold=5)
        self.circuit_breakers["task_execution"] = CircuitBreaker("task_execution", failure_threshold=10)
        self.circuit_breakers["prediction"] = CircuitBreaker("prediction", failure_threshold=20)

    @property
    def max_cpu(self) -> float:
        """CPU上限"""
        return self._max_cpu

    @max_cpu.setter
    def max_cpu(self, value: float) -> None:
        """动态设置CPU上限"""
        self._max_cpu = float(value)

    @property
    def max_memory(self) -> float:
        """内存上限"""
        return self._max_memory

    @max_memory.setter
    def max_memory(self, value: float) -> None:
        """动态设置内存上限"""
        self._max_memory = float(value)

    @property
    def max_disk(self) -> float:
        """磁盘上限"""
        return self._max_disk

    @max_disk.setter
    def max_disk(self, value: float) -> None:
        """动态设置磁盘上限"""
        self._max_disk = float(value)

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name)
        return self.circuit_breakers[name]

    def _match_forbidden(self, operation: str) -> Optional[GuardrailResult]:
        """匹配禁止的操作模式"""
        for pattern, severity, description in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, operation):
                return self._forbidden_result(description, severity)
        return None

    def _forbidden_result(self, description: str, severity: str) -> GuardrailResult:
        logger.critical(f"FORBIDDEN OPERATION DETECTED: {description}")
        return GuardrailResult(
            allowed=False,
            reason=description,
            severity=severity
        )

    def check_operation(self, operation: str) -> GuardrailResult:
        """
        检查操作是否允许

        此检查必须在任何操作执行前调用，且不能被任何条件跳过
        """
        result = self._match_forbidden(operation)
        if result is not None:
            return result
        return GuardrailResult(allowed=True)

    def _check_cpu(self, usage: ResourceUsage) -> Optional[str]:
        """检查CPU是否超限"""
        if usage.cpu > self._max_cpu:
            return f"CPU usage {usage.cpu:.2%} exceeds limit {self._max_cpu:.2%}"
        return None

    def _check_memory(self, usage: ResourceUsage) -> Optional[str]:
        """检查内存是否超限"""
        if usage.memory > self._max_memory:
            return f"Memory usage {usage.memory:.2%} exceeds limit {self._max_memory:.2%}"
        return None

    def _check_disk(self, usage: ResourceUsage) -> Optional[str]:
        """检查磁盘是否超限"""
        if usage.disk > self._max_disk:
            return f"Disk usage {usage.disk:.2%} exceeds limit {self._max_disk:.2%}"
        return None

    def check_resource_usage(self, usage: ResourceUsage) -> GuardrailResult:
        """检查资源使用是否超限"""
        violations = self._collect_violations(usage)
        if violations:
            return self._build_violation_result(violations)
        return GuardrailResult(allowed=True)

    def _collect_violations(self, usage: ResourceUsage) -> List[str]:
        violations: List[str] = []
        for check in [self._check_cpu, self._check_memory, self._check_disk]:
            msg = check(usage)
            if msg:
                violations.append(msg)
        return violations

    def _build_violation_result(self, violations: List[str]) -> GuardrailResult:
        self.violation_count += 1
        return GuardrailResult(
            allowed=False,
            reason="; ".join(violations),
            severity="HIGH"
        )

    def _cpu_action(self, usage: ResourceUsage, reason: str) -> EnforcementAction:
        """CPU超限的强制动作"""
        return EnforcementAction(
            action="THROTTLE",
            target_cpu=self._max_cpu,
            reason=reason
        )

    def _memory_action(self, reason: str) -> EnforcementAction:
        """内存超限的强制动作"""
        return EnforcementAction(
            action="TERMINATE",
            reason=reason
        )

    def _default_action(self, reason: str) -> EnforcementAction:
        """默认强制动作"""
        return EnforcementAction(action="BLOCK", reason=reason)

    def enforce_resource_limits(self, usage: ResourceUsage) -> EnforcementAction:
        """
        强制执行资源限制

        如果超出限制，返回限制动作
        """
        result = self.check_resource_usage(usage)
        if result.allowed:
            return EnforcementAction(action="NONE")
        return self._resolve_enforcement_action(usage, result.reason)

    def _resolve_enforcement_action(self, usage: ResourceUsage, reason: str) -> EnforcementAction:
        if usage.cpu > self._max_cpu:
            return self._cpu_action(usage, reason)
        if usage.memory > self._max_memory:
            return self._memory_action(reason)
        return self._default_action(reason)

    def _update_cpu(self, cpu: float = None) -> None:
        """更新CPU使用记录"""
        if cpu is not None:
            self.current_usage.cpu = cpu

    def _update_memory(self, memory: float = None) -> None:
        """更新内存使用记录"""
        if memory is not None:
            self.current_usage.memory = memory

    def _update_disk(self, disk: float = None) -> None:
        """更新磁盘使用记录"""
        if disk is not None:
            self.current_usage.disk = disk

    def update_usage(
        self,
        cpu: float = None,
        memory: float = None,
        disk: float = None
    ) -> None:
        """更新当前资源使用记录"""
        self._update_cpu(cpu)
        self._update_memory(memory)
        self._update_disk(disk)

    def record_circuit_result(self, breaker_name: str, success: bool) -> None:
        """记录熔断器结果"""
        breaker = self.get_circuit_breaker(breaker_name)
        if success:
            breaker.record_success()
        else:
            breaker.record_failure()

    def check_circuit(self, breaker_name: str) -> GuardrailResult:
        """检查熔断器状态"""
        breaker = self.get_circuit_breaker(breaker_name)
        if breaker.can_execute():
            return GuardrailResult(allowed=True)
        return self._circuit_blocked_result(breaker_name, breaker)

    def _circuit_blocked_result(self, breaker_name: str, breaker: CircuitBreaker) -> GuardrailResult:
        return GuardrailResult(
            allowed=False,
            reason=f"Circuit breaker '{breaker_name}' is {breaker.state.value}",
            severity="HIGH"
        )

    def get_circuit_stats(self) -> Dict[str, Dict]:
        """获取所有熔断器统计"""
        return {
            name: self._breaker_stats(cb)
            for name, cb in self.circuit_breakers.items()
        }

    def _breaker_stats(self, cb: CircuitBreaker) -> Dict:
        return {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "success_count": cb.success_count,
        }


class ExplorationStopLoss:
    """
    探索止损机制

    刚性约束：连续失败N次后必须停止
    """

    MAX_CONSECUTIVE_FAILURES = 5

    def __init__(self) -> None:
        self.failure_counts: Dict[str, int] = {}
        self.frozen_explorations: set = set()

    def record_result(self, exploration_type: str, success: bool) -> None:
        """记录探索结果"""
        if success:
            self._record_success(exploration_type)
        else:
            self._record_failure(exploration_type)

    def _record_success(self, exploration_type: str) -> None:
        self.failure_counts[exploration_type] = 0
        if exploration_type in self.frozen_explorations:
            self.frozen_explorations.remove(exploration_type)
            logger.info(f"Exploration {exploration_type} unfrozen")

    def _record_failure(self, exploration_type: str) -> None:
        self.failure_counts[exploration_type] = self.failure_counts.get(exploration_type, 0) + 1
        if self.failure_counts[exploration_type] >= self.MAX_CONSECUTIVE_FAILURES:
            self._freeze_exploration(exploration_type)

    def _freeze_exploration(self, exploration_type: str) -> None:
        self.frozen_explorations.add(exploration_type)
        logger.warning(
            f"Exploration {exploration_type} frozen after "
            f"{self.MAX_CONSECUTIVE_FAILURES} failures"
        )

    def is_allowed(self, exploration_type: str) -> bool:
        """检查是否允许探索"""
        return exploration_type not in self.frozen_explorations


@dataclass
class GuardrailAuditEntry:
    """护栏审计条目"""
    timestamp: float
    operation: str
    allowed: bool
    reason: str
    severity: str


class GuardrailAuditLog:
    """
    护栏审计日志

    第一性原理：所有安全决策必须可追溯
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries = max_entries
        self.entries: List[GuardrailAuditEntry] = []

    def record(self, operation: str, result: GuardrailResult) -> None:
        """记录审计条目"""
        entry = GuardrailAuditEntry(
            timestamp=time.time(),
            operation=operation,
            allowed=result.allowed,
            reason=result.reason,
            severity=result.severity,
        )
        self.entries.append(entry)
        self._trim_entries()

    def _trim_entries(self) -> None:
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def query(self, allowed_only: bool = False, severity: str = None) -> List[GuardrailAuditEntry]:
        """查询审计日志"""
        results = self.entries
        if allowed_only:
            results = [e for e in results if e.allowed]
        if severity:
            results = [e for e in results if e.severity == severity]
        return results

    def get_stats(self) -> Dict[str, int]:
        """获取审计统计"""
        total = len(self.entries)
        blocked = sum(1 for e in self.entries if not e.allowed)
        return {"total": total, "blocked": blocked}


class RateLimiter:
    """
    速率限制器

    第一性原理：防止护栏自身成为系统瓶颈
    """

    def __init__(self, max_requests: int = 100, window_seconds: float = 1.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times: List[float] = []

    def _trim_window(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self.request_times = [t for t in self.request_times if t > cutoff]

    def allow(self) -> bool:
        """检查是否允许当前请求"""
        now = time.time()
        self._trim_window(now)
        if len(self.request_times) >= self.max_requests:
            return False
        self.request_times.append(now)
        return True

    def get_current_rate(self) -> int:
        """获取当前窗口内请求数"""
        self._trim_window(time.time())
        return len(self.request_times)


class CompositeGuardrail(GuardrailBase):
    """
    复合护栏策略

    第一性原理：安全决策需要多条件联合判断
    """

    def __init__(self, guardrails: List[GuardrailBase]) -> None:
        self.guardrails = guardrails

    def check_operation(self, operation: str) -> GuardrailResult:
        """检查操作是否允许（所有子护栏都必须通过）"""
        for guardrail in self.guardrails:
            result = guardrail.check_operation(operation)
            if not result.allowed:
                return result
        return GuardrailResult(allowed=True)

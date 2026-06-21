"""
API网关与外部接口系统

第一性原理：系统必须可被外部观测和交互，但必须有严格的访问控制
- 统一入口：所有外部请求通过网关
- 路由分发：根据路径路由到对应处理器
- 限流保护：防止外部请求压垮系统
- 健康暴露：提供标准化的健康检查接口

类比：生物的"感官门户"——眼睛、耳朵接收外部信息，
但大脑有注意力机制过滤无关刺激
"""

import json
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class HTTPStatus(Enum):
    """HTTP状态码简化"""
    OK = 200
    BAD_REQUEST = 400
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


@dataclass
class APIRequest:
    """API请求"""
    path: str
    method: str = "GET"
    params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None


@dataclass
class APIResponse:
    """API响应"""
    status: int
    data: Any = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": self.status}
        if self.error:
            result["error"] = self.error
        else:
            result["data"] = self.data
        return result


class RateLimiter:
    """
    令牌桶限流器

    第一性原理：资源有限，必须控制访问速率
    """

    def __init__(self, rate: float = 10.0, capacity: int = 20) -> None:
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_time = time.time()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """是否允许通过"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_time
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_time = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def get_status(self) -> Dict[str, float]:
        """获取限流器状态"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_time
            tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            return {
                "tokens": round(tokens, 2),
                "capacity": float(self.capacity),
                "rate": self.rate,
            }


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    熔断器

    第一性原理：故障传播必须被阻断
    - CLOSED: 正常通过
    - OPEN: 快速失败
    - HALF_OPEN: 试探性恢复

    类比：生物的"痛觉反射"——受伤部位自动回避，避免进一步损伤
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._init_thresholds(failure_threshold, recovery_timeout, half_open_max_calls)
        self._init_state()
        self._init_lock()

    def _init_thresholds(self, failure_threshold: int, recovery_timeout: float, half_open_max_calls: int) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

    def _init_state(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    def _init_lock(self) -> None:
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow(self) -> bool:
        """是否允许请求通过"""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return True
                return False
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            return False

    def _should_attempt_reset(self) -> bool:
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _transition_to_half_open(self) -> None:
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0

    def record_success(self) -> None:
        """记录成功"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._close_circuit()
            else:
                self._failure_count = 0

    def _close_circuit(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def record_failure(self) -> None:
        """记录失败"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._open_circuit()
            elif self._failure_count >= self.failure_threshold:
                self._open_circuit()

    def _open_circuit(self) -> None:
        self._state = CircuitState.OPEN
        self._half_open_calls = 0
        self._success_count = 0

    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_calls": self._half_open_calls,
            }


class APIGatewayBase(ABC):
    """API网关抽象基类"""

    @abstractmethod
    def register_handler(self, path: str, handler: Callable[[APIRequest], APIResponse]) -> None:
        """注册请求处理器"""
        pass

    @abstractmethod
    def handle(self, request: APIRequest) -> APIResponse:
        """处理请求"""
        pass


class APIGateway(APIGatewayBase):
    """
    API网关

    职责：
    1. 注册和管理API端点
    2. 请求路由和分发
    3. 限流保护
    4. 统一响应格式
    5. 请求日志记录

    第一性原理：
    - 单一入口：所有外部交互必须经过网关
    - fail-fast：非法请求尽早拒绝
    - 自我保护：过载时主动限流
    """

    def __init__(
        self,
        rate_limit: float = 50.0,
        rate_capacity: int = 100,
        enable_circuit_breaker: bool = True,
    ) -> None:
        self._handlers: Dict[str, Callable[[APIRequest], APIResponse]] = {}
        self._limiter = RateLimiter(rate=rate_limit, capacity=rate_capacity)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._enable_circuit_breaker = enable_circuit_breaker
        self._request_count = 0
        self._error_count = 0
        self._lock = threading.Lock()

    def register_handler(self, path: str, handler: Callable[[APIRequest], APIResponse]) -> None:
        """
        注册API处理器

        Args:
            path: API路径（如 /health, /metrics）
            handler: 处理函数，接收APIRequest返回APIResponse
        """
        if not path:
            raise ValueError("path must not be empty")
        if not callable(handler):
            raise ValueError("handler must be callable")

        with self._lock:
            self._handlers[path] = handler

    def unregister_handler(self, path: str) -> bool:
        """注销API处理器"""
        with self._lock:
            if path in self._handlers:
                del self._handlers[path]
                return True
            return False

    def _validate_request(self, request: APIRequest) -> Optional[APIResponse]:
        """验证请求合法性"""
        if not request.path:
            return APIResponse(
                status=HTTPStatus.BAD_REQUEST.value,
                error="path is required",
            )
        return None

    def _check_rate_limit(self) -> Optional[APIResponse]:
        """检查限流"""
        if not self._limiter.allow():
            return APIResponse(
                status=HTTPStatus.TOO_MANY_REQUESTS.value,
                error="rate limit exceeded",
            )
        return None

    def _find_handler(self, path: str) -> Optional[APIResponse]:
        """查找请求处理器"""
        handler = self._handlers.get(path)
        if not handler:
            return APIResponse(
                status=HTTPStatus.NOT_FOUND.value,
                error=f"path not found: {path}",
            )
        return handler

    def _get_circuit_breaker(self, path: str) -> CircuitBreaker:
        """获取路径对应的熔断器"""
        if path not in self._circuit_breakers:
            self._circuit_breakers[path] = CircuitBreaker()
        return self._circuit_breakers[path]

    def _check_circuit_breaker(self, path: str) -> Optional[APIResponse]:
        """检查熔断器状态"""
        if not self._enable_circuit_breaker:
            return None
        breaker = self._get_circuit_breaker(path)
        if not breaker.allow():
            return APIResponse(
                status=HTTPStatus.SERVICE_UNAVAILABLE.value,
                error="circuit breaker open",
            )
        return None

    def _record_handler_result(self, path: str, response: APIResponse) -> None:
        """记录handler执行结果到熔断器"""
        if not self._enable_circuit_breaker:
            return
        breaker = self._get_circuit_breaker(path)
        if response.status >= 500:
            breaker.record_failure()
        else:
            breaker.record_success()

    def _execute_handler(self, handler, request: APIRequest) -> APIResponse:
        """执行处理器并捕获异常"""
        try:
            return handler(request)
        except Exception as e:
            with self._lock:
                self._error_count += 1
            return APIResponse(
                status=HTTPStatus.INTERNAL_ERROR.value,
                error=str(e),
            )

    def _increment_request(self) -> None:
        with self._lock:
            self._request_count += 1

    def _route_and_execute(self, request: APIRequest) -> APIResponse:
        handler = self._find_handler(request.path)
        if isinstance(handler, APIResponse):
            return handler
        cb_error = self._check_circuit_breaker(request.path)
        if cb_error:
            return cb_error
        response = self._execute_handler(handler, request)
        self._record_handler_result(request.path, response)
        return response

    def handle(self, request: APIRequest) -> APIResponse:
        """
        处理API请求

        流程：
        1. 请求验证
        2. 限流检查
        3. 熔断检查
        4. 路由匹配
        5. 执行处理器
        6. 错误处理
        """
        validation_error = self._validate_request(request)
        if validation_error:
            return validation_error
        self._increment_request()
        rate_limit_error = self._check_rate_limit()
        if rate_limit_error:
            return rate_limit_error
        return self._route_and_execute(request)

    def get_registered_paths(self) -> List[str]:
        """获取已注册的路径列表"""
        with self._lock:
            return list(self._handlers.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取网关统计信息"""
        with self._lock:
            return {
                "registered_paths": len(self._handlers),
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "rate_limiter": self._limiter.get_status(),
                "circuit_breakers": {
                    path: cb.get_status()
                    for path, cb in self._circuit_breakers.items()
                },
            }

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._request_count = 0
            self._error_count = 0


def create_health_handler(system_status_fn: Callable[[], Dict[str, Any]]) -> Callable[[APIRequest], APIResponse]:
    """创建健康检查处理器"""
    def handler(request: APIRequest) -> APIResponse:
        status = system_status_fn()
        is_healthy = status.get("healthy", False)
        return APIResponse(
            status=HTTPStatus.OK.value if is_healthy else HTTPStatus.SERVICE_UNAVAILABLE.value,
            data=status,
        )
    return handler


def create_metrics_handler(metrics_fn: Callable[[], Dict[str, Any]]) -> Callable[[APIRequest], APIResponse]:
    """创建指标暴露处理器"""
    def handler(request: APIRequest) -> APIResponse:
        metrics = metrics_fn()
        return APIResponse(
            status=HTTPStatus.OK.value,
            data=metrics,
        )
    return handler


def create_status_handler(status_fn: Callable[[], Dict[str, Any]]) -> Callable[[APIRequest], APIResponse]:
    """创建系统状态处理器"""
    def handler(request: APIRequest) -> APIResponse:
        status = status_fn()
        return APIResponse(
            status=HTTPStatus.OK.value,
            data=status,
        )
    return handler

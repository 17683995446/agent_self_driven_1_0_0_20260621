"""
API网关测试

验证路由、限流、错误处理、处理器工厂函数
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import time

import pytest

from src.platform.support.infra.config.api_gateway import (
    APIGateway, APIGatewayBase, RateLimiter, CircuitBreaker, CircuitState,
    APIRequest, APIResponse, HTTPStatus,
    create_health_handler, create_metrics_handler, create_status_handler,
)


class TestAPIGatewayBase:
    """测试抽象基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            APIGatewayBase()


class TestRateLimiter:
    """测试限流器"""

    def test_allow_initial(self):
        limiter = RateLimiter(rate=10.0, capacity=5)
        assert limiter.allow() is True

    def test_allow_exhausted(self):
        limiter = RateLimiter(rate=0.1, capacity=1)
        assert limiter.allow() is True
        assert limiter.allow() is False

    def test_get_status(self):
        limiter = RateLimiter(rate=10.0, capacity=5)
        status = limiter.get_status()
        assert "tokens" in status
        assert "capacity" in status
        assert status["capacity"] == 5.0


class TestAPIResponse:
    """测试API响应"""

    def test_to_dict_with_data(self):
        resp = APIResponse(status=200, data={"key": "value"})
        d = resp.to_dict()
        assert d["status"] == 200
        assert d["data"]["key"] == "value"

    def test_to_dict_with_error(self):
        resp = APIResponse(status=500, error="fail")
        d = resp.to_dict()
        assert d["status"] == 500
        assert d["error"] == "fail"
        assert "data" not in d


class TestAPIGatewayInit:
    """测试网关初始化"""

    def test_normal_init(self):
        gateway = APIGateway()
        assert gateway.get_registered_paths() == []

    def test_custom_rate_limit(self):
        gateway = APIGateway(rate_limit=10.0, rate_capacity=5)
        stats = gateway.get_stats()
        assert stats["rate_limiter"]["rate"] == 10.0


class TestRegisterHandler:
    """测试注册处理器"""

    def test_register_and_handle(self):
        gateway = APIGateway()
        gateway.register_handler("/test", lambda req: APIResponse(status=200, data="ok"))
        resp = gateway.handle(APIRequest(path="/test"))
        assert resp.status == 200
        assert resp.data == "ok"

    def test_register_empty_path(self):
        gateway = APIGateway()
        with pytest.raises(ValueError):
            gateway.register_handler("", lambda req: APIResponse(status=200))

    def test_register_non_callable(self):
        gateway = APIGateway()
        with pytest.raises(ValueError):
            gateway.register_handler("/test", "not_callable")

    def test_unregister(self):
        gateway = APIGateway()
        gateway.register_handler("/test", lambda req: APIResponse(status=200))
        assert gateway.unregister_handler("/test") is True
        assert gateway.unregister_handler("/test") is False


class TestHandleRequests:
    """测试请求处理"""

    def test_empty_path(self):
        gateway = APIGateway()
        resp = gateway.handle(APIRequest(path=""))
        assert resp.status == HTTPStatus.BAD_REQUEST.value

    def test_not_found(self):
        gateway = APIGateway()
        resp = gateway.handle(APIRequest(path="/unknown"))
        assert resp.status == HTTPStatus.NOT_FOUND.value

    def test_handler_exception(self):
        gateway = APIGateway()
        gateway.register_handler("/fail", lambda req: 1 / 0)
        resp = gateway.handle(APIRequest(path="/fail"))
        assert resp.status == HTTPStatus.INTERNAL_ERROR.value
        assert "division" in resp.error

    def test_request_count(self):
        gateway = APIGateway()
        gateway.handle(APIRequest(path="/unknown"))
        stats = gateway.get_stats()
        assert stats["total_requests"] == 1

    def test_error_count(self):
        gateway = APIGateway()
        gateway.register_handler("/fail", lambda req: 1 / 0)
        gateway.handle(APIRequest(path="/fail"))
        stats = gateway.get_stats()
        assert stats["total_errors"] == 1


class TestRateLimiting:
    """测试限流"""

    def test_rate_limit_triggered(self):
        gateway = APIGateway(rate_limit=0.1, rate_capacity=1)
        gateway.register_handler("/api", lambda req: APIResponse(status=200))
        gateway.handle(APIRequest(path="/api"))
        resp = gateway.handle(APIRequest(path="/api"))
        assert resp.status == HTTPStatus.TOO_MANY_REQUESTS.value


class TestGetStats:
    """测试统计信息"""

    def test_stats_structure(self):
        gateway = APIGateway()
        gateway.register_handler("/a", lambda req: APIResponse(status=200))
        gateway.register_handler("/b", lambda req: APIResponse(status=200))
        stats = gateway.get_stats()
        assert stats["registered_paths"] == 2
        assert "rate_limiter" in stats

    def test_reset_stats(self):
        gateway = APIGateway()
        gateway.handle(APIRequest(path="/unknown"))
        gateway.reset_stats()
        stats = gateway.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0


class TestHealthHandler:
    """测试健康检查处理器工厂"""

    def test_healthy(self):
        handler = create_health_handler(lambda: {"healthy": True, "cpu": 0.5})
        resp = handler(APIRequest(path="/health"))
        assert resp.status == HTTPStatus.OK.value
        assert resp.data["healthy"] is True

    def test_unhealthy(self):
        handler = create_health_handler(lambda: {"healthy": False})
        resp = handler(APIRequest(path="/health"))
        assert resp.status == HTTPStatus.SERVICE_UNAVAILABLE.value


class TestMetricsHandler:
    """测试指标处理器工厂"""

    def test_metrics(self):
        handler = create_metrics_handler(lambda: {"latency_p99": 0.5})
        resp = handler(APIRequest(path="/metrics"))
        assert resp.status == HTTPStatus.OK.value
        assert resp.data["latency_p99"] == 0.5


class TestStatusHandler:
    """测试状态处理器工厂"""

    def test_status(self):
        handler = create_status_handler(lambda: {"cycle": 42})
        resp = handler(APIRequest(path="/status"))
        assert resp.status == HTTPStatus.OK.value
        assert resp.data["cycle"] == 42


class TestCircuitBreaker:
    """测试熔断器"""

    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow() is True

    def test_record_success_resets_failure(self):
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time
        time.sleep(0.02)
        assert cb.allow() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        cb.record_failure()
        import time
        time.sleep(0.02)
        cb.allow()
        cb.record_success()
        cb.allow()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        import time
        time.sleep(0.02)
        cb.allow()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_get_status(self):
        cb = CircuitBreaker()
        status = cb.get_status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    def test_boundary_threshold_exact(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_boundary_zero_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        time.sleep(0.01)
        assert cb.allow() is True

    def test_invalid_negative_threshold(self):
        cb = CircuitBreaker(failure_threshold=-1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerIntegration:
    """测试熔断器与网关集成"""

    def test_circuit_breaker_blocks_on_errors(self):
        gateway = APIGateway(enable_circuit_breaker=True)
        gateway.register_handler("/fail", lambda req: 1 / 0)
        for _ in range(5):
            gateway.handle(APIRequest(path="/fail"))
        resp = gateway.handle(APIRequest(path="/fail"))
        assert resp.status == HTTPStatus.SERVICE_UNAVAILABLE.value
        assert "circuit breaker open" in resp.error

    def test_circuit_breaker_disabled(self):
        gateway = APIGateway(enable_circuit_breaker=False)
        gateway.register_handler("/fail", lambda req: 1 / 0)
        for _ in range(10):
            resp = gateway.handle(APIRequest(path="/fail"))
        assert resp.status == HTTPStatus.INTERNAL_ERROR.value

    def test_circuit_breaker_in_stats(self):
        gateway = APIGateway()
        gateway.register_handler("/ok", lambda req: APIResponse(status=200))
        gateway.handle(APIRequest(path="/ok"))
        stats = gateway.get_stats()
        assert "circuit_breakers" in stats
        assert "/ok" in stats["circuit_breakers"]


class TestAPIRequest:
    """测试API请求"""

    def test_default_method(self):
        req = APIRequest(path="/test")
        assert req.method == "GET"
        assert req.params == {}
        assert req.body is None

    def test_with_body(self):
        req = APIRequest(path="/test", method="POST", body={"key": "value"})
        assert req.method == "POST"
        assert req.body["key"] == "value"

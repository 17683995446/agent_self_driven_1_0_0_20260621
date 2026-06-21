"""
O8：熔断器接入测试

验证DecisionEngine正确接入CircuitBreaker：
1. 未注入时向后兼容
2. 执行前检查熔断器
3. 执行后记录成功/失败
4. 连续失败触发熔断
5. 熔断期间任务被跳过
6. 异常处理
"""

import pytest
import time
from unittest.mock import MagicMock

from src.left.action.decision.decision import DecisionEngine
from src.platform.lifecycle.memory.guardrail import CircuitBreaker, CircuitState
from src.platform.support.models.base.task import Task, TaskResult, TaskPriority


def make_task(success=True, message="ok"):
    """创建测试任务"""
    def execute_fn():
        return TaskResult(success=success, message=message)
    return Task(
        name="test_task",
        description="test",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


class TestO8BackwardCompatibility:
    """测试未注入CircuitBreaker时的向后兼容"""

    def test_no_breaker_execute_succeeds(self):
        """未注入时正常执行"""
        engine = DecisionEngine()
        task = make_task(success=True)
        result = engine.execute_task(task)
        assert result.success is True

    def test_no_breaker_execute_failure(self):
        """未注入时执行失败也正常"""
        engine = DecisionEngine()
        task = make_task(success=False, message="fail")
        result = engine.execute_task(task)
        assert result.success is False


class TestO8CircuitBreakerCheck:
    """测试熔断器检查"""

    def test_closed_breaker_allows_execution(self):
        """关闭状态的熔断器允许执行"""
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(circuit_breaker=breaker)
        task = make_task(success=True)
        result = engine.execute_task(task)
        assert result.success is True

    def test_open_breaker_blocks_execution(self):
        """打开状态的熔断器阻止执行"""
        breaker = CircuitBreaker("test", failure_threshold=2)
        # 触发熔断
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        engine = DecisionEngine(circuit_breaker=breaker)
        task = make_task(success=True)
        result = engine.execute_task(task)
        assert result.success is False
        assert "Circuit breaker open" in result.message

    def test_blocked_task_message_contains_task_name(self):
        """被阻止的任务消息包含任务名"""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure()
        engine = DecisionEngine(circuit_breaker=breaker)
        task = make_task(success=True)
        task.name = "my_special_task"
        result = engine.execute_task(task)
        assert "my_special_task" in result.message


class TestO8CircuitBreakerRecording:
    """测试熔断器记录"""

    def test_success_records_to_breaker(self):
        """成功执行记录到熔断器"""
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(circuit_breaker=breaker)
        task = make_task(success=True)
        engine.execute_task(task)
        # 成功后failure_count应归零
        assert breaker.failure_count == 0

    def test_failure_records_to_breaker(self):
        """失败执行记录到熔断器"""
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(circuit_breaker=breaker)
        task = make_task(success=False)
        engine.execute_task(task)
        assert breaker.failure_count == 1

    def test_multiple_failures_accumulate(self):
        """多次失败累积"""
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(circuit_breaker=breaker)
        for _ in range(3):
            task = make_task(success=False)
            engine.execute_task(task)
        assert breaker.failure_count == 3


class TestO8CircuitTripping:
    """测试熔断触发"""

    def test_consecutive_failures_trip_breaker(self):
        """连续失败触发熔断"""
        breaker = CircuitBreaker("test", failure_threshold=3)
        engine = DecisionEngine(circuit_breaker=breaker)
        # 执行3次失败
        for _ in range(3):
            task = make_task(success=False)
            engine.execute_task(task)
        assert breaker.state == CircuitState.OPEN

    def test_tripped_breaker_blocks_subsequent_tasks(self):
        """熔断后阻止后续任务"""
        breaker = CircuitBreaker("test", failure_threshold=2)
        engine = DecisionEngine(circuit_breaker=breaker)
        # 触发熔断
        for _ in range(2):
            task = make_task(success=False)
            engine.execute_task(task)
        assert breaker.state == CircuitState.OPEN
        # 后续任务被阻止
        task = make_task(success=True)
        result = engine.execute_task(task)
        assert result.success is False
        assert "Circuit breaker open" in result.message

    def test_success_resets_failure_count(self):
        """成功重置失败计数"""
        breaker = CircuitBreaker("test", failure_threshold=3)
        engine = DecisionEngine(circuit_breaker=breaker)
        # 2次失败
        for _ in range(2):
            task = make_task(success=False)
            engine.execute_task(task)
        assert breaker.failure_count == 2
        # 1次成功
        task = make_task(success=True)
        engine.execute_task(task)
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_breaker_does_not_trip_with_mixed_results(self):
        """混合结果不触发熔断"""
        breaker = CircuitBreaker("test", failure_threshold=3)
        engine = DecisionEngine(circuit_breaker=breaker)
        # 失败、成功、失败、成功
        for success in [False, True, False, True]:
            task = make_task(success=success)
            engine.execute_task(task)
        assert breaker.state == CircuitState.CLOSED


class TestO8CircuitRecovery:
    """测试熔断恢复"""

    def test_breaker_recovers_after_timeout(self):
        """超时后熔断器恢复"""
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1,
        )
        engine = DecisionEngine(circuit_breaker=breaker)
        # 触发熔断
        task = make_task(success=False)
        engine.execute_task(task)
        assert breaker.state == CircuitState.OPEN
        # 等待恢复
        time.sleep(0.15)
        # 应该允许执行（进入HALF_OPEN）
        task = make_task(success=True)
        result = engine.execute_task(task)
        assert result.success is True

    def test_half_open_success_closes_breaker(self):
        """HALF_OPEN状态成功后关闭熔断器"""
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1,
            half_open_max_calls=1,
        )
        engine = DecisionEngine(circuit_breaker=breaker)
        # 触发熔断
        task = make_task(success=False)
        engine.execute_task(task)
        # 等待恢复
        time.sleep(0.15)
        # HALF_OPEN状态成功
        task = make_task(success=True)
        engine.execute_task(task)
        assert breaker.state == CircuitState.CLOSED


class TestO8ExceptionHandling:
    """测试异常处理"""

    def test_breaker_check_exception_handled(self):
        """熔断器检查异常被捕获"""
        mock_breaker = MagicMock()
        mock_breaker.can_execute.side_effect = RuntimeError("boom")
        engine = DecisionEngine(circuit_breaker=mock_breaker)
        task = make_task(success=True)
        # 不应抛异常，应继续执行
        result = engine.execute_task(task)
        assert result.success is True

    def test_breaker_record_exception_handled(self):
        """熔断器记录异常被捕获"""
        mock_breaker = MagicMock()
        mock_breaker.can_execute.return_value = True
        mock_breaker.record_success.side_effect = RuntimeError("boom")
        engine = DecisionEngine(circuit_breaker=mock_breaker)
        task = make_task(success=True)
        # 不应抛异常
        result = engine.execute_task(task)
        assert result.success is True

    def test_execute_exception_records_failure_to_breaker(self):
        """执行异常时记录失败到熔断器"""
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(circuit_breaker=breaker)
        def boom():
            raise RuntimeError("crash")
        task = Task(
            name="crashing_task",
            description="crashes",
            target_drive="safe",
            execute_fn=boom,
        )
        result = engine.execute_task(task)
        assert result.success is False
        assert breaker.failure_count == 1


class TestO8IntegrationWithFeedback:
    """测试熔断器与反馈学习器协同"""

    def test_breaker_and_learner_both_record(self):
        """熔断器和学习器都记录"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        learner = TaskFeedbackLearner()
        breaker = CircuitBreaker("test", failure_threshold=5)
        engine = DecisionEngine(
            circuit_breaker=breaker,
            feedback_learner=learner,
        )
        task = make_task(success=False)
        engine.execute_task(task)
        # 学习器记录了失败
        stats = learner.get_statistics(task.name)
        assert stats.failure_count == 1
        # 熔断器也记录了失败
        assert breaker.failure_count == 1

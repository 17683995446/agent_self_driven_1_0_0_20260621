"""
任务执行器 _wait_* 方法直接测试

覆盖 _wait_success、_wait_timeout、_wait_exception 路径
"""

import time
from concurrent.futures import Future

import pytest

from src.left.action.decision.executor import TaskExecutor, ExecutionStatus, ExecutionRecord
from src.platform.support.models.base.task import Task, TaskResult, TaskStatus


class TestWaitMethods:
    """测试 _wait_* 方法"""

    def test_wait_success_completed(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="ok")
        future = Future()
        future.set_result(TaskResult(success=True))
        record = executor._wait_success(task, future, time.time(), time.time())
        assert record.status == ExecutionStatus.COMPLETED
        assert record.result is not None
        assert record.result.success is True
        executor.shutdown()

    def test_wait_success_failed(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="fail")
        future = Future()
        future.set_result(TaskResult(success=False, message="failed"))
        record = executor._wait_success(task, future, time.time(), time.time())
        assert record.status == ExecutionStatus.FAILED
        assert record.error == "failed"
        executor.shutdown()

    def test_wait_timeout(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="to")
        future = Future()
        record = executor._wait_timeout(task, future, time.time(), time.time(), 0.5)
        assert record.status == ExecutionStatus.TIMEOUT
        assert "Timeout" in record.error
        executor.shutdown()

    def test_wait_exception(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="exc")
        record = executor._wait_exception(task, time.time(), time.time(), ValueError("boom"))
        assert record.status == ExecutionStatus.FAILED
        assert "boom" in record.error
        executor.shutdown()

    def test_wait_for_result_success(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="ok")
        future = Future()
        future.set_result(TaskResult(success=True))
        record = executor._wait_for_result(task, future, 1.0)
        assert record.status == ExecutionStatus.COMPLETED
        executor.shutdown()

    def test_wait_for_result_timeout(self):
        executor = TaskExecutor(max_workers=2, default_timeout=0.1)
        task = Task(name="slow")
        future = Future()
        # 不设置结果，让 future.result(timeout) 超时
        record = executor._wait_for_result(task, future, 0.01)
        assert record.status == ExecutionStatus.TIMEOUT
        executor.shutdown()

    def test_wait_for_result_exception(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="exc")
        future = Future()
        future.set_exception(RuntimeError("crash"))
        record = executor._wait_for_result(task, future, 1.0)
        assert record.status == ExecutionStatus.FAILED
        assert "crash" in record.error
        executor.shutdown()

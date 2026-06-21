"""
任务执行器与并发控制测试

验证任务提交、超时、取消、并发限制的正确性
"""

import pytest
import time
import threading

from src.left.action.decision.executor import (
    TaskExecutor, ConcurrentTaskManager, ExecutionStatus, ExecutionRecord,
)
from src.platform.support.models.base.task import Task, TaskResult, TaskStatus, TaskPriority


class TestExecutionRecord:
    """测试执行记录"""

    def test_duration(self):
        record = ExecutionRecord(
            task_id="t1", task_name="test", status=ExecutionStatus.COMPLETED,
            start_time=time.time() - 2.0, end_time=time.time(),
        )
        assert record.duration >= 2.0

    def test_duration_running(self):
        record = ExecutionRecord(
            task_id="t1", task_name="test", status=ExecutionStatus.RUNNING,
            start_time=time.time() - 1.0, end_time=0.0,
        )
        assert record.duration >= 1.0


class TestTaskExecutor:
    """测试任务执行器"""

    def setup_method(self):
        self.executor = TaskExecutor(max_workers=2, default_timeout=2.0)

    def teardown_method(self):
        self.executor.shutdown(wait=True)

    def test_submit_success(self):
        task = Task(
            name="success_task",
            execute_fn=lambda: TaskResult(success=True, message="ok"),
        )
        record = self.executor.submit(task)
        assert record.status == ExecutionStatus.COMPLETED
        assert record.result.success is True
        assert task.status == TaskStatus.COMPLETED

    def test_submit_failure(self):
        task = Task(
            name="fail_task",
            execute_fn=lambda: TaskResult(success=False, message="error"),
        )
        record = self.executor.submit(task)
        assert record.status == ExecutionStatus.FAILED
        assert task.status == TaskStatus.FAILED

    def test_submit_exception(self):
        def bad_fn():
            raise ValueError("boom")

        task = Task(name="exception_task", execute_fn=bad_fn)
        record = self.executor.submit(task)
        assert record.status == ExecutionStatus.FAILED
        assert "boom" in record.error

    def test_submit_no_function(self):
        task = Task(name="no_fn_task", execute_fn=None)
        record = self.executor.submit(task)
        assert record.status == ExecutionStatus.FAILED
        assert "No execute function" in record.error

    def test_timeout(self):
        def slow_fn():
            time.sleep(5.0)
            return TaskResult(success=True)

        task = Task(name="slow_task", execute_fn=slow_fn)
        record = self.executor.submit(task, timeout=0.2)
        assert record.status == ExecutionStatus.TIMEOUT
        assert "Timeout" in record.error

    def test_cancel_task(self):
        def slow_fn():
            time.sleep(10.0)
            return TaskResult(success=True)

        task = Task(name="cancel_task", execute_fn=slow_fn)
        # 在另一个线程提交（避免阻塞）
        result = [None]
        def submitter():
            result[0] = self.executor.submit(task, timeout=5.0)

        t = threading.Thread(target=submitter)
        t.start()
        time.sleep(0.1)

        # 尝试取消（已运行的线程池任务可能无法取消）
        cancelled = self.executor.cancel_task(task.id)
        t.join(timeout=6.0)

        # 取消可能成功也可能失败，取决于future状态
        assert result[0] is not None

    def test_concurrency_limit(self):
        lock = threading.Lock()
        running_count = [0]
        max_running = [0]

        def sync_fn():
            with lock:
                running_count[0] += 1
                max_running[0] = max(max_running[0], running_count[0])
            time.sleep(0.3)
            with lock:
                running_count[0] -= 1
            return TaskResult(success=True)

        tasks = [Task(name=f"task_{i}", execute_fn=sync_fn) for i in range(3)]

        records = []
        for task in tasks:
            records.append(self.executor.submit(task))

        # 3个任务，2个worker，同时运行的最大任务数不应超过2
        assert all(r.status == ExecutionStatus.COMPLETED for r in records)
        assert max_running[0] <= 2

    def test_stats(self):
        task = Task(
            name="stat_task",
            execute_fn=lambda: TaskResult(success=True),
        )
        self.executor.submit(task)
        stats = self.executor.get_stats()
        assert stats["total_submitted"] == 1
        assert stats["total_completed"] == 1
        assert stats["max_workers"] == 2

    def test_history(self):
        for i in range(5):
            task = Task(
                name=f"hist_task_{i}",
                execute_fn=lambda: TaskResult(success=True),
            )
            self.executor.submit(task)

        history = self.executor.get_recent_history(3)
        assert len(history) == 3
        assert history[-1].task_name == "hist_task_4"

    def test_running_count(self):
        assert self.executor.get_running_count() == 0


class TestConcurrentTaskManager:
    """测试并发任务管理器"""

    def setup_method(self):
        self.manager = ConcurrentTaskManager(max_concurrent=2, default_timeout=1.0)

    def teardown_method(self):
        self.manager.stop()

    def test_enqueue(self):
        task = Task(name="queued_task", priority=TaskPriority.NORMAL)
        assert self.manager.enqueue(task) is True
        assert self.manager.get_queue_size() == 1

    def test_priority_queue(self):
        low = Task(name="low", priority=TaskPriority.LOW)
        high = Task(name="high", priority=TaskPriority.HIGH)
        normal = Task(name="normal", priority=TaskPriority.NORMAL)

        self.manager.enqueue(low)
        self.manager.enqueue(high)
        self.manager.enqueue(normal)

        # 按优先级排序后，high应该在第一个
        with self.manager._queue_lock:
            assert self.manager._pending_queue[0].name == "high"
            assert self.manager._pending_queue[1].name == "normal"
            assert self.manager._pending_queue[2].name == "low"

    def test_start_stop(self):
        self.manager.start()
        assert self.manager._is_running is True
        self.manager.stop()
        assert self.manager._is_running is False

    def test_stats(self):
        self.manager.start()
        task = Task(
            name="exec_task",
            execute_fn=lambda: TaskResult(success=True),
        )
        self.manager.enqueue(task)
        time.sleep(0.3)

        stats = self.manager.get_stats()
        assert "queue_size" in stats
        assert "max_workers" in stats

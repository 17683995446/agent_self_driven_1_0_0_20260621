"""
任务执行器扩展测试

补充覆盖 get_stats、get_recent_history、shutdown、并发管理器等路径
"""

import pytest
import time

from src.left.action.decision.executor import (
    TaskExecutor, ConcurrentTaskManager, ExecutionStatus, ExecutionRecord,
    TaskExecutorBase,
)
from src.platform.support.models.base.task import Task, TaskResult, TaskStatus, TaskPriority


class TestTaskExecutorBase:
    """测试执行器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            TaskExecutorBase()


class TestTaskExecutorExtended:
    """测试任务执行器扩展路径"""

    def test_get_stats_empty(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        stats = executor.get_stats()
        assert stats["total_submitted"] == 0
        assert stats["running"] == 0
        executor.shutdown()

    def test_get_recent_history_empty(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        history = executor.get_recent_history(10)
        assert history == []
        executor.shutdown()

    def test_add_history_limit(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        executor._max_history = 3
        for i in range(5):
            record = ExecutionRecord(
                task_id=str(i), task_name=f"t{i}",
                status=ExecutionStatus.COMPLETED, start_time=time.time(),
            )
            executor._add_history(record)
        history = executor.get_recent_history(10)
        assert len(history) == 3
        executor.shutdown()

    def test_cancel_nonexistent_task(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        result = executor.cancel_task("nonexistent")
        assert result is False
        executor.shutdown()

    def test_submit_success_stats(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="ok", execute_fn=lambda: TaskResult(success=True))
        executor.submit(task)
        assert executor.total_completed == 1
        assert executor.total_submitted == 1
        executor.shutdown()

    def test_submit_failure_stats(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        task = Task(name="fail", execute_fn=lambda: TaskResult(success=False))
        executor.submit(task)
        assert executor.total_failed == 1
        executor.shutdown()

    def test_shutdown_no_wait(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        executor.shutdown(wait=False)

    def test_submit_task_with_exception(self):
        executor = TaskExecutor(max_workers=2, default_timeout=1.0)
        def bad_fn():
            raise ValueError("execution error")
        task = Task(name="exc", execute_fn=bad_fn)
        record = executor.submit(task)
        assert record.status == ExecutionStatus.FAILED
        assert "execution error" in record.error
        executor.shutdown()

    def test_submit_task_timeout(self):
        executor = TaskExecutor(max_workers=2, default_timeout=0.1)
        def slow_fn():
            time.sleep(2.0)
            return TaskResult(success=True)
        task = Task(name="slow", execute_fn=slow_fn)
        record = executor.submit(task)
        assert record.status == ExecutionStatus.TIMEOUT
        executor.shutdown()


class TestConcurrentTaskManagerExtended:
    """测试并发任务管理器扩展路径"""

    def test_get_queue_size_empty(self):
        manager = ConcurrentTaskManager(max_concurrent=1, default_timeout=1.0)
        assert manager.get_queue_size() == 0
        manager.stop()

    def test_enqueue_and_priority(self):
        manager = ConcurrentTaskManager(max_concurrent=1, default_timeout=1.0)
        manager.enqueue(Task(name="low", priority=TaskPriority.LOW))
        manager.enqueue(Task(name="high", priority=TaskPriority.HIGH))
        assert manager.get_queue_size() == 2
        manager.stop()

    def test_start_stop(self):
        manager = ConcurrentTaskManager(max_concurrent=1, default_timeout=1.0)
        manager.start()
        assert manager._is_running is True
        manager.stop()
        assert manager._is_running is False

    def test_get_stats(self):
        manager = ConcurrentTaskManager(max_concurrent=1, default_timeout=1.0)
        stats = manager.get_stats()
        assert "queue_size" in stats
        manager.stop()

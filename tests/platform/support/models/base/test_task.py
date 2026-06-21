"""
任务模型测试

验证任务创建、状态转换、任务池管理的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import time

import pytest

from src.platform.support.models.base.task import Task, TaskPool, TaskResult, TaskStatus, TaskPriority


class TestTaskInit:
    """测试任务初始化"""

    def test_normal_init(self):
        task = Task(name="test_task", priority=TaskPriority.HIGH)
        assert task.name == "test_task"
        assert task.status == TaskStatus.CREATED

    def test_empty_name(self):
        task = Task(name="", priority=TaskPriority.NORMAL)
        assert task.name == ""

    def test_boundary_priority(self):
        task = Task(name="test", priority=TaskPriority.LOW)
        assert task.priority == TaskPriority.LOW


class TestTaskStatusTransition:
    """测试任务状态转换"""

    def test_start_task(self):
        task = Task(name="test")
        task.start()
        assert task.status == TaskStatus.RUNNING

    def test_complete_task(self):
        task = Task(name="test")
        result = TaskResult(success=True, message="done")
        task.complete(result)
        assert task.status == TaskStatus.COMPLETED

    def test_fail_task(self):
        task = Task(name="test")
        result = TaskResult(success=False, message="error")
        task.complete(result)
        assert task.status == TaskStatus.FAILED


class TestTaskProperties:
    """测试任务属性"""

    def test_success_rate_default(self):
        task = Task(name="test")
        assert task.success_rate == 0.5

    def test_success_rate_after_success(self):
        task = Task(name="test")
        task.start()
        task.complete(TaskResult(success=True))
        assert task.success_rate == 1.0

    def test_average_reward_default(self):
        task = Task(name="test")
        assert task.average_reward == 0.0

    def test_average_reward_after_execution(self):
        task = Task(name="test")
        task.start()
        task.complete(TaskResult(success=True))
        assert task.average_reward == 0.0

    def test_is_expired_true(self):
        task = Task(name="test", deadline=1.0)
        assert task.is_expired is True

    def test_is_expired_false(self):
        task = Task(name="test", deadline=time.time() + 3600)
        assert task.is_expired is False

    def test_duration_not_started(self):
        task = Task(name="test")
        assert task.duration == 0.0

    def test_duration_started(self):
        task = Task(name="test")
        task.start()
        assert task.duration >= 0.0

    def test_cancel_task(self):
        task = Task(name="test")
        task.cancel()
        assert task.status == TaskStatus.CANCELLED

    def test_to_dict(self):
        task = Task(name="test", target_drive="gain")
        d = task.to_dict()
        assert d["name"] == "test"
        assert d["target_drive"] == "gain"


class TestTaskPool:
    """测试任务池"""

    def test_normal_add(self):
        pool = TaskPool()
        task = Task(name="test")
        assert pool.add_task(task) is True

    def test_get_task(self):
        pool = TaskPool()
        task = Task(name="test", priority=TaskPriority.HIGH)
        pool.add_task(task)
        fetched = pool.get_task(task.id)
        assert fetched is not None

    def test_empty_pool(self):
        pool = TaskPool()
        assert pool.get_task("missing") is None

    def test_capacity_limit(self):
        pool = TaskPool(max_size=2)
        pool.add_task(Task(name="a"))
        pool.add_task(Task(name="b"))
        result = pool.add_task(Task(name="c"))
        assert result is True  # 会淘汰最低价值的任务

    def test_remove_task(self):
        pool = TaskPool()
        task = Task(name="test")
        pool.add_task(task)
        pool.remove_task(task.id)
        assert pool.get_task(task.id) is None

    def test_get_pending_tasks(self):
        pool = TaskPool()
        pool.add_task(Task(name="a"))
        pool.add_task(Task(name="b"))
        assert len(pool.get_pending_tasks()) == 2

    def test_clear_completed(self):
        pool = TaskPool()
        task = Task(name="a")
        pool.add_task(task)
        task.complete(TaskResult(success=True))
        pool.clear_completed()
        assert len(pool.get_pending_tasks()) == 0

    def test_get_tasks_by_drive(self):
        pool = TaskPool()
        pool.add_task(Task(name="a", target_drive="safe"))
        pool.add_task(Task(name="b", target_drive="gain"))
        assert len(pool.get_tasks_by_drive("safe")) == 1

    def test_record_execution_trims_history(self):
        pool = TaskPool()
        for _ in range(1002):
            pool.record_execution(Task(name="x"))
        assert len(pool.execution_history) == 1000

    def test_evict_lowest_value_empty(self):
        pool = TaskPool()
        pool._evict_lowest_value()
        assert pool.size == 0

    def test_size_property(self):
        pool = TaskPool()
        pool.add_task(Task(name="a"))
        assert pool.size == 1

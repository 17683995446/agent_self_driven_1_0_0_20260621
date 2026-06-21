"""
任务生命周期状态机测试

验证状态转换规则、异常处理、边界条件
"""

import pytest
import time

from src.left.action.decision.task_lifecycle import TaskLifecycle, InvalidTransitionError
from src.platform.support.models.base.task import Task, TaskStatus
from src.platform.support.models.base.error_code import ValidationError


class TestTaskLifecycleTransitions:
    """测试状态转换"""

    def test_created_to_pending(self):
        """正常值：CREATED -> PENDING"""
        task = Task()
        assert task.status == TaskStatus.CREATED
        TaskLifecycle.transition(task, TaskStatus.PENDING)
        assert task.status == TaskStatus.PENDING

    def test_created_to_cancelled(self):
        """正常值：CREATED -> CANCELLED"""
        task = Task()
        TaskLifecycle.transition(task, TaskStatus.CANCELLED)
        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None

    def test_pending_to_running(self):
        """正常值：PENDING -> RUNNING"""
        task = Task(status=TaskStatus.PENDING)
        TaskLifecycle.transition(task, TaskStatus.RUNNING)
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None

    def test_running_to_completed(self):
        """正常值：RUNNING -> COMPLETED"""
        task = Task(status=TaskStatus.RUNNING)
        TaskLifecycle.transition(task, TaskStatus.COMPLETED)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_running_to_failed(self):
        """正常值：RUNNING -> FAILED"""
        task = Task(status=TaskStatus.RUNNING)
        TaskLifecycle.transition(task, TaskStatus.FAILED)
        assert task.status == TaskStatus.FAILED

    def test_failed_to_pending(self):
        """正常值：FAILED -> PENDING（重试）"""
        task = Task(status=TaskStatus.FAILED)
        TaskLifecycle.transition(task, TaskStatus.PENDING)
        assert task.status == TaskStatus.PENDING

    def test_pending_to_expired(self):
        """正常值：PENDING -> EXPIRED"""
        task = Task(status=TaskStatus.PENDING)
        TaskLifecycle.transition(task, TaskStatus.EXPIRED)
        assert task.status == TaskStatus.EXPIRED


class TestTaskLifecycleInvalidTransitions:
    """测试非法状态转换"""

    def test_completed_to_running(self):
        """非法：COMPLETED -> RUNNING"""
        task = Task(status=TaskStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            TaskLifecycle.transition(task, TaskStatus.RUNNING)

    def test_cancelled_to_pending(self):
        """非法：CANCELLED -> PENDING"""
        task = Task(status=TaskStatus.CANCELLED)
        with pytest.raises(InvalidTransitionError):
            TaskLifecycle.transition(task, TaskStatus.PENDING)

    def test_created_to_completed(self):
        """非法：CREATED -> COMPLETED"""
        task = Task()
        with pytest.raises(InvalidTransitionError):
            TaskLifecycle.transition(task, TaskStatus.COMPLETED)

    def test_running_to_pending(self):
        """非法：RUNNING -> PENDING"""
        task = Task(status=TaskStatus.RUNNING)
        with pytest.raises(InvalidTransitionError):
            TaskLifecycle.transition(task, TaskStatus.PENDING)

    def test_expired_to_any(self):
        """非法：EXPIRED -> 任何状态"""
        task = Task(status=TaskStatus.EXPIRED)
        for status in TaskStatus:
            if status != TaskStatus.EXPIRED:
                with pytest.raises(InvalidTransitionError):
                    TaskLifecycle.transition(task, status)


class TestTaskLifecycleUtilityMethods:
    """测试工具方法"""

    def test_can_transition_valid(self):
        """测试合法转换判断"""
        assert TaskLifecycle.can_transition(TaskStatus.CREATED, TaskStatus.PENDING)
        assert TaskLifecycle.can_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED)
        assert TaskLifecycle.can_transition(TaskStatus.FAILED, TaskStatus.PENDING)

    def test_can_transition_invalid(self):
        """测试非法转换判断"""
        assert not TaskLifecycle.can_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
        assert not TaskLifecycle.can_transition(TaskStatus.CANCELLED, TaskStatus.PENDING)
        assert not TaskLifecycle.can_transition(TaskStatus.CREATED, TaskStatus.COMPLETED)

    def test_get_allowed_transitions(self):
        """测试获取允许转换列表"""
        created_allowed = TaskLifecycle.get_allowed_transitions(TaskStatus.CREATED)
        assert TaskStatus.PENDING in created_allowed
        assert TaskStatus.CANCELLED in created_allowed
        assert len(created_allowed) == 2

        completed_allowed = TaskLifecycle.get_allowed_transitions(TaskStatus.COMPLETED)
        assert completed_allowed == []

    def test_is_terminal(self):
        """测试终态判断"""
        assert TaskLifecycle.is_terminal(TaskStatus.COMPLETED)
        assert TaskLifecycle.is_terminal(TaskStatus.CANCELLED)
        assert TaskLifecycle.is_terminal(TaskStatus.EXPIRED)
        assert not TaskLifecycle.is_terminal(TaskStatus.CREATED)
        assert not TaskLifecycle.is_terminal(TaskStatus.PENDING)
        assert not TaskLifecycle.is_terminal(TaskStatus.RUNNING)
        assert not TaskLifecycle.is_terminal(TaskStatus.FAILED)


class TestTaskLifecycleBoundaryConditions:
    """测试边界条件"""

    def test_empty_task(self):
        """空入参边界：默认状态"""
        task = Task()
        assert task.status == TaskStatus.CREATED
        allowed = TaskLifecycle.get_allowed_transitions(task.status)
        assert len(allowed) == 2

    def test_terminal_state_no_transitions(self):
        """边界极值：终态无出边"""
        for status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.EXPIRED]:
            task = Task(status=status)
            assert TaskLifecycle.get_allowed_transitions(status) == []
            assert TaskLifecycle.is_terminal(status)

    def test_running_has_three_exits(self):
        """边界极值：RUNNING有3个出口"""
        exits = TaskLifecycle.get_allowed_transitions(TaskStatus.RUNNING)
        assert len(exits) == 3
        assert TaskStatus.COMPLETED in exits
        assert TaskStatus.FAILED in exits
        assert TaskStatus.CANCELLED in exits

    def test_timestamp_recording(self):
        """边界：时间戳记录"""
        task = Task(status=TaskStatus.PENDING)
        before = time.time()
        TaskLifecycle.transition(task, TaskStatus.RUNNING)
        after = time.time()
        assert before <= task.started_at <= after

        before = time.time()
        TaskLifecycle.transition(task, TaskStatus.COMPLETED)
        after = time.time()
        assert before <= task.completed_at <= after


class TestTaskLifecycleInvalidInputs:
    """测试非法格式输入"""

    def test_invalid_status_type(self):
        """非法格式：状态类型错误"""
        with pytest.raises(ValidationError):
            TaskLifecycle.validate_task_status("invalid")

    def test_none_status(self):
        """空入参：None状态"""
        with pytest.raises(ValidationError):
            TaskLifecycle.validate_task_status(None)

    def test_integer_status(self):
        """非法格式：整数作为状态"""
        with pytest.raises(ValidationError):
            TaskLifecycle.validate_task_status(1)

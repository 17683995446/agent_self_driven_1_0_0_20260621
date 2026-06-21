"""
任务中断机制测试

验证中断规则、恢复机制、边界条件
"""

import pytest

from src.left.action.decision.task_interrupt import TaskInterruptHandler, TaskContext
from src.platform.support.models.base.task import Task, TaskPriority
from src.platform.support.models.base.state import GapState


class TestTaskInterruptCanInterrupt:
    """测试中断判断"""

    def setup_method(self):
        self.handler = TaskInterruptHandler()

    def test_safety_override(self):
        """正常值：安全任务可中断非安全任务"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="safe", target_drive="safe")
        gaps = GapState(safety=0.6, gain=0.2, efficiency=0.1)
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_safety_override_low_gap(self):
        """边界：安全缺口不足时不中断"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="safe", target_drive="safe")
        gaps = GapState(safety=0.3, gain=0.2, efficiency=0.1)
        assert not self.handler.can_interrupt(current, new_task, gaps)

    def test_gap_dominant(self):
        """正常值：新任务缺口是当前的2倍以上"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.8, gain=0.3, efficiency=0.1)
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_gap_not_dominant(self):
        """正常值：新任务缺口不够大"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.1)
        assert not self.handler.can_interrupt(current, new_task, gaps)

    def test_urgency_override(self):
        """正常值：紧急任务可中断非紧急任务"""
        current = Task(name="current", target_drive="gain", priority=TaskPriority.NORMAL)
        new_task = Task(name="urgent", target_drive="gain", priority=TaskPriority.CRITICAL)
        gaps = GapState(safety=0.3, gain=0.3, efficiency=0.3)
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_same_priority_no_interrupt(self):
        """正常值：同优先级不中断"""
        current = Task(name="current", target_drive="gain", priority=TaskPriority.NORMAL)
        new_task = Task(name="new", target_drive="gain", priority=TaskPriority.NORMAL)
        gaps = GapState(safety=0.3, gain=0.3, efficiency=0.3)
        assert not self.handler.can_interrupt(current, new_task, gaps)

    def test_safe_to_safe_no_interrupt(self):
        """正常值：安全任务不中断安全任务"""
        current = Task(name="current", target_drive="safe")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.8, gain=0.2, efficiency=0.1)
        assert not self.handler.can_interrupt(current, new_task, gaps)


class TestTaskInterruptExecution:
    """测试中断执行"""

    def setup_method(self):
        self.handler = TaskInterruptHandler()

    def test_interrupt_saves_context(self):
        """正常值：中断保存上下文"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        context = self.handler.interrupt(current, new_task)
        assert isinstance(context, TaskContext)
        assert context.task == current
        assert self.handler.current_task == new_task
        assert self.handler.interrupt_count == 1

    def test_resume_restores_task(self):
        """正常值：恢复被中断的任务"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        self.handler.interrupt(current, new_task)
        resumed = self.handler.resume()
        assert resumed == current
        assert self.handler.current_task == current
        assert self.handler.interrupt_count == 0

    def test_resume_empty_stack(self):
        """空入参：空栈恢复返回None"""
        assert self.handler.resume() is None

    def test_multiple_interrupts(self):
        """正常值：多层中断"""
        task1 = Task(name="t1", target_drive="gain")
        task2 = Task(name="t2", target_drive="safe")
        task3 = Task(name="t3", target_drive="eff")
        self.handler.interrupt(task1, task2)
        self.handler.interrupt(task2, task3)
        assert self.handler.interrupt_count == 2
        assert self.handler.current_task == task3
        resumed = self.handler.resume()
        assert resumed == task2
        assert self.handler.interrupt_count == 1

    def test_clear_stack(self):
        """正常值：清空中断栈"""
        task1 = Task(name="t1", target_drive="gain")
        task2 = Task(name="t2", target_drive="safe")
        self.handler.interrupt(task1, task2)
        self.handler.clear()
        assert self.handler.interrupt_count == 0
        assert self.handler.current_task is None


class TestTaskInterruptBoundaryConditions:
    """测试边界条件"""

    def setup_method(self):
        self.handler = TaskInterruptHandler()

    def test_exact_gap_ratio_threshold(self):
        """边界极值：恰好等于2倍阈值（同时触发安全覆盖）"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.6, gain=0.3, efficiency=0.1)
        # safety=0.6 > 0.5 阈值，触发安全覆盖
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_just_above_gap_ratio(self):
        """边界极值：略高于2倍阈值"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.61, gain=0.3, efficiency=0.1)
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_zero_gaps(self):
        """边界极值：所有缺口为零"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="new", target_drive="safe")
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        assert not self.handler.can_interrupt(current, new_task, gaps)

    def test_critical_interrupts_normal(self):
        """边界：CRITICAL可中断NORMAL"""
        current = Task(name="current", priority=TaskPriority.NORMAL)
        new_task = Task(name="new", priority=TaskPriority.CRITICAL)
        gaps = GapState(safety=0.1, gain=0.1, efficiency=0.1)
        assert self.handler.can_interrupt(current, new_task, gaps)

    def test_normal_does_not_interrupt_critical(self):
        """边界：NORMAL不可中断CRITICAL"""
        current = Task(name="current", priority=TaskPriority.CRITICAL)
        new_task = Task(name="new", priority=TaskPriority.NORMAL)
        gaps = GapState(safety=0.1, gain=0.1, efficiency=0.1)
        assert not self.handler.can_interrupt(current, new_task, gaps)

    def test_get_stack_returns_copy(self):
        """边界：get_stack返回副本"""
        task1 = Task(name="t1")
        task2 = Task(name="t2")
        self.handler.interrupt(task1, task2)
        stack = self.handler.get_stack()
        assert len(stack) == 1
        stack.clear()
        assert self.handler.interrupt_count == 1


class TestTaskInterruptInvalidInputs:
    """测试非法输入"""

    def setup_method(self):
        self.handler = TaskInterruptHandler()

    def test_unknown_drive_gap(self):
        """非法格式：未知驱力类型返回0.0"""
        task = Task(name="unknown", target_drive="unknown")
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        gap = self.handler._get_gap_for_task(task, gaps)
        assert gap == 0.0

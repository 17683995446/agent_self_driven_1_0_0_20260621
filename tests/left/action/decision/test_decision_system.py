"""
决策系统集成测试

验证决策引擎各组件的协同工作
"""

import pytest

from src.left.action.decision.task_lifecycle import TaskLifecycle, InvalidTransitionError
from src.left.action.decision.task_scorer import StandardTaskScorer
from src.left.action.decision.exploration_policy import EpsilonGreedyPolicy
from src.left.action.decision.task_interrupt import TaskInterruptHandler
from src.left.action.decision.decision_audit import DecisionAuditLog
from src.left.action.decision.task_dependency import StandardTaskDependencyManager
from src.left.action.decision.task_resource_budget import TaskResourceBudget
from src.platform.support.models.base.task import Task, TaskStatus, TaskPriority
from src.platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class TestDecisionSystemIntegration:
    """决策系统集成测试"""

    def setup_method(self):
        self.gaps = GapState(safety=0.8, gain=0.2, efficiency=0.1)
        self.weights = DriveWeights(safe=0.5, gain=0.3, eff=0.2)
        self.state = EnvironmentState()
        self.scorer = StandardTaskScorer()
        self.policy = EpsilonGreedyPolicy(epsilon=0.0)
        self.interrupt = TaskInterruptHandler()
        self.audit = DecisionAuditLog()
        self.dependency = StandardTaskDependencyManager()
        self.budget = TaskResourceBudget(total_cpu=0.5, total_memory=0.5)

    def test_task_selection_prefers_high_gap(self):
        """正常值：高缺口任务被优先选择"""
        safe_task = Task(name="safe_task", target_drive="safe", priority=TaskPriority.NORMAL)
        gain_task = Task(name="gain_task", target_drive="gain", priority=TaskPriority.NORMAL)
        safe_score = self.scorer.score(safe_task, self.gaps, self.weights, self.state)
        gain_score = self.scorer.score(gain_task, self.gaps, self.weights, self.state)
        assert safe_score > gain_score

    def test_task_selection_with_policy(self):
        """正常值：策略选择最高分任务"""
        safe_task = Task(name="safe_task", target_drive="safe")
        gain_task = Task(name="gain_task", target_drive="gain")
        safe_score = self.scorer.score(safe_task, self.gaps, self.weights, self.state)
        gain_score = self.scorer.score(gain_task, self.gaps, self.weights, self.state)
        scored = [(safe_score, safe_task), (gain_score, gain_task)]
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected == safe_task

    def test_interrupt_safety_override(self):
        """正常值：安全任务可中断非安全任务"""
        current = Task(name="current", target_drive="gain")
        new_task = Task(name="safe", target_drive="safe")
        assert self.interrupt.can_interrupt(current, new_task, self.gaps)

    def test_lifecycle_transition_to_running(self):
        """正常值：生命周期转换到运行态"""
        task = Task(status=TaskStatus.PENDING)
        TaskLifecycle.transition(task, TaskStatus.RUNNING)
        assert task.status == TaskStatus.RUNNING

    def test_audit_logs_decision(self):
        """正常值：审计记录决策"""
        task = Task(name="test", target_drive="safe")
        self.audit.log_decision(self.gaps, self.weights, [task], task, False, 0.9)
        assert self.audit.get_entry_count() == 1
        entry = self.audit.get_entries()[0]
        assert entry.selected_task_name == "test"

    def test_dependency_enforces_order(self):
        """正常值：依赖管理强制执行顺序"""
        t1 = Task(id="t1", name="t1")
        t2 = Task(id="t2", name="t2")
        self.dependency.add_dependency("t2", "t1")
        assert not self.dependency.can_execute("t2", set())
        assert self.dependency.can_execute("t2", {"t1"})

    def test_budget_limits_resources(self):
        """正常值：预算限制资源使用"""
        task = Task(name="big", max_cpu_usage=1.0, max_memory_usage=1.0)
        alloc = self.budget.allocate(task)
        assert not alloc.approved
        assert alloc.cpu <= self.budget.total_cpu

    def test_full_decision_pipeline(self):
        """正常值：完整决策流水线"""
        tasks = [
            Task(name="safe", target_drive="safe", status=TaskStatus.PENDING),
            Task(name="gain", target_drive="gain", status=TaskStatus.PENDING),
        ]
        scored = [(self.scorer.score(t, self.gaps, self.weights, self.state), t) for t in tasks]
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = self.policy.select_task(scored, self.gaps, self.weights)
        assert selected is not None
        TaskLifecycle.transition(selected, TaskStatus.RUNNING)
        alloc = self.budget.allocate(selected)
        self.audit.log_decision(self.gaps, self.weights, tasks, selected, False, scored[0][0])
        assert selected.status == TaskStatus.RUNNING
        assert self.audit.get_entry_count() == 1


class TestDecisionSystemBoundaryConditions:
    """测试边界条件"""

    def test_empty_task_list(self):
        """空入参：空任务列表"""
        policy = EpsilonGreedyPolicy(epsilon=0.0)
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        selected = policy.select_task([], gaps, weights)
        assert selected is None

    def test_single_task(self):
        """边界：单个任务"""
        task = Task(name="only", target_drive="safe")
        scorer = StandardTaskScorer()
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        state = EnvironmentState()
        score = scorer.score(task, gaps, weights, state)
        assert 0.0 <= score <= 1.0

    def test_all_tasks_same_drive(self):
        """边界：所有任务同驱力"""
        tasks = [Task(name=f"t{i}", target_drive="safe") for i in range(5)]
        scorer = StandardTaskScorer()
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        state = EnvironmentState()
        scores = [scorer.score(t, gaps, weights, state) for t in tasks]
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_zero_gaps(self):
        """边界极值：所有缺口为零"""
        task = Task(name="task", target_drive="safe")
        scorer = StandardTaskScorer()
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        state = EnvironmentState()
        score = scorer.score(task, gaps, weights, state)
        assert 0.0 <= score <= 1.0


class TestDecisionSystemInvalidInputs:
    """测试非法输入"""

    def test_invalid_lifecycle_transition(self):
        """非法格式：非法状态转换"""
        task = Task(status=TaskStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            TaskLifecycle.transition(task, TaskStatus.RUNNING)

    def test_cycle_in_dependencies(self):
        """非法格式：循环依赖"""
        manager = StandardTaskDependencyManager()
        manager.add_dependency("t1", "t2")
        manager.add_dependency("t2", "t1")
        assert manager.has_cycle()

    def test_negative_budget_allocation(self):
        """非法格式：负预算"""
        budget = TaskResourceBudget(total_cpu=-0.1, total_memory=-0.1)
        task = Task(name="task", max_cpu_usage=0.1)
        alloc = budget.allocate(task)
        assert alloc.cpu <= 0.0
        assert not alloc.approved

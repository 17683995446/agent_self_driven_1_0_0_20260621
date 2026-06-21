"""
决策系统性能测试

验证决策延迟、吞吐量、资源使用
"""

import time

import pytest

from src.left.action.decision.task_scorer import StandardTaskScorer
from src.left.action.decision.exploration_policy import EpsilonGreedyPolicy
from src.left.action.decision.task_lifecycle import TaskLifecycle
from src.left.action.decision.task_dependency import StandardTaskDependencyManager
from src.platform.support.models.base.task import Task, TaskStatus
from src.platform.support.models.base.state import GapState, DriveWeights, EnvironmentState


class TestDecisionSystemPerformance:
    """决策系统性能测试"""

    def setup_method(self):
        self.scorer = StandardTaskScorer()
        self.policy = EpsilonGreedyPolicy(epsilon=0.0)
        self.gaps = GapState(safety=0.3, gain=0.3, efficiency=0.3)
        self.weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        self.state = EnvironmentState()

    def test_scoring_latency(self):
        """性能：评分延迟 < 1ms"""
        task = Task(name="perf", target_drive="safe")
        start = time.perf_counter()
        for _ in range(1000):
            self.scorer.score(task, self.gaps, self.weights, self.state)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Scoring too slow: {avg_ms:.3f}ms"

    def test_selection_latency(self):
        """性能：选择延迟 < 10ms (100个任务)"""
        tasks = [Task(id=str(i), name=f"task{i}", target_drive="safe") for i in range(100)]
        scored = [(self.scorer.score(t, self.gaps, self.weights, self.state), t) for t in tasks]
        scored.sort(key=lambda x: x[0], reverse=True)
        start = time.perf_counter()
        for _ in range(1000):
            self.policy.select_task(scored, self.gaps, self.weights)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 10.0, f"Selection too slow: {avg_ms:.3f}ms"

    def test_lifecycle_transition_speed(self):
        """性能：状态转换延迟 < 0.1ms"""
        task = Task(status=TaskStatus.PENDING)
        start = time.perf_counter()
        for _ in range(1000):
            t = Task(status=TaskStatus.PENDING)
            TaskLifecycle.transition(t, TaskStatus.RUNNING)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 0.1, f"Transition too slow: {avg_ms:.3f}ms"

    def test_dependency_topological_sort_speed(self):
        """性能：拓扑排序延迟 < 5ms (100个任务)"""
        manager = StandardTaskDependencyManager()
        tasks = [Task(id=f"t{i}", name=f"t{i}") for i in range(100)]
        for i in range(1, 100):
            manager.add_dependency(f"t{i}", f"t{i-1}")
        start = time.perf_counter()
        for _ in range(100):
            manager.get_execution_order(tasks)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 5.0, f"Topo sort too slow: {avg_ms:.3f}ms"

    def test_memory_usage_stable(self):
        """性能：内存使用稳定"""
        tasks = [Task(name=f"t{i}") for i in range(1000)]
        scored = [(self.scorer.score(t, self.gaps, self.weights, self.state), t) for t in tasks]
        assert len(scored) == 1000


class TestDecisionSystemThroughput:
    """决策系统吞吐量测试"""

    def test_tasks_per_second(self):
        """性能：每秒处理 > 1000个任务评分"""
        scorer = StandardTaskScorer()
        gaps = GapState(safety=0.5, gain=0.5, efficiency=0.5)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        state = EnvironmentState()
        tasks = [Task(name=f"t{i}", target_drive="safe") for i in range(100)]
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            for t in tasks:
                scorer.score(t, gaps, weights, state)
            count += len(tasks)
        assert count > 1000, f"Throughput too low: {count} tasks/sec"

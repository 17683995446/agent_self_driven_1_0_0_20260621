"""
决策引擎扩展测试

补充覆盖 execute_task、update_exploration_ratio、各类任务生成路径
"""

import pytest

from src.left.action.decision.decision import DecisionEngine, DecisionEngineBase
from src.platform.support.models.base.state import EnvironmentState, GapState, DriveWeights
from src.platform.support.models.base.task import Task, TaskPool, TaskPriority, TaskResult


class TestDecisionEngineExtended:
    """测试决策引擎扩展路径"""

    def test_generate_tasks_safety_only(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.8, gain=0.0, efficiency=0.0)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) > 0

    def test_generate_tasks_gain_only(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.0, gain=0.8, efficiency=0.0)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) > 0

    def test_generate_tasks_eff_only(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.8)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) > 0

    def test_generate_tasks_fallback(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) > 0

    def test_select_next_task_empty_pool(self):
        engine = DecisionEngine()
        pool = TaskPool()
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        weights = DriveWeights()
        task = engine.select_next_task(pool, gaps, weights)
        assert task is not None

    def test_score_task_exploration(self):
        engine = DecisionEngine()
        task = Task(name="explore", priority=TaskPriority.EXPLORATION, is_exploration=True)
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        weights = DriveWeights()
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_execute_task_success(self):
        engine = DecisionEngine()
        task = Task(name="test", execute_fn=lambda: TaskResult(success=True))
        result = engine.execute_task(task)
        assert result.success is True

    def test_execute_task_no_fn(self):
        engine = DecisionEngine()
        task = Task(name="test")
        result = engine.execute_task(task)
        assert result.success is False

    def test_update_exploration_ratio_stagnation(self):
        engine = DecisionEngine()
        engine.update_exploration_ratio(0.0, stagnation_detected=True)
        assert engine.current_exploration_ratio > engine.base_exploration_ratio

    def test_update_exploration_ratio_error_trend(self):
        engine = DecisionEngine()
        engine.update_exploration_ratio(1.0)
        assert engine.current_exploration_ratio < engine.base_exploration_ratio

    def test_exploration_count_increment(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 1.0
        pool = TaskPool()
        pool.add_task(Task(name="a", priority=TaskPriority.LOW))
        pool.add_task(Task(name="b", priority=TaskPriority.LOW))
        pool.add_task(Task(name="c", priority=TaskPriority.LOW))
        engine.select_next_task(pool, GapState(), DriveWeights())
        assert engine.exploration_count >= 1

    def test_exploitation_count_increment(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 0.0
        pool = TaskPool()
        pool.add_task(Task(name="a", priority=TaskPriority.LOW))
        engine.select_next_task(pool, GapState(), DriveWeights())
        assert engine.exploitation_count >= 1

    def test_score_task_safety(self):
        engine = DecisionEngine()
        task = Task(name="safety_task", priority=TaskPriority.HIGH, is_exploration=False)
        gaps = GapState(safety=0.8, gain=0.1, efficiency=0.1)
        weights = DriveWeights(safe=0.6, gain=0.2, eff=0.2)
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_score_task_gain(self):
        engine = DecisionEngine()
        task = Task(name="gain_task", priority=TaskPriority.NORMAL, is_exploration=False)
        gaps = GapState(safety=0.1, gain=0.8, efficiency=0.1)
        weights = DriveWeights(safe=0.2, gain=0.6, eff=0.2)
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_score_task_efficiency(self):
        engine = DecisionEngine()
        task = Task(name="eff_task", priority=TaskPriority.LOW, is_exploration=False)
        gaps = GapState(safety=0.1, gain=0.1, efficiency=0.8)
        weights = DriveWeights(safe=0.2, gain=0.2, eff=0.6)
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_compute_gap_match_safe(self):
        engine = DecisionEngine()
        task = Task(name="t", target_drive="safe")
        gaps = GapState(safety=0.7)
        assert engine._compute_gap_match(task, gaps) == 0.7

    def test_compute_gap_match_gain(self):
        engine = DecisionEngine()
        task = Task(name="t", target_drive="gain")
        gaps = GapState(gain=0.6)
        assert engine._compute_gap_match(task, gaps) == 0.6

    def test_compute_gap_match_eff(self):
        engine = DecisionEngine()
        task = Task(name="t", target_drive="eff")
        gaps = GapState(efficiency=0.5)
        assert engine._compute_gap_match(task, gaps) == 0.5

    def test_compute_gap_match_unknown(self):
        engine = DecisionEngine()
        task = Task(name="t", target_drive="unknown")
        gaps = GapState()
        assert engine._compute_gap_match(task, gaps) == 0.0

    def test_compute_urgency_critical(self):
        engine = DecisionEngine()
        task = Task(name="t", priority=TaskPriority.CRITICAL)
        urgency = engine._compute_urgency(task)
        assert urgency == 1.0

    def test_compute_urgency_low(self):
        engine = DecisionEngine()
        task = Task(name="t", priority=TaskPriority.LOW)
        urgency = engine._compute_urgency(task)
        assert urgency == 0.25

    def test_compute_novelty_exploration(self):
        engine = DecisionEngine()
        task = Task(name="t", is_exploration=True)
        assert engine._compute_novelty(task) == 0.3

    def test_compute_novelty_normal(self):
        engine = DecisionEngine()
        task = Task(name="t", is_exploration=False)
        assert engine._compute_novelty(task) == 0.0

    def test_compute_cost(self):
        engine = DecisionEngine()
        task = Task(name="t", max_cpu_usage=0.1, max_memory_usage=0.2)
        assert abs(engine._compute_cost(task) - 0.15) < 0.001

    def test_score_task_expired_bonus(self):
        engine = DecisionEngine()
        task = Task(name="t", deadline=1.0)
        score = engine.score_task(task, GapState(), DriveWeights())
        assert 0.0 <= score <= 1.0

    def test_execute_task_exception(self):
        engine = DecisionEngine()
        def bad_fn():
            raise ValueError("exec error")
        task = Task(name="test", execute_fn=bad_fn)
        result = engine.execute_task(task)
        assert result.success is False
        assert "exec error" in result.message

    def test_explore_select_empty(self):
        engine = DecisionEngine()
        result = engine._explore_select([])
        assert result is None

    def test_get_pending_or_generate(self):
        engine = DecisionEngine()
        pool = TaskPool()
        tasks = engine._get_pending_or_generate(pool, GapState(safety=0.5))
        assert len(tasks) > 0

    def test_score_tasks(self):
        engine = DecisionEngine()
        tasks = [Task(name="a"), Task(name="b")]
        scored = engine._score_tasks(tasks, GapState(), DriveWeights())
        assert len(scored) == 2
        assert scored[0][0] >= scored[1][0]

    def test_create_safety_tasks_high_gap(self):
        engine = DecisionEngine()
        tasks = engine._create_safety_tasks(GapState(safety=0.8), EnvironmentState())
        assert any(t.priority == TaskPriority.HIGH for t in tasks)

    def test_create_safety_tasks_low_gap(self):
        engine = DecisionEngine()
        tasks = engine._create_safety_tasks(GapState(safety=0.2), EnvironmentState())
        assert all(t.priority != TaskPriority.HIGH for t in tasks)

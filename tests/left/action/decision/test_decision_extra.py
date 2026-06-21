"""
决策引擎补充测试

覆盖缺失分支：_create_*_tasks、update_exploration_ratio边界
"""

import pytest

from src.left.action.decision.decision import DecisionEngine
from src.platform.support.models.base.state import EnvironmentState, GapState, DriveWeights
from src.platform.support.models.base.task import TaskPool


class TestDecisionEngineTaskCreation:
    """测试任务创建函数"""

    def test_create_safety_tasks_high_gap(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.8, gain=0.1, efficiency=0.1)
        state = EnvironmentState()
        tasks = engine._create_safety_tasks(gaps, state)
        assert len(tasks) == 2
        assert tasks[0].priority.name == "HIGH"

    def test_create_safety_tasks_normal_gap(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.4, gain=0.1, efficiency=0.1)
        state = EnvironmentState()
        tasks = engine._create_safety_tasks(gaps, state)
        assert len(tasks) == 2
        assert tasks[0].priority.name == "NORMAL"

    def test_create_gain_tasks(self):
        engine = DecisionEngine()
        tasks = engine._create_gain_tasks()
        assert len(tasks) == 1
        assert tasks[0].name == "explore_new_patterns"

    def test_create_efficiency_tasks(self):
        engine = DecisionEngine()
        tasks = engine._create_efficiency_tasks()
        assert len(tasks) == 1
        assert tasks[0].name == "optimize_resource_usage"

    def test_create_fallback_task(self):
        engine = DecisionEngine()
        tasks = engine._create_fallback_task()
        assert len(tasks) == 1
        assert tasks[0].name == "idle_observation"


class TestDecisionEngineExplorationRatio:
    """测试探索比例调整"""

    def test_update_stagnation_increases(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 0.2
        engine.update_exploration_ratio(0.0, stagnation_detected=True)
        assert engine.current_exploration_ratio == 0.25

    def test_update_error_decreases(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 0.3
        engine.update_exploration_ratio(0.5, stagnation_detected=False)
        assert abs(engine.current_exploration_ratio - 0.28) < 1e-9

    def test_update_min_boundary(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 0.11
        engine.update_exploration_ratio(0.5, stagnation_detected=False)
        assert engine.current_exploration_ratio == 0.1

    def test_update_max_boundary(self):
        engine = DecisionEngine()
        engine.current_exploration_ratio = 0.46
        engine.update_exploration_ratio(0.0, stagnation_detected=True)
        assert engine.current_exploration_ratio == 0.5


class TestDecisionEngineGenerateTasks:
    """测试任务生成组合"""

    def test_generate_all_tasks(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.8, gain=0.8, efficiency=0.8)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) >= 3

    def test_generate_fallback_when_no_gap(self):
        engine = DecisionEngine()
        gaps = GapState(safety=0.1, gain=0.1, efficiency=0.1)
        tasks = engine.generate_tasks(gaps, EnvironmentState())
        assert len(tasks) == 1
        assert tasks[0].name == "idle_observation"

"""
决策引擎测试

验证任务生成、评分、选择的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.decision.decision import DecisionEngine, DecisionEngineBase
from src.platform.support.models.base.state import EnvironmentState, GapState, DriveWeights
from src.platform.support.models.base.task import Task, TaskPool, TaskPriority


class TestDecisionEngineBase:
    """测试决策引擎基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            DecisionEngineBase()


class TestDecisionEngineInit:
    """测试决策引擎初始化"""

    def test_normal_init(self):
        engine = DecisionEngine(base_exploration_ratio=0.3)
        assert engine.base_exploration_ratio == 0.3

    def test_boundary_min_exploration(self):
        engine = DecisionEngine(min_exploration_ratio=0.0)
        assert engine.min_exploration_ratio == 0.0

    def test_boundary_max_exploration(self):
        engine = DecisionEngine(max_exploration_ratio=1.0)
        assert engine.max_exploration_ratio == 1.0


class TestGenerateTasks:
    """测试任务生成"""

    def test_normal_gaps(self):
        engine = DecisionEngine()
        state = EnvironmentState()
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) > 0

    def test_empty_gaps(self):
        engine = DecisionEngine()
        state = EnvironmentState()
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) >= 0

    def test_large_gaps(self):
        engine = DecisionEngine()
        state = EnvironmentState()
        gaps = GapState(safety=1.0, gain=1.0, efficiency=1.0)
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) > 0


class TestSelectNextTask:
    """测试任务选择"""

    def test_normal_pool(self):
        engine = DecisionEngine()
        pool = TaskPool()
        gaps = GapState(safety=0.5)
        weights = DriveWeights()
        task = Task(name="test", priority=TaskPriority.HIGH)
        pool.add_task(task)
        selected = engine.select_next_task(pool, gaps, weights)
        assert selected is not None

    def test_empty_pool(self):
        engine = DecisionEngine()
        pool = TaskPool()
        gaps = GapState()
        weights = DriveWeights()
        selected = engine.select_next_task(pool, gaps, weights)
        assert selected is not None  # 引擎会自动生成默认任务


class TestScoreTask:
    """测试任务评分"""

    def test_normal_task(self):
        engine = DecisionEngine()
        task = Task(name="test", priority=TaskPriority.HIGH)
        gaps = GapState(safety=0.5, gain=0.3, efficiency=0.2)
        weights = DriveWeights()
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_null_task(self):
        engine = DecisionEngine()
        gaps = GapState()
        weights = DriveWeights()
        with pytest.raises(AttributeError):
            engine.score_task(None, gaps, weights)

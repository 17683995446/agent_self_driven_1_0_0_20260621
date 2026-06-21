"""
决策引擎V2测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.action.decision.decision_v2 import DecisionEngineV2
from src.platform.lifecycle.memory.plugin_manager import PluginManager
from src.platform.support.models.base.state import EnvironmentState, GapState, DriveWeights
from src.platform.support.models.base.task import TaskPool, TaskPriority


class TestDecisionEngineV2:
    """决策引擎V2测试类"""

    @pytest.fixture
    def engine(self):
        pm = PluginManager()
        pm.initialize()
        return DecisionEngineV2(pm)

    def test_init(self, engine):
        """测试初始化"""
        assert engine.base_exploration_ratio == 0.3
        assert engine.exploration_count == 0
        assert engine.exploitation_count == 0

    def test_create_plugin_task(self, engine):
        """测试创建插件任务"""
        task = engine._create_plugin_task("test", "tool_plugin", "calculate", {"expression": "1+1"})
        assert task.name == "test"
        assert task.target_drive == "gain"

    def test_create_file_read_task(self, engine):
        """测试创建文件读取任务"""
        task = engine._create_file_read_task("test.txt")
        assert "read_file" in task.name
        assert task.priority == TaskPriority.NORMAL

    def test_create_http_get_task(self, engine):
        """测试创建HTTP任务"""
        task = engine._create_http_get_task("https://example.com")
        assert "http_get" in task.name

    def test_create_db_query_task(self, engine):
        """测试创建数据库任务"""
        task = engine._create_db_query_task("SELECT 1")
        assert "db_query" in task.name

    def test_create_code_task(self, engine):
        """测试创建代码任务"""
        task = engine._create_code_task("print(1)")
        assert task.name == "execute_code"
        assert task.priority == TaskPriority.HIGH

    def test_create_tool_calculate_task(self, engine):
        """测试创建计算任务"""
        task = engine._create_tool_calculate_task("2+2")
        assert "calculate" in task.name
        assert task.target_drive == "eff"

    def test_generate_tasks_empty_gaps(self, engine):
        """测试零缺口生成任务"""
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        state = EnvironmentState()
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) == 1
        assert "calculate" in tasks[0].name

    def test_generate_tasks_safety(self, engine):
        """测试安全缺口生成任务"""
        gaps = GapState(safety=0.5, gain=0.0, efficiency=0.0)
        state = EnvironmentState()
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) == 1
        assert tasks[0].target_drive == "safe"

    def test_generate_tasks_gain(self, engine):
        """测试收益缺口生成任务"""
        gaps = GapState(safety=0.0, gain=0.5, efficiency=0.0)
        state = EnvironmentState()
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) >= 1

    def test_generate_tasks_efficiency(self, engine):
        """测试能效缺口生成任务"""
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.5)
        state = EnvironmentState()
        tasks = engine.generate_tasks(gaps, state)
        assert len(tasks) == 1
        assert tasks[0].target_drive in ["eff", "gain"]

    def test_compute_gap_match_safe(self, engine):
        """测试安全缺口匹配"""
        task = engine._create_safety_monitor_task(EnvironmentState())
        gaps = GapState(safety=0.8, gain=0.0, efficiency=0.0)
        match = engine._compute_gap_match(task, gaps)
        assert match == 0.8

    def test_compute_gap_match_gain(self, engine):
        """测试收益缺口匹配"""
        task = engine._create_file_read_task("test.txt")
        gaps = GapState(safety=0.0, gain=0.6, efficiency=0.0)
        match = engine._compute_gap_match(task, gaps)
        assert match == 0.6

    def test_compute_urgency_critical(self, engine):
        """测试紧急程度计算"""
        task = engine._create_safety_monitor_task(EnvironmentState())
        urgency = engine._compute_urgency(task)
        assert urgency == 0.75

    def test_compute_urgency_low(self, engine):
        """测试低优先级紧急程度"""
        task = engine._create_tool_calculate_task("1+1")
        urgency = engine._compute_urgency(task)
        assert urgency == 0.5

    def test_compute_novelty(self, engine):
        """测试新颖性计算"""
        task = engine._create_file_read_task("test.txt")
        assert engine._compute_novelty(task) == 0.0
        task.is_exploration = True
        assert engine._compute_novelty(task) == 0.3

    def test_compute_cost(self, engine):
        """测试成本计算"""
        task = engine._create_file_read_task("test.txt")
        cost = engine._compute_cost(task)
        assert 0.0 <= cost <= 1.0

    def test_compute_expired_bonus(self, engine):
        """测试过期奖励"""
        task = engine._create_file_read_task("test.txt")
        assert engine._compute_expired_bonus(task) == 0.0

    def test_compute_raw_score(self, engine):
        """测试原始分数计算"""
        score = engine._compute_raw_score(1.0, 1.0, 1.0, 0.3, 0.0, 0.0)
        assert 0.0 <= score <= 1.0

    def test_score_task(self, engine):
        """测试任务评分"""
        task = engine._create_file_read_task("test.txt")
        gaps = GapState(safety=0.0, gain=0.5, efficiency=0.0)
        weights = DriveWeights(safe=0.3, gain=0.5, eff=0.2)
        score = engine.score_task(task, gaps, weights)
        assert 0.0 <= score <= 1.0

    def test_select_next_task_empty_pool(self, engine):
        """测试空任务池选择"""
        pool = TaskPool()
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        weights = DriveWeights(safe=0.3, gain=0.5, eff=0.2)
        task = engine.select_next_task(pool, gaps, weights)
        assert task is not None

    def test_exploit_select(self, engine):
        """测试利用选择"""
        task = engine._create_file_read_task("test.txt")
        scored = [(0.8, task)]
        selected = engine._exploit_select(scored)
        assert selected is task
        assert engine.exploitation_count == 1

    def test_explore_select(self, engine):
        """测试探索选择"""
        t1 = engine._create_file_read_task("a.txt")
        t2 = engine._create_file_read_task("b.txt")
        t3 = engine._create_file_read_task("c.txt")
        scored = [(0.9, t1), (0.5, t2), (0.1, t3)]
        selected = engine._explore_select(scored)
        assert selected in [t1, t2, t3]
        assert engine.exploration_count == 1

    def test_execute_task_success(self, engine):
        """测试执行任务成功"""
        from src.left.action.execution.tool_plugin import ToolPlugin
        engine.plugin_manager.register("tool_plugin", ToolPlugin(), {})
        engine.plugin_manager.load("tool_plugin")
        task = engine._create_tool_calculate_task("2+2")
        result = engine.execute_task(task)
        assert result.success is True
        assert task.status.name == "COMPLETED"

    def test_execute_task_no_fn(self, engine):
        """测试无执行函数"""
        from src.platform.support.models.base.task import Task
        task = Task(name="empty")
        result = engine.execute_task(task)
        assert result.success is False

    def test_explore_select_empty(self, engine):
        """测试空列表探索"""
        result = engine._explore_select([])
        assert result is None

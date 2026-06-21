"""
多Agent协作协调器测试

验证Agent注册、任务分发、负载均衡、结果聚合的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.lifecycle.memory.agent_coordinator import (
    AgentCoordinator, AgentCoordinatorBase, AgentIdentity, AgentRole,
    TaskAssignment,
)
from src.platform.support.models.base.state import GapState
from src.platform.support.models.base.task import Task, TaskResult, TaskPriority


class TestAgentCoordinatorBase:
    """测试协调器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            AgentCoordinatorBase()


class TestAgentCoordinatorInit:
    """测试协调器初始化"""

    def test_normal_init(self):
        coord = AgentCoordinator()
        assert coord is not None
        assert len(coord.agents) == 0


class TestRegisterAgent:
    """测试Agent注册"""

    def test_register_single(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        assert coord.register_agent(agent) is True
        assert agent.id in coord.agents

    def test_register_duplicate(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        assert coord.register_agent(agent) is False

    def test_unregister(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        assert coord.unregister_agent(agent.id) is True
        assert agent.id not in coord.agents

    def test_unregister_nonexistent(self):
        coord = AgentCoordinator()
        assert coord.unregister_agent("none") is False


class TestDistributeTask:
    """测试任务分发"""

    def test_distribute_to_matching_agent(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        task = Task(name="check_cpu", target_drive="safe")
        gaps = GapState(safety=0.8, gain=0.1, efficiency=0.1)
        agent_id = coord.distribute_task(task, gaps)
        assert agent_id == safety.id

    def test_distribute_no_agents(self):
        coord = AgentCoordinator()
        task = Task(name="check_cpu", target_drive="safe")
        gaps = GapState()
        agent_id = coord.distribute_task(task, gaps)
        assert agent_id is None

    def test_distribute_considers_gaps(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        gain = AgentIdentity(name="gain_1", role=AgentRole.GAIN)
        coord.register_agent(safety)
        coord.register_agent(gain)
        task = Task(name="optimize", target_drive="gain")
        gaps = GapState(safety=0.1, gain=0.8, efficiency=0.1)
        agent_id = coord.distribute_task(task, gaps)
        assert agent_id == gain.id

    def test_distribute_load_balancing(self):
        coord = AgentCoordinator()
        safety1 = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        safety2 = AgentIdentity(name="safety_2", role=AgentRole.SAFETY)
        coord.register_agent(safety1)
        coord.register_agent(safety2)
        # 给safety1添加大量任务
        for i in range(50):
            coord.agent_pools[safety1.id].add_task(Task(name=f"t{i}"))
        task = Task(name="check_cpu", target_drive="safe")
        gaps = GapState(safety=0.5)
        agent_id = coord.distribute_task(task, gaps)
        assert agent_id == safety2.id


class TestReportResult:
    """测试结果报告"""

    def test_report_success(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        task = Task(name="check_cpu", target_drive="safe")
        coord.distribute_task(task, GapState())
        coord.report_result(task.id, TaskResult(success=True))
        assert coord.stats["tasks_completed"] == 1

    def test_report_failure(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        task = Task(name="check_cpu", target_drive="safe")
        coord.distribute_task(task, GapState())
        coord.report_result(task.id, TaskResult(success=False))
        assert coord.stats["tasks_failed"] == 1


class TestGetStats:
    """测试统计信息"""

    def test_get_agent_stats(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        stats = coord.get_agent_stats(safety.id)
        assert stats is not None
        assert stats["name"] == "safety_1"
        assert stats["role"] == "safety"

    def test_get_agent_stats_nonexistent(self):
        coord = AgentCoordinator()
        assert coord.get_agent_stats("none") is None

    def test_get_all_stats(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        stats = coord.get_all_stats()
        assert "coordinator_stats" in stats
        assert stats["agent_count"] == 1


class TestBroadcastTask:
    """测试任务广播"""

    def test_broadcast(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        gain = AgentIdentity(name="gain_1", role=AgentRole.GAIN)
        coord.register_agent(safety)
        coord.register_agent(gain)
        task = Task(name="broadcast_task")
        assigned = coord.broadcast_task(task)
        assert len(assigned) == 2

    def test_broadcast_no_agents(self):
        coord = AgentCoordinator()
        task = Task(name="broadcast_task")
        assigned = coord.broadcast_task(task)
        assert len(assigned) == 0


class TestGetPendingTasks:
    """测试获取待处理任务"""

    def test_get_pending(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        task = Task(name="check_cpu")
        coord.agent_pools[safety.id].add_task(task)
        pending = coord.get_pending_tasks(safety.id)
        assert len(pending) == 1

    def test_get_pending_nonexistent(self):
        coord = AgentCoordinator()
        pending = coord.get_pending_tasks("none")
        assert pending == []

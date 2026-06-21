"""
多Agent协作协调器补充测试

覆盖缺失分支：unregister日志、broadcast跳过COORDINATOR、_load_penalty边界
"""

import pytest

from src.platform.lifecycle.memory.agent_coordinator import (
    AgentCoordinator, AgentIdentity, AgentRole,
)
from src.platform.support.models.base.state import GapState
from src.platform.support.models.base.task import Task


class TestUnregisterAgent:
    """测试注销Agent"""

    def test_unregister_logs_and_removes(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        assert coord.unregister_agent(agent.id) is True
        assert agent.id not in coord.agents


class TestLoadPenalty:
    """测试负载惩罚边界"""

    def test_load_penalty_empty_pool(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        # 删除pool测试边界
        coord.agent_pools.pop(agent.id)
        penalty = coord._load_penalty(agent.id)
        assert penalty == 0.0

    def test_load_penalty_full_pool(self):
        coord = AgentCoordinator()
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        for i in range(120):
            coord.agent_pools[agent.id].add_task(Task(name=f"t{i}"))
        penalty = coord._load_penalty(agent.id)
        assert penalty == 1.0


class TestBroadcastSkipsCoordinator:
    """测试广播跳过协调器角色"""

    def test_broadcast_skips_coordinator(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coordinator = AgentIdentity(name="coord_1", role=AgentRole.COORDINATOR)
        coord.register_agent(safety)
        coord.register_agent(coordinator)
        task = Task(name="broadcast_task")
        assigned = coord.broadcast_task(task)
        assert len(assigned) == 1
        assert assigned[0] == safety.id

    def test_broadcast_only_coordinator(self):
        coord = AgentCoordinator()
        coordinator = AgentIdentity(name="coord_1", role=AgentRole.COORDINATOR)
        coord.register_agent(coordinator)
        task = Task(name="broadcast_task")
        assigned = coord.broadcast_task(task)
        assert len(assigned) == 0


class TestDistributeTaskEdgeCases:
    """测试任务分发边界"""

    def test_distribute_only_coordinator(self):
        coord = AgentCoordinator()
        coordinator = AgentIdentity(name="coord_1", role=AgentRole.COORDINATOR)
        coord.register_agent(coordinator)
        task = Task(name="check_cpu", target_drive="safe")
        agent_id = coord.distribute_task(task, GapState())
        assert agent_id is None

    def test_distribute_with_zero_gap(self):
        coord = AgentCoordinator()
        safety = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(safety)
        task = Task(name="check_cpu", target_drive="safe")
        gaps = GapState(safety=0.0, gain=0.0, efficiency=0.0)
        agent_id = coord.distribute_task(task, gaps)
        assert agent_id == safety.id

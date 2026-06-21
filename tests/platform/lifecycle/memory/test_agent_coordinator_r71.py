"""
多Agent协作R71完善测试

验证Agent心跳、健康监控、共识投票
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import time

import pytest

from src.platform.lifecycle.memory.agent_coordinator import (
    AgentCoordinator, AgentIdentity, AgentRole,
    AgentHeartbeat, AgentHealthMonitor, ConsensusVoter,
)


class TestAgentHeartbeat:
    """测试Agent心跳记录"""

    def test_heartbeat_creation(self):
        hb = AgentHeartbeat(agent_id="a1", timestamp=100.0)
        assert hb.agent_id == "a1"
        assert hb.timestamp == 100.0
        assert hb.status == "alive"


class TestAgentHealthMonitor:
    """测试Agent健康监控"""

    def test_record_heartbeat(self):
        monitor = AgentHealthMonitor(timeout_seconds=10.0)
        monitor.record_heartbeat("a1")
        assert "a1" in monitor.heartbeats

    def test_is_alive_recent(self):
        monitor = AgentHealthMonitor(timeout_seconds=10.0)
        monitor.record_heartbeat("a1")
        assert monitor.is_alive("a1") is True

    def test_is_alive_expired(self):
        monitor = AgentHealthMonitor(timeout_seconds=0.01)
        monitor.record_heartbeat("a1")
        time.sleep(0.02)
        assert monitor.is_alive("a1") is False

    def test_is_alive_unknown(self):
        monitor = AgentHealthMonitor(timeout_seconds=10.0)
        assert monitor.is_alive("unknown") is False

    def test_get_dead_agents(self):
        monitor = AgentHealthMonitor(timeout_seconds=0.01)
        monitor.record_heartbeat("a1")
        monitor.record_heartbeat("a2")
        time.sleep(0.02)
        dead = monitor.get_dead_agents()
        assert "a1" in dead
        assert "a2" in dead

    def test_get_dead_agents_mixed(self):
        monitor = AgentHealthMonitor(timeout_seconds=0.05)
        monitor.record_heartbeat("alive")
        monitor.record_heartbeat("dead")
        time.sleep(0.06)
        monitor.record_heartbeat("alive")
        dead = monitor.get_dead_agents()
        assert "dead" in dead
        assert "alive" not in dead

    def test_get_stats(self):
        monitor = AgentHealthMonitor(timeout_seconds=10.0)
        monitor.record_heartbeat("a1")
        monitor.record_heartbeat("a2")
        stats = monitor.get_stats()
        assert stats["total"] == 2
        assert stats["alive"] == 2
        assert stats["dead"] == 0

    def test_get_stats_with_dead(self):
        monitor = AgentHealthMonitor(timeout_seconds=0.01)
        monitor.record_heartbeat("a1")
        time.sleep(0.02)
        stats = monitor.get_stats()
        assert stats["total"] == 1
        assert stats["alive"] == 0
        assert stats["dead"] == 1

    def test_empty_stats(self):
        monitor = AgentHealthMonitor()
        stats = monitor.get_stats()
        assert stats["total"] == 0
        assert stats["alive"] == 0
        assert stats["dead"] == 0


class TestConsensusVoter:
    """测试共识投票器"""

    def test_cast_vote_yes(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        result = voter.get_result("p1")
        assert result["yes"] == 1
        assert result["no"] == 0

    def test_cast_vote_no(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", False)
        result = voter.get_result("p1")
        assert result["yes"] == 0
        assert result["no"] == 1

    def test_multiple_votes(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        voter.cast_vote("p1", "a2", True)
        voter.cast_vote("p1", "a3", False)
        result = voter.get_result("p1")
        assert result["yes"] == 2
        assert result["no"] == 1

    def test_duplicate_vote_ignored(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        voter.cast_vote("p1", "a1", True)
        result = voter.get_result("p1")
        assert result["yes"] == 1

    def test_is_approved_pass(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        voter.cast_vote("p1", "a2", True)
        assert voter.is_approved("p1", total_agents=3) is True

    def test_is_approved_fail(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        assert voter.is_approved("p1", total_agents=3) is False

    def test_is_approved_exact_threshold(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        voter.cast_vote("p1", "a2", False)
        assert voter.is_approved("p1", total_agents=2) is True

    def test_is_approved_no_votes(self):
        voter = ConsensusVoter(threshold=0.5)
        assert voter.is_approved("p1", total_agents=3) is False

    def test_get_result_no_votes(self):
        voter = ConsensusVoter(threshold=0.5)
        result = voter.get_result("p1")
        assert result["yes"] == 0
        assert result["no"] == 0

    def test_reset(self):
        voter = ConsensusVoter(threshold=0.5)
        voter.cast_vote("p1", "a1", True)
        voter.reset("p1")
        result = voter.get_result("p1")
        assert result["yes"] == 0
        assert result["no"] == 0

    def test_high_threshold(self):
        voter = ConsensusVoter(threshold=0.8)
        voter.cast_vote("p1", "a1", True)
        voter.cast_vote("p1", "a2", True)
        voter.cast_vote("p1", "a3", True)
        voter.cast_vote("p1", "a4", False)
        assert voter.is_approved("p1", total_agents=5) is False

    def test_low_threshold(self):
        voter = ConsensusVoter(threshold=0.2)
        voter.cast_vote("p1", "a1", True)
        assert voter.is_approved("p1", total_agents=5) is True


class TestAgentCoordinatorR71:
    """测试协调器R71补充用例"""

    def test_coordinator_with_health_monitor(self):
        coord = AgentCoordinator()
        monitor = AgentHealthMonitor(timeout_seconds=10.0)
        agent = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        coord.register_agent(agent)
        monitor.record_heartbeat(agent.id)
        assert monitor.is_alive(agent.id) is True

    def test_coordinator_with_consensus(self):
        coord = AgentCoordinator()
        voter = ConsensusVoter(threshold=0.5)
        a1 = AgentIdentity(name="safety_1", role=AgentRole.SAFETY)
        a2 = AgentIdentity(name="gain_1", role=AgentRole.GAIN)
        coord.register_agent(a1)
        coord.register_agent(a2)
        voter.cast_vote("proposal_1", a1.id, True)
        voter.cast_vote("proposal_1", a2.id, True)
        assert voter.is_approved("proposal_1", total_agents=2) is True

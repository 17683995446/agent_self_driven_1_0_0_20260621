"""
主入口扩展测试

补充覆盖事件总线集成、模块解耦路径
"""

import pytest

from src.main import AgentSystem


class TestAgentSystemExtended:
    """测试Agent系统扩展路径"""

    def test_event_bus_started(self):
        system = AgentSystem()
        assert system.event_bus._running is True

    def test_status_logger_subscribed(self):
        system = AgentSystem()
        assert system.status_logger is not None

    def test_module_connectors_exist(self):
        system = AgentSystem()
        assert system.perception_conn is not None
        assert system.drive_conn is not None
        assert system.decision_conn is not None
        assert system.guardrail_conn is not None

    def test_connector_names(self):
        system = AgentSystem()
        assert system.perception_conn.module_name == "perception"
        assert system.drive_conn.module_name == "drive_engine"
        assert system.decision_conn.module_name == "decision"
        assert system.guardrail_conn.module_name == "guardrail"

"""
O7：事件总线双向化测试

验证组件订阅事件并响应：
1. 任务失败事件监听器
2. 安全违规事件监听器
3. 周期指标事件监听器
4. 事件触发组件响应
5. 多监听器并行工作
"""

import pytest
import time
from unittest.mock import MagicMock

from src.platform.support.infra.event.event_bus import (
    EventBus, EventType, Event, EventListener,
)


class MockAgent:
    """模拟AgentSystem用于测试"""
    pass


class TestO7TaskFailureEventListener:
    """测试任务失败事件监听器"""

    def test_listener_subscribes_to_task_failed(self):
        """监听器订阅TASK_FAILED事件"""
        from src.main import TaskFailureEventListener
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        assert EventType.TASK_FAILED in listener.interested_events

    def test_listener_records_failure(self):
        """监听器记录失败事件"""
        from src.main import TaskFailureEventListener
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        event = Event(
            event_type=EventType.TASK_FAILED,
            payload={"task_name": "bad_task", "error": "timeout"},
        )
        listener.on_event(event)
        assert len(listener.failure_events_received) == 1
        assert listener.failure_events_received[0] == "bad_task"

    def test_listener_ignores_other_events(self):
        """监听器忽略非TASK_FAILED事件"""
        from src.main import TaskFailureEventListener
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            payload={"task_name": "good_task"},
        )
        listener.on_event(event)
        assert len(listener.failure_events_received) == 0

    def test_listener_records_multiple_failures(self):
        """监听器记录多次失败"""
        from src.main import TaskFailureEventListener
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        for i in range(5):
            event = Event(
                event_type=EventType.TASK_FAILED,
                payload={"task_name": f"task_{i}"},
            )
            listener.on_event(event)
        assert len(listener.failure_events_received) == 5


class TestO7SafetyViolationEventListener:
    """测试安全违规事件监听器"""

    def test_listener_subscribes_to_safety_violation(self):
        """监听器订阅SAFETY_VIOLATION事件"""
        from src.main import SafetyViolationEventListener
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        assert EventType.SAFETY_VIOLATION in listener.interested_events

    def test_listener_records_violation(self):
        """监听器记录违规事件"""
        from src.main import SafetyViolationEventListener
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        event = Event(
            event_type=EventType.SAFETY_VIOLATION,
            payload={"reason": "CPU too high"},
        )
        listener.on_event(event)
        assert listener.violation_count == 1
        assert "CPU too high" in listener.violation_reasons

    def test_listener_ignores_other_events(self):
        """监听器忽略非SAFETY_VIOLATION事件"""
        from src.main import SafetyViolationEventListener
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            payload={},
        )
        listener.on_event(event)
        assert listener.violation_count == 0

    def test_listener_counts_multiple_violations(self):
        """监听器统计多次违规"""
        from src.main import SafetyViolationEventListener
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        for i in range(3):
            event = Event(
                event_type=EventType.SAFETY_VIOLATION,
                payload={"reason": f"violation_{i}"},
            )
            listener.on_event(event)
        assert listener.violation_count == 3
        assert len(listener.violation_reasons) == 3


class TestO7CycleMetricsEventListener:
    """测试周期指标事件监听器"""

    def test_listener_subscribes_to_cycle_end(self):
        """监听器订阅CYCLE_END事件"""
        from src.main import CycleMetricsEventListener
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        assert EventType.CYCLE_END in listener.interested_events

    def test_listener_records_cycle_metrics(self):
        """监听器记录周期指标"""
        from src.main import CycleMetricsEventListener
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        event = Event(
            event_type=EventType.CYCLE_END,
            payload={"cycle": 1, "cpu": 0.5, "success_rate": 0.8},
        )
        listener.on_event(event)
        assert listener.cycle_count == 1
        assert listener.last_cpu == 0.5
        assert listener.last_success_rate == 0.8

    def test_listener_ignores_other_events(self):
        """监听器忽略非CYCLE_END事件"""
        from src.main import CycleMetricsEventListener
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        event = Event(
            event_type=EventType.CYCLE_START,
            payload={"cycle": 1},
        )
        listener.on_event(event)
        assert listener.cycle_count == 0

    def test_listener_accumulates_cycles(self):
        """监听器累积周期计数"""
        from src.main import CycleMetricsEventListener
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        for i in range(10):
            event = Event(
                event_type=EventType.CYCLE_END,
                payload={"cycle": i, "cpu": 0.1 * i, "success_rate": 0.9},
            )
            listener.on_event(event)
        assert listener.cycle_count == 10


class TestO7EventBusIntegration:
    """测试事件总线集成"""

    def test_event_bus_dispatches_to_failure_listener(self):
        """事件总线分发到失败监听器"""
        from src.main import TaskFailureEventListener
        bus = EventBus()
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        bus.subscribe(listener)
        bus.publish_simple(
            EventType.TASK_FAILED,
            payload={"task_name": "failed_task"},
        )
        assert len(listener.failure_events_received) == 1
        assert listener.failure_events_received[0] == "failed_task"

    def test_event_bus_dispatches_to_safety_listener(self):
        """事件总线分发到安全监听器"""
        from src.main import SafetyViolationEventListener
        bus = EventBus()
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        bus.subscribe(listener)
        bus.publish_simple(
            EventType.SAFETY_VIOLATION,
            payload={"reason": "memory exceeded"},
        )
        assert listener.violation_count == 1

    def test_event_bus_dispatches_to_cycle_listener(self):
        """事件总线分发到周期监听器"""
        from src.main import CycleMetricsEventListener
        bus = EventBus()
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        bus.subscribe(listener)
        bus.publish_simple(
            EventType.CYCLE_END,
            payload={"cycle": 1, "cpu": 0.3, "success_rate": 0.9},
        )
        assert listener.cycle_count == 1
        assert listener.last_cpu == 0.3

    def test_multiple_listeners_receive_events(self):
        """多个监听器同时接收事件"""
        from src.main import (
            TaskFailureEventListener,
            SafetyViolationEventListener,
            CycleMetricsEventListener,
        )
        bus = EventBus()
        agent = MockAgent()
        failure_listener = TaskFailureEventListener(agent)
        safety_listener = SafetyViolationEventListener(agent)
        cycle_listener = CycleMetricsEventListener(agent)
        bus.subscribe(failure_listener)
        bus.subscribe(safety_listener)
        bus.subscribe(cycle_listener)
        # 发布不同事件
        bus.publish_simple(EventType.TASK_FAILED, payload={"task_name": "t1"})
        bus.publish_simple(EventType.SAFETY_VIOLATION, payload={"reason": "r1"})
        bus.publish_simple(EventType.CYCLE_END, payload={"cycle": 1, "cpu": 0.5})
        # 验证各自收到对应事件
        assert len(failure_listener.failure_events_received) == 1
        assert safety_listener.violation_count == 1
        assert cycle_listener.cycle_count == 1

    def test_listener_does_not_receive_unsubscribed_events(self):
        """监听器不接收未订阅的事件"""
        from src.main import TaskFailureEventListener
        bus = EventBus()
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        bus.subscribe(listener)
        # 发布未订阅的事件
        bus.publish_simple(EventType.TASK_COMPLETED, payload={"task_name": "ok"})
        bus.publish_simple(EventType.CYCLE_END, payload={"cycle": 1})
        assert len(listener.failure_events_received) == 0


class TestO7ListenerNames:
    """测试监听器名称"""

    def test_failure_listener_name(self):
        """失败监听器有正确名称"""
        from src.main import TaskFailureEventListener
        agent = MockAgent()
        listener = TaskFailureEventListener(agent)
        assert listener.name == "task_failure_listener"

    def test_safety_listener_name(self):
        """安全监听器有正确名称"""
        from src.main import SafetyViolationEventListener
        agent = MockAgent()
        listener = SafetyViolationEventListener(agent)
        assert listener.name == "safety_violation_listener"

    def test_cycle_listener_name(self):
        """周期监听器有正确名称"""
        from src.main import CycleMetricsEventListener
        agent = MockAgent()
        listener = CycleMetricsEventListener(agent)
        assert listener.name == "cycle_metrics_listener"

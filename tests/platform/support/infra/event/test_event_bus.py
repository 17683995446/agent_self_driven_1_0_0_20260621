"""
事件总线系统测试

验证事件发布-订阅、异步分发、模块连接器的正确性
"""

import pytest
import time
import threading
from src.platform.support.infra.event.event_bus import (
    EventBus, Event, EventType, EventListener, ModuleConnector,
)


class MockListener(EventListener):
    """测试用监听器"""

    def __init__(self, name: str):
        super().__init__(name)
        self.received_events: list = []
        self._lock = threading.Lock()

    def on_event(self, event: Event):
        with self._lock:
            self.received_events.append(event)

    def get_events(self) -> list:
        with self._lock:
            return self.received_events.copy()


class TestEvent:
    """测试事件对象"""

    def test_event_creation(self):
        event = Event(
            event_type=EventType.STATE_UPDATED,
            payload={"cpu": 0.5},
            source="perception",
            cycle=10,
        )
        assert event.event_type == EventType.STATE_UPDATED
        assert event.payload["cpu"] == 0.5
        assert event.source == "perception"
        assert event.cycle == 10

    def test_event_to_dict(self):
        event = Event(event_type=EventType.TASK_COMPLETED, payload={"success": True})
        d = event.to_dict()
        assert d["event_type"] == "TASK_COMPLETED"
        assert d["payload"]["success"] is True
        assert "timestamp" in d


class TestEventBus:
    """测试事件总线"""

    def setup_method(self):
        self.bus = EventBus()

    def teardown_method(self):
        self.bus.stop()

    def test_subscribe_and_publish(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5})
        self.bus.publish(event)

        assert len(listener.get_events()) == 1
        assert listener.get_events()[0].payload["cpu"] == 0.5

    def test_unsubscribe(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])
        self.bus.unsubscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5})
        self.bus.publish(event)

        assert len(listener.get_events()) == 0

    def test_multiple_listeners(self):
        listener1 = MockListener("l1")
        listener2 = MockListener("l2")
        self.bus.subscribe(listener1, [EventType.STATE_UPDATED])
        self.bus.subscribe(listener2, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5})
        self.bus.publish(event)

        assert len(listener1.get_events()) == 1
        assert len(listener2.get_events()) == 1

    def test_different_event_types(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        self.bus.publish(Event(EventType.TASK_COMPLETED, {}))
        self.bus.publish(Event(EventType.STATE_UPDATED, {"cpu": 0.5}))

        assert len(listener.get_events()) == 1
        assert listener.get_events()[0].event_type == EventType.STATE_UPDATED

    def test_global_listener(self):
        listener = MockListener("global")
        self.bus.subscribe(listener, None)  # 订阅所有

        self.bus.publish(Event(EventType.STATE_UPDATED, {}))
        self.bus.publish(Event(EventType.TASK_COMPLETED, {}))

        assert len(listener.get_events()) == 2

    def test_publish_simple(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.GAPS_COMPUTED])

        self.bus.publish_simple(
            event_type=EventType.GAPS_COMPUTED,
            payload={"gap": 0.3},
            source="drive_engine",
            cycle=5,
        )

        events = listener.get_events()
        assert len(events) == 1
        assert events[0].payload["gap"] == 0.3
        assert events[0].source == "drive_engine"
        assert events[0].cycle == 5

    def test_history(self):
        self.bus.publish(Event(EventType.STATE_UPDATED, {"i": 1}))
        self.bus.publish(Event(EventType.STATE_UPDATED, {"i": 2}))
        self.bus.publish(Event(EventType.TASK_COMPLETED, {"i": 3}))

        recent = self.bus.get_recent_events(2)
        assert len(recent) == 2
        assert recent[-1].payload["i"] == 3

        filtered = self.bus.get_recent_events(10, EventType.STATE_UPDATED)
        assert len(filtered) == 2

    def test_event_stats(self):
        self.bus.publish(Event(EventType.STATE_UPDATED, {}))
        self.bus.publish(Event(EventType.STATE_UPDATED, {}))
        self.bus.publish(Event(EventType.TASK_COMPLETED, {}))

        stats = self.bus.get_event_stats()
        assert stats["STATE_UPDATED"] == 2
        assert stats["TASK_COMPLETED"] == 1

    def test_async_publish(self):
        self.bus.start()
        listener = MockListener("async")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        self.bus.publish(Event(EventType.STATE_UPDATED, {"cpu": 0.5}), async_mode=True)
        time.sleep(0.2)  # 等待异步处理

        assert len(listener.get_events()) == 1

    def test_listener_exception_isolated(self):
        """监听器异常不应影响其他监听器"""
        class BadListener(EventListener):
            def on_event(self, event: Event):
                raise ValueError("boom")

        bad = BadListener("bad")
        good = MockListener("good")
        self.bus.subscribe(bad, [EventType.STATE_UPDATED])
        self.bus.subscribe(good, [EventType.STATE_UPDATED])

        self.bus.publish(Event(EventType.STATE_UPDATED, {}))
        assert len(good.get_events()) == 1

    def test_thread_safety(self):
        errors = []
        listener = MockListener("thread")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        def publisher(idx):
            try:
                for _ in range(50):
                    self.bus.publish(Event(EventType.STATE_UPDATED, {"idx": idx}))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publisher, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(listener.get_events()) == 250


class TestEventBusFiltering:
    """测试事件过滤链"""

    def setup_method(self):
        self.bus = EventBus()

    def teardown_method(self):
        self.bus.stop()

    def test_publish_filtered_pass(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5})
        result = self.bus.publish_filtered(event, [lambda e: e.payload.get("cpu", 0) > 0.3])
        assert result is True
        assert len(listener.get_events()) == 1

    def test_publish_filtered_block(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.1})
        result = self.bus.publish_filtered(event, [lambda e: e.payload.get("cpu", 0) > 0.3])
        assert result is False
        assert len(listener.get_events()) == 0

    def test_publish_filtered_multiple_filters(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5, "mem": 0.8})
        filters = [
            lambda e: e.payload.get("cpu", 0) > 0.3,
            lambda e: e.payload.get("mem", 0) > 0.5,
        ]
        result = self.bus.publish_filtered(event, filters)
        assert result is True

    def test_publish_filtered_one_fails(self):
        listener = MockListener("test")
        self.bus.subscribe(listener, [EventType.STATE_UPDATED])

        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5, "mem": 0.2})
        filters = [
            lambda e: e.payload.get("cpu", 0) > 0.3,
            lambda e: e.payload.get("mem", 0) > 0.5,
        ]
        result = self.bus.publish_filtered(event, filters)
        assert result is False


class TestEventBusDeadLetter:
    """测试死信队列"""

    def setup_method(self):
        self.bus = EventBus()

    def teardown_method(self):
        self.bus.stop()

    def test_dead_letter_queue_empty(self):
        assert self.bus.get_dead_letter_events() == []

    def test_move_to_dead_letter(self):
        event = Event(EventType.STATE_UPDATED, {"cpu": 0.5})
        self.bus._move_to_dead_letter(event, "test error")
        dead = self.bus.get_dead_letter_events()
        assert len(dead) == 1
        assert dead[0]["error"] == "test error"

    def test_dead_letter_max_size(self):
        for i in range(5):
            event = Event(EventType.STATE_UPDATED, {"i": i})
            self.bus._move_to_dead_letter(event, f"error {i}")
        dead = self.bus.get_dead_letter_events(n=3)
        assert len(dead) == 3


class TestModuleConnector:
    """测试模块连接器"""

    def setup_method(self):
        self.bus = EventBus()
        self.connector = ModuleConnector(self.bus, "test_module")

    def teardown_method(self):
        self.bus.stop()

    def test_publish(self):
        listener = MockListener("receiver")
        self.bus.subscribe(listener, [EventType.TASK_COMPLETED])

        self.connector.set_cycle(10)
        self.connector.publish(EventType.TASK_COMPLETED, {"success": True})

        events = listener.get_events()
        assert len(events) == 1
        assert events[0].source == "test_module"
        assert events[0].cycle == 10
        assert events[0].payload["success"] is True

    def test_subscribe(self):
        listener = MockListener("local")
        self.connector.subscribe(listener, [EventType.GAPS_COMPUTED])

        self.connector.publish(EventType.GAPS_COMPUTED, {"gap": 0.2})

        assert len(listener.get_events()) == 1

    def test_get_recent_events(self):
        self.connector.publish(EventType.STATE_UPDATED, {"cpu": 0.1})
        self.connector.publish(EventType.STATE_UPDATED, {"cpu": 0.2})

        events = self.connector.get_recent_events(1)
        assert len(events) == 1
        assert events[0].payload["cpu"] == 0.2

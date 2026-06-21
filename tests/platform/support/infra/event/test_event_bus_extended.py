"""
事件总线扩展测试

补充覆盖 start/stop、unsubscribe全部、异常分发等路径
"""

import pytest
import time

from src.platform.support.infra.event.event_bus import (
    EventBus, Event, EventType, EventListener, EventBusBase, EventListenerBase,
)


class MockListener(EventListener):
    """测试用监听器"""

    def __init__(self, name: str):
        super().__init__(name)
        self.received_events: list = []

    def on_event(self, event: Event):
        self.received_events.append(event)


class TestEventBusBases:
    """测试抽象基类"""

    def test_event_bus_base_abstract(self):
        with pytest.raises(TypeError):
            EventBusBase()

    def test_event_listener_base_abstract(self):
        with pytest.raises(TypeError):
            EventListenerBase()


class TestEventBusExtended:
    """测试事件总线扩展路径"""

    def test_unsubscribe_all(self):
        bus = EventBus()
        listener = MockListener("test")
        bus.subscribe(listener, [EventType.STATE_UPDATED])
        bus.unsubscribe(listener)
        bus.publish(Event(EventType.STATE_UPDATED, {}))
        assert len(listener.received_events) == 0

    def test_start_stop(self):
        bus = EventBus()
        bus.start()
        assert bus._running is True
        bus.stop()
        assert bus._running is False

    def test_publish_async_then_stop(self):
        bus = EventBus()
        bus.start()
        listener = MockListener("async")
        bus.subscribe(listener, [EventType.STATE_UPDATED])
        bus.publish(Event(EventType.STATE_UPDATED, {}), async_mode=True)
        time.sleep(0.2)
        bus.stop()
        assert len(listener.received_events) >= 1

    def test_listener_not_interested(self):
        bus = EventBus()
        listener = MockListener("test")
        bus.subscribe(listener, [EventType.STATE_UPDATED])
        # 手动取消感兴趣，模拟不感兴趣的监听器
        listener.interested_events.discard(EventType.STATE_UPDATED)
        bus.publish(Event(EventType.STATE_UPDATED, {}))
        assert len(listener.received_events) == 0

    def test_get_recent_events_empty(self):
        bus = EventBus()
        events = bus.get_recent_events(10)
        assert events == []

    def test_get_event_stats_empty(self):
        bus = EventBus()
        stats = bus.get_event_stats()
        assert stats == {}


class TestEventListenerExtended:
    """测试事件监听器扩展路径"""

    def test_subscribe_unsubscribe(self):
        listener = MockListener("test")
        listener.subscribe(EventType.STATE_UPDATED)
        assert listener.is_interested(EventType.STATE_UPDATED) is True
        listener.unsubscribe(EventType.STATE_UPDATED)
        assert listener.is_interested(EventType.STATE_UPDATED) is False

    def test_is_interested_false(self):
        listener = MockListener("test")
        assert listener.is_interested(EventType.STATE_UPDATED) is False

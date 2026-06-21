"""
事件总线系统

第一性原理：模块间必须通过事件通信，禁止直接调用，实现彻底解耦
- 发布-订阅模式：模块只关心自己感兴趣的事件
- 异步处理：事件处理不阻塞发布者
- 类型安全：事件必须有明确类型和结构
- 可追溯：所有事件可被审计日志记录

类比：生物的"激素系统"——不同器官通过化学信号通信，而非直接连接
"""

import time
import threading
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Optional, Set
from collections import deque
from queue import Queue, Empty


logger = logging.getLogger(__name__)


class EventType(Enum):
    """系统事件类型"""
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    CYCLE_START = auto()
    CYCLE_END = auto()
    STATE_UPDATED = auto()
    SENSOR_ERROR = auto()
    GAPS_COMPUTED = auto()
    WEIGHTS_UPDATED = auto()
    REWARD_RECEIVED = auto()
    TASK_GENERATED = auto()
    TASK_SELECTED = auto()
    TASK_EXECUTED = auto()
    TASK_COMPLETED = auto()
    TASK_FAILED = auto()
    PREDICTION_UPDATED = auto()
    ERROR_COMPUTED = auto()
    MODEL_IMPROVED = auto()
    SAFETY_VIOLATION = auto()
    GUARDRAIL_TRIGGERED = auto()
    SNAPSHOT_CREATED = auto()
    SNAPSHOT_ROLLBACK = auto()
    SLEEP_ENTER = auto()
    SLEEP_WAKE = auto()
    CONFIG_RELOADED = auto()
    HEALTH_CHECK = auto()
    ANOMALY_DETECTED = auto()


@dataclass
class Event:
    """事件对象"""
    event_type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    cycle: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
            "cycle": self.cycle,
        }


class EventListenerBase(ABC):
    """事件监听器抽象基类"""

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """处理事件"""
        pass


class EventListener(EventListenerBase):
    """事件监听器接口"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.interested_events: Set[EventType] = set()

    def on_event(self, event: Event) -> None:
        """处理事件（子类重写）"""
        pass

    def subscribe(self, event_type: EventType) -> None:
        """订阅事件类型"""
        self.interested_events.add(event_type)

    def unsubscribe(self, event_type: EventType) -> None:
        """取消订阅"""
        self.interested_events.discard(event_type)

    def is_interested(self, event_type: EventType) -> bool:
        """是否对某事件感兴趣"""
        return event_type in self.interested_events


class EventBusBase(ABC):
    """事件总线抽象基类"""

    @abstractmethod
    def publish(self, event: Event, async_mode: bool = False) -> None:
        """发布事件"""
        pass

    @abstractmethod
    def subscribe(self, listener: EventListener, event_types: Optional[List[EventType]] = None) -> None:
        """订阅事件"""
        pass


class EventBus(EventBusBase):
    """
    事件总线

    第一性原理：事件总线是系统的"神经系统"，负责模块间通信
    - 同步发布：立即通知所有订阅者（用于关键事件）
    - 异步发布：放入队列，后台线程分发（用于普通事件）
    - 历史记录：保留最近N个事件，支持回放
    """

    def _init_listeners(self) -> None:
        self._listeners: Dict[EventType, List[EventListener]] = {et: [] for et in EventType}
        self._global_listeners: List[EventListener] = []

    def _init_async(self, max_history: int, async_workers: int) -> None:
        self._history: deque = deque(maxlen=max_history)
        self._dead_letter_queue: deque = deque(maxlen=max_history)
        self._lock = threading.RLock()
        self._async_queue: Queue = Queue()
        self._async_workers = async_workers
        self._worker_threads: List[threading.Thread] = []
        self._running = False

    def __init__(self, max_history: int = 1000, async_workers: int = 1) -> None:
        self._init_listeners()
        self._init_async(max_history, async_workers)

    def start(self) -> None:
        """启动异步处理线程"""
        self._running = True
        for i in range(self._async_workers):
            t = threading.Thread(target=self._async_dispatch_loop, name=f"event-worker-{i}")
            t.daemon = True
            t.start()
            self._worker_threads.append(t)
        logger.info(f"EventBus started with {self._async_workers} workers")

    def stop(self) -> None:
        """停止异步处理线程"""
        self._running = False
        for _ in self._worker_threads:
            self._async_queue.put(None)
        for t in self._worker_threads:
            t.join(timeout=2.0)
        self._worker_threads = []
        logger.info("EventBus stopped")

    def _async_dispatch_loop(self) -> None:
        """异步分发循环"""
        while self._running:
            try:
                event = self._async_queue.get(timeout=0.5)
                if event is None:
                    break
                self._dispatch_sync(event)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Async dispatch error: {e}")

    def _add_to_event_listeners(
        self, listener: EventListener, event_types: Optional[List[EventType]]
    ) -> None:
        """将监听器添加到对应事件类型列表"""
        if event_types is None:
            self._global_listeners.append(listener)
            for et in EventType:
                listener.subscribe(et)
        else:
            for et in event_types:
                if listener not in self._listeners[et]:
                    self._listeners[et].append(listener)
                    listener.subscribe(et)

    def subscribe(
        self,
        listener: EventListener,
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """
        订阅事件

        Args:
            listener: 监听器
            event_types: 感兴趣的事件类型，None表示订阅所有
        """
        with self._lock:
            self._add_to_event_listeners(listener, event_types)
        logger.debug(f"Listener '{listener.name}' subscribed to {event_types or 'ALL'}")

    def _remove_from_event_listeners(
        self, listener: EventListener, event_types: Optional[List[EventType]]
    ) -> None:
        """从对应事件类型列表移除监听器"""
        if event_types is None:
            if listener in self._global_listeners:
                self._global_listeners.remove(listener)
            for et in EventType:
                if listener in self._listeners[et]:
                    self._listeners[et].remove(listener)
        else:
            for et in event_types:
                if listener in self._listeners[et]:
                    self._listeners[et].remove(listener)

    def unsubscribe(
        self,
        listener: EventListener,
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """取消订阅"""
        with self._lock:
            self._remove_from_event_listeners(listener, event_types)

    def publish(self, event: Event, async_mode: bool = False) -> None:
        """
        发布事件

        Args:
            event: 事件对象
            async_mode: 是否异步分发
        """
        self._history.append(event)
        if async_mode:
            self._async_queue.put(event)
        else:
            self._dispatch_sync(event)

    def publish_simple(
        self,
        event_type: EventType,
        payload: Dict[str, Any] = None,
        source: str = "unknown",
        cycle: int = 0,
        async_mode: bool = False
    ) -> None:
        """简化版发布"""
        event = Event(
            event_type=event_type,
            payload=payload or {},
            source=source,
            cycle=cycle,
        )
        self.publish(event, async_mode=async_mode)

    def _get_listeners(self, event_type: EventType) -> Tuple[List[EventListener], List[EventListener]]:
        """获取特定事件类型的监听器副本"""
        with self._lock:
            listeners = self._listeners[event_type].copy()
            global_listeners = self._global_listeners.copy()
        return listeners, global_listeners

    def _notify_listener(self, listener: EventListener, event: Event) -> None:
        """通知单个监听器"""
        try:
            if listener.is_interested(event.event_type):
                listener.on_event(event)
        except Exception as e:
            logger.error(f"Listener '{listener.name}' failed to handle {event.event_type.name}: {e}")

    def _dispatch_sync(self, event: Event) -> None:
        """同步分发事件到所有订阅者"""
        listeners, global_listeners = self._get_listeners(event.event_type)
        for listener in listeners:
            self._notify_listener(listener, event)
        for listener in global_listeners:
            if listener not in listeners:
                self._notify_listener(listener, event)

    def get_recent_events(self, n: int = 100, event_type: Optional[EventType] = None) -> List[Event]:
        """获取最近事件"""
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-n:]

    def get_event_stats(self) -> Dict[str, int]:
        """获取事件统计"""
        with self._lock:
            stats: Dict[str, int] = {}
            for event in self._history:
                name = event.event_type.name
                stats[name] = stats.get(name, 0) + 1
            return stats

    def _should_filter_event(self, event: Event, filters: List[Callable[[Event], bool]]) -> bool:
        """检查事件是否被过滤链阻断"""
        for filt in filters:
            if not filt(event):
                return True
        return False

    def publish_filtered(
        self,
        event: Event,
        filters: List[Callable[[Event], bool]],
        async_mode: bool = False,
    ) -> bool:
        """
        带过滤链的事件发布

        Args:
            event: 事件对象
            filters: 过滤函数列表，任一返回False则阻断
            async_mode: 是否异步分发

        Returns:
            是否成功通过过滤并发布
        """
        if self._should_filter_event(event, filters):
            return False
        self.publish(event, async_mode=async_mode)
        return True

    def _move_to_dead_letter(self, event: Event, error: str) -> None:
        """将失败事件移入死信队列"""
        dead_event = {
            "event": event.to_dict(),
            "error": error,
            "dead_time": time.time(),
        }
        with self._lock:
            self._dead_letter_queue.append(dead_event)

    def get_dead_letter_events(self, n: int = 100) -> List[Dict[str, Any]]:
        """获取死信队列中的事件"""
        with self._lock:
            return list(self._dead_letter_queue)[-n:]

    def retry_dead_letter(self, max_retries: int = 3) -> int:
        """
        重试死信队列中的事件

        Returns:
            成功重试的数量
        """
        success_count = 0
        with self._lock:
            pending = list(self._dead_letter_queue)
            self._dead_letter_queue.clear()

        for item in pending:
            event_data = item["event"]
            event = Event(
                event_type=EventType[event_data["event_type"]],
                payload=event_data["payload"],
                timestamp=event_data["timestamp"],
                source=event_data["source"],
                cycle=event_data["cycle"],
            )
            try:
                self.publish(event)
                success_count += 1
            except Exception as e:
                self._move_to_dead_letter(event, str(e))

        return success_count


class ModuleConnector:
    """
    模块连接器

    第一性原理：模块只通过事件总线通信，禁止直接引用
    - 每个模块持有连接器引用
    - 通过连接器发布和订阅事件
    - 模块间零直接依赖
    """

    def __init__(self, event_bus: EventBus, module_name: str) -> None:
        self.event_bus = event_bus
        self.module_name = module_name
        self._cycle = 0

    def set_cycle(self, cycle: int) -> None:
        """设置当前循环周期"""
        self._cycle = cycle

    def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any] = None,
        async_mode: bool = False
    ) -> None:
        """发布事件"""
        self.event_bus.publish_simple(
            event_type=event_type,
            payload=payload,
            source=self.module_name,
            cycle=self._cycle,
            async_mode=async_mode,
        )

    def subscribe(
        self,
        listener: EventListener,
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """订阅事件"""
        self.event_bus.subscribe(listener, event_types)

    def get_recent_events(self, n: int = 100, event_type: Optional[EventType] = None) -> List[Event]:
        """获取最近事件"""
        return self.event_bus.get_recent_events(n, event_type)

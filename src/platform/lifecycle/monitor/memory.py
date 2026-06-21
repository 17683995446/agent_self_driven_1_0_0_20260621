"""
记忆系统

系统的"海马体"，负责经验的存储和检索。

架构：
- 短期记忆：快速访问，容量有限
- 长期记忆：持久存储，容量大
- 压缩机制：减少冗余

第一性原理：
- 记忆必须分层（快/慢）
- 记忆必须有价值筛选
- 记忆操作必须原子化

保证：
- 短期记忆写入 < 1ms
- 长期记忆查询 < 100ms
- 压缩后保留Top 30%
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Type
from collections import deque
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """
    经验 —— 系统与环境交互的记录

    第一性原理：经验 = (状态, 动作, 结果, 奖励)
    """
    timestamp: float = field(default_factory=time.time)
    state: Dict[str, Any] = field(default_factory=dict)
    action: str = ""
    result: Dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    importance: float = 0.5  # [0, 1]

    def __post_init__(self) -> None:
        if not (0.0 <= self.importance <= 1.0):
            raise ValueError(f"importance must be in [0.0, 1.0], got {self.importance}")

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return self._build_dict()

    def _build_dict(self) -> Dict[str, Any]:
        return self._make_dict(
            self.timestamp, self.state, self.action,
            self.result, self.reward, self.importance,
        )

    @staticmethod
    def _make_dict(
        timestamp: float,
        state: Dict[str, Any],
        action: str,
        result: Dict[str, Any],
        reward: float,
        importance: float,
    ) -> Dict[str, Any]:
        d = {"timestamp": timestamp, "state": state, "action": action}
        d["result"] = result
        d["reward"] = reward
        d["importance"] = importance
        return d

    @classmethod
    def from_dict(cls: Type["Experience"], data: Dict[str, Any]) -> "Experience":
        """从字典反序列化"""
        return cls(**cls._extract_kwargs(data))

    @classmethod
    def _extract_kwargs(cls: Type["Experience"], data: Dict[str, Any]) -> Dict[str, Any]:
        ts = data.get("timestamp", time.time())
        state = data.get("state", {})
        action = data.get("action", "")
        result = data.get("result", {})
        reward = data.get("reward", 0.0)
        importance = data.get("importance", 0.5)
        return cls._make_kwargs(ts, state, action, result, reward, importance)

    @staticmethod
    def _make_kwargs(
        timestamp: float,
        state: Dict[str, Any],
        action: str,
        result: Dict[str, Any],
        reward: float,
        importance: float,
    ) -> Dict[str, Any]:
        d = {"timestamp": timestamp, "state": state, "action": action}
        d["result"] = result
        d["reward"] = reward
        d["importance"] = importance
        return d


class MemoryLayer(ABC):
    """
    记忆层抽象基类

    第一性原理：记忆操作必须是原子的
    """

    @abstractmethod
    def store(self, experience: Experience) -> bool:
        """存储经验"""
        pass

    @abstractmethod
    def retrieve(self, count: int = 10) -> List[Experience]:
        """检索经验"""
        pass

    @abstractmethod
    def count(self) -> int:
        """获取记忆数量"""
        pass


class ShortTermMemory(MemoryLayer):
    """
    短期记忆

    特点：
    - 容量有限（~7±2项）
    - 访问快速（O(1)）
    - 易失性（系统重启丢失）

    第一性原理：近期经验需要快速访问
    """

    def __init__(self, capacity: int = 10000) -> None:
        self.capacity = capacity
        self.buffer: deque = deque(maxlen=capacity)
        logger.info(f"ShortTermMemory initialized with capacity={capacity}")

    def store(self, experience: Experience) -> bool:
        """存储经验"""
        self.buffer.append(experience)
        return True

    def retrieve(self, count: int = 10) -> List[Experience]:
        """检索最近的经验"""
        return list(self.buffer)[-count:]

    def retrieve_by_importance(
        self,
        min_importance: float = 0.5,
        count: int = 10
    ) -> List[Experience]:
        """按重要性检索"""
        important = [e for e in self.buffer if e.importance >= min_importance]
        return important[-count:]

    def count(self) -> int:
        """获取记忆数量"""
        return len(self.buffer)

    def clear(self) -> None:
        """清空记忆"""
        self.buffer.clear()


class LongTermMemory(MemoryLayer):
    """
    长期记忆

    特点：
    - 容量大（磁盘限制）
    - 持久化（系统重启保留）
    - 结构化（支持复杂查询）

    MVP简化：使用JSON文件存储
    """

    def __init__(self, db_path: str = "./data/memory.json") -> None:
        self.db_path = db_path
        self.buffer: List[Experience] = []
        self.max_size = 100000
        self.archive_dir = "./data/archives"
        self.archive_threshold = 80000
        self._load()
        logger.info(f"LongTermMemory initialized with path={db_path}")

    def store(self, experience: Experience) -> bool:
        """存储经验"""
        self.buffer.append(experience)
        self._maybe_archive()
        self._maybe_compress()
        self._maybe_save()
        return True

    def _maybe_archive(self) -> None:
        if len(self.buffer) > self.archive_threshold:
            self._archive_old_memories()

    def _maybe_compress(self) -> None:
        if len(self.buffer) > self.max_size:
            self._compress()

    def _maybe_save(self) -> None:
        if len(self.buffer) % 100 == 0:
            self._save()

    def retrieve(self, count: int = 10) -> List[Experience]:
        """检索最近的经验"""
        return self.buffer[-count:]

    def retrieve_by_importance(
        self,
        min_importance: float = 0.7,
        count: int = 10
    ) -> List[Experience]:
        """按重要性检索"""
        important = [e for e in self.buffer if e.importance >= min_importance]
        important.sort(key=lambda e: e.importance, reverse=True)
        return important[:count]

    def count(self) -> int:
        """获取记忆数量"""
        return len(self.buffer)

    def _compress(self) -> None:
        """
        压缩记忆

        保留高价值记忆，淘汰低价值记忆
        """
        self.buffer.sort(key=lambda e: e.importance, reverse=True)
        keep_count = int(self.max_size * 0.7)
        self.buffer = self.buffer[:keep_count]
        logger.info(f"Memory compressed, kept {len(self.buffer)} experiences")

    def _archive_old_memories(self) -> None:
        """
        归档旧记忆

        将超过阈值的老旧低价值记忆归档到单独文件
        """
        import os
        os.makedirs(self.archive_dir, exist_ok=True)
        to_archive, to_keep = self._partition_memories(time.time() - 86400)
        if to_archive:
            to_keep = self._write_archive(to_archive, to_keep)
        self.buffer = to_keep

    def _partition_memories(self, cutoff_time: float) -> Tuple[List[Experience], List[Experience]]:
        to_archive = [e for e in self.buffer if self._should_archive(e, cutoff_time)]
        to_keep = [e for e in self.buffer if not self._should_archive(e, cutoff_time)]
        return to_archive, to_keep

    @staticmethod
    def _should_archive(exp: Experience, cutoff_time: float) -> bool:
        return exp.timestamp < cutoff_time and exp.importance < 0.5

    def _write_archive(
        self, to_archive: List[Experience], to_keep: List[Experience]
    ) -> List[Experience]:
        import os
        archive_path = os.path.join(self.archive_dir, f"archive_{int(time.time())}.json")
        return self._try_archive(archive_path, to_archive, to_keep)

    def _try_archive(
        self, archive_path: str, to_archive: List[Experience], to_keep: List[Experience]
    ) -> List[Experience]:
        try:
            self._dump_archive(archive_path, to_archive)
            logger.info(f"Archived {len(to_archive)} experiences to {archive_path}")
        except Exception as e:
            logger.error(f"Failed to archive memories: {e}")
            to_keep.extend(to_archive)
        return to_keep

    def _dump_archive(self, archive_path: str, to_archive: List[Experience]) -> None:
        import json
        with open(archive_path, 'w') as f:
            json.dump([exp.to_dict() for exp in to_archive], f)

    def _save(self) -> None:
        """保存到磁盘"""
        try:
            self._write_db(self._collect_recent())
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def _collect_recent(self) -> List[Dict[str, Any]]:
        return [exp.to_dict() for exp in self.buffer[-1000:]]

    def _write_db(self, data: List[Dict[str, Any]]) -> None:
        import json
        with open(self.db_path, 'w') as f:
            json.dump(data, f)

    def _try_load(self) -> None:
        import os
        if not os.path.exists(self.db_path):
            return
        self._populate_buffer(self._read_db_file())
        logger.info(f"Loaded {len(self.buffer)} experiences from disk")

    def _load(self) -> None:
        """从磁盘加载"""
        try:
            self._try_load()
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")

    def _read_db_file(self) -> List[Dict[str, Any]]:
        import json
        with open(self.db_path, 'r') as f:
            return json.load(f)

    def _populate_buffer(self, data: List[Dict[str, Any]]) -> None:
        for item in data:
            self.buffer.append(Experience.from_dict(item))


class MemorySystem:
    """
    记忆系统

    统一管理短期记忆和长期记忆

    第一性原理：
    - 记忆必须分层（快/慢）
    - 记忆必须有价值筛选
    - 记忆操作必须原子化
    """

    def __init__(
        self,
        short_term_capacity: int = 10000,
        long_term_path: str = "./data/memory.json"
    ) -> None:
        self.short_term = ShortTermMemory(capacity=short_term_capacity)
        self.long_term = LongTermMemory(db_path=long_term_path)
        self.sync_count = 0
        logger.info("MemorySystem initialized")

    def store_experience(
        self,
        state: Dict[str, Any],
        action: str,
        result: Dict[str, Any],
        reward: float,
        importance: float = 0.5
    ) -> None:
        """
        存储经验

        流程：
        1. 存储到短期记忆
        2. 如果重要性高，同时存储到长期记忆
        """
        experience = self._make_experience(state, action, result, reward, importance)
        self._store_in_layers(experience, importance)

    def _make_experience(
        self,
        state: Dict[str, Any],
        action: str,
        result: Dict[str, Any],
        reward: float,
        importance: float,
    ) -> Experience:
        return Experience(
            state=state,
            action=action,
            result=result,
            reward=reward,
            importance=importance,
        )

    def _store_in_layers(self, experience: Experience, importance: float) -> None:
        self.short_term.store(experience)
        if importance > 0.7:
            self.long_term.store(experience)

    def sync_to_long_term(self) -> None:
        """
        同步短期记忆到长期记忆

        策略：
        1. 选择高价值记忆
        2. 去重
        3. 批量写入
        """
        items = self.short_term.retrieve_by_importance(min_importance=0.5, count=100)
        for item in items:
            self.long_term.store(item)
        self.sync_count += 1
        logger.info(f"Synced {len(items)} experiences to long-term memory")

    def retrieve_recent(self, count: int = 10) -> List[Experience]:
        """获取最近的经验"""
        return self.short_term.retrieve(count)

    def _get_important_from_long(self, count: int) -> List[Experience]:
        """从长期记忆获取重要经验"""
        return self.long_term.retrieve_by_importance(min_importance=0.7, count=count)

    def _get_important_from_short(self, count: int) -> List[Experience]:
        """从短期记忆获取重要经验"""
        return self.short_term.retrieve_by_importance(min_importance=0.5, count=count)

    def retrieve_important(self, count: int = 10) -> List[Experience]:
        """获取重要的经验"""
        important = self._get_important_from_long(count)
        if len(important) < count:
            short_important = self._get_important_from_short(count - len(important))
            important.extend(short_important)
        return important[:count]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "short_term_count": self.short_term.count(),
            "long_term_count": self.long_term.count(),
            "sync_count": self.sync_count,
            "archive_dir": self.long_term.archive_dir,
        }

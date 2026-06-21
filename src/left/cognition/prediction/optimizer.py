"""
驱力引擎优化器

第一性原理：计算必须高效，否则优化本身成为瓶颈
类比：生物大脑的能量预算——大脑占体重2%但消耗20%能量，必须高效
"""

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable

from ....platform.support.models.base.state import EnvironmentState, DriveRewards


@dataclass
class CacheEntry:
    """缓存条目"""
    value: DriveRewards
    timestamp: float


class RewardCache:
    """奖励计算缓存"""

    def __init__(self, max_size: int = 1000, ttl: float = 1.0) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[int, CacheEntry] = OrderedDict()

    def _state_key(self, state: EnvironmentState) -> int:
        """生成状态键"""
        return hash(state.to_vector())

    def get(self, state: EnvironmentState) -> Optional[DriveRewards]:
        """获取缓存值"""
        key = self._state_key(state)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.ttl:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry.value

    def set(self, state: EnvironmentState, value: DriveRewards) -> None:
        """设置缓存值"""
        key = self._state_key(state)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = CacheEntry(value=value, timestamp=time.time())
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    @property
    def size(self) -> int:
        """当前缓存大小"""
        return len(self._cache)


class DriveEngineOptimizer:
    """
    驱力引擎优化器

    通过缓存和批量计算提升性能
    """

    def __init__(self, cache_size: int = 1000, cache_ttl: float = 1.0) -> None:
        self.cache = RewardCache(max_size=cache_size, ttl=cache_ttl)
        self.hit_count = 0
        self.miss_count = 0

    def compute_with_cache(
        self,
        state: EnvironmentState,
        compute_fn: Callable[[EnvironmentState], DriveRewards],
    ) -> DriveRewards:
        """带缓存的计算"""
        cached = self.cache.get(state)
        if cached is not None:
            self.hit_count += 1
            return cached
        self.miss_count += 1
        result = compute_fn(state)
        self.cache.set(state, result)
        return result

    def batch_compute(
        self,
        states: List[EnvironmentState],
        compute_fn: Callable[[EnvironmentState], DriveRewards],
    ) -> List[DriveRewards]:
        """批量计算"""
        results: List[Optional[DriveRewards]] = [None] * len(states)
        uncached: List[Tuple[int, EnvironmentState]] = []

        for i, state in enumerate(states):
            cached = self.cache.get(state)
            if cached is not None:
                self.hit_count += 1
                results[i] = cached
            else:
                self.miss_count += 1
                uncached.append((i, state))

        if uncached:
            batch_results = [compute_fn(state) for _, state in uncached]
            for (i, state), result in zip(uncached, batch_results):
                results[i] = result
                self.cache.set(state, result)

        return results

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total

    def reset_stats(self) -> None:
        """重置统计"""
        self.hit_count = 0
        self.miss_count = 0

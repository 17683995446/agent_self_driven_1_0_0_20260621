"""
记忆系统性能测试

验证写入速度、查询速度、吞吐量
"""

import time
import tempfile
import os

import pytest

from src.platform.lifecycle.monitor.memory import (
    Experience, ShortTermMemory, LongTermMemory, MemorySystem
)


class TestMemoryPerformance:
    """记忆系统性能测试"""

    def test_stm_write_speed(self):
        """性能：短期记忆写入 < 1ms/条"""
        stm = ShortTermMemory(capacity=100000)
        start = time.perf_counter()
        for i in range(10000):
            stm.store(Experience(action=f"a{i}"))
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 10000) * 1000
        assert avg_ms < 1.0, f"STM write too slow: {avg_ms:.3f}ms"

    def test_stm_retrieve_speed(self):
        """性能：短期记忆检索 < 1ms"""
        stm = ShortTermMemory(capacity=100000)
        for i in range(10000):
            stm.store(Experience(action=f"a{i}", importance=i / 10000.0))
        start = time.perf_counter()
        for _ in range(1000):
            stm.retrieve(count=10)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"STM retrieve too slow: {avg_ms:.3f}ms"

    def test_ltm_write_speed(self):
        """性能：长期记忆写入 < 10ms/条"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "perf.json")
        ltm = LongTermMemory(db_path=db_path)
        start = time.perf_counter()
        for i in range(1000):
            ltm.store(Experience(action=f"a{i}"))
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 10.0, f"LTM write too slow: {avg_ms:.3f}ms"

    def test_ltm_retrieve_speed(self):
        """性能：长期记忆检索 < 10ms"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "perf.json")
        ltm = LongTermMemory(db_path=db_path)
        for i in range(1000):
            ltm.store(Experience(action=f"a{i}", importance=i / 1000.0))
        start = time.perf_counter()
        for _ in range(100):
            ltm.retrieve_by_importance(min_importance=0.5, count=10)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10.0, f"LTM retrieve too slow: {avg_ms:.3f}ms"

    def test_memory_system_throughput(self):
        """性能：记忆系统吞吐量 > 1000条/秒"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "perf.json")
        ms = MemorySystem(long_term_path=db_path)
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            for i in range(100):
                ms.store_experience(
                    state={}, action=f"a{i}", result={}, reward=0.5
                )
            count += 100
        assert count > 1000, f"Throughput too low: {count} exp/sec"

    def test_compression_speed(self):
        """性能：压缩1000条记忆 < 100ms"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "perf.json")
        ltm = LongTermMemory(db_path=db_path)
        for i in range(1000):
            ltm.store(Experience(action=f"a{i}", importance=i / 1000.0))
        ltm.max_size = 500
        start = time.perf_counter()
        ltm._compress()
        elapsed = time.perf_counter() - start
        ms_elapsed = elapsed * 1000
        assert ms_elapsed < 100.0, f"Compression too slow: {ms_elapsed:.3f}ms"

"""
记忆系统测试

验证短期记忆、长期记忆、压缩、一致性
"""

import os
import tempfile
import pytest

from src.platform.lifecycle.monitor.memory import (
    Experience, MemoryLayer, ShortTermMemory, LongTermMemory, MemorySystem
)


class TestExperience:
    """测试经验数据类"""

    def test_normal_creation(self):
        """正常值：创建经验"""
        exp = Experience(action="test", reward=1.0, importance=0.8)
        assert exp.action == "test"
        assert exp.reward == 1.0
        assert exp.importance == 0.8

    def test_default_values(self):
        """正常值：默认值"""
        exp = Experience()
        assert exp.action == ""
        assert exp.reward == 0.0
        assert exp.importance == 0.5
        assert exp.timestamp > 0

    def test_importance_boundary_low(self):
        """边界极值：重要性为0"""
        exp = Experience(importance=0.0)
        assert exp.importance == 0.0

    def test_importance_boundary_high(self):
        """边界极值：重要性为1"""
        exp = Experience(importance=1.0)
        assert exp.importance == 1.0

    def test_invalid_importance(self):
        """非法格式：重要性超出范围"""
        with pytest.raises(ValueError):
            Experience(importance=1.5)

    def test_to_dict_roundtrip(self):
        """正常值：序列化反序列化"""
        exp = Experience(action="a", reward=0.5, importance=0.7)
        d = exp.to_dict()
        restored = Experience.from_dict(d)
        assert restored.action == exp.action
        assert restored.reward == exp.reward
        assert restored.importance == exp.importance


class TestShortTermMemory:
    """测试短期记忆"""

    def setup_method(self):
        self.stm = ShortTermMemory(capacity=100)

    def test_store_and_retrieve(self):
        """正常值：存储和检索"""
        exp = Experience(action="test")
        self.stm.store(exp)
        results = self.stm.retrieve(count=1)
        assert len(results) == 1
        assert results[0].action == "test"

    def test_capacity_limit(self):
        """边界极值：容量限制"""
        stm = ShortTermMemory(capacity=10)
        for i in range(20):
            stm.store(Experience(action=f"a{i}"))
        assert stm.count() == 10

    def test_retrieve_by_importance(self):
        """正常值：按重要性检索"""
        self.stm.store(Experience(action="low", importance=0.3))
        self.stm.store(Experience(action="high", importance=0.9))
        results = self.stm.retrieve_by_importance(min_importance=0.5, count=10)
        assert len(results) == 1
        assert results[0].action == "high"

    def test_empty_retrieve(self):
        """空入参：空记忆检索"""
        results = self.stm.retrieve(count=5)
        assert results == []

    def test_clear(self):
        """正常值：清空"""
        self.stm.store(Experience(action="test"))
        self.stm.clear()
        assert self.stm.count() == 0


class TestLongTermMemory:
    """测试长期记忆"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "memory.json")

    def test_store_and_retrieve(self):
        """正常值：存储和检索"""
        ltm = LongTermMemory(db_path=self.db_path)
        ltm.store(Experience(action="ltm_test", importance=0.8))
        results = ltm.retrieve(count=1)
        assert len(results) == 1
        assert results[0].action == "ltm_test"

    def test_persistence(self):
        """正常值：持久化"""
        ltm1 = LongTermMemory(db_path=self.db_path)
        ltm1.store(Experience(action="persist", importance=0.9))
        ltm1._save()

        ltm2 = LongTermMemory(db_path=self.db_path)
        results = ltm2.retrieve(count=1)
        assert len(results) == 1
        assert results[0].action == "persist"

    def test_retrieve_by_importance(self):
        """正常值：按重要性检索"""
        ltm = LongTermMemory(db_path=self.db_path)
        ltm.store(Experience(action="low", importance=0.3))
        ltm.store(Experience(action="high", importance=0.95))
        results = ltm.retrieve_by_importance(min_importance=0.7, count=10)
        assert len(results) == 1
        assert results[0].action == "high"

    def test_compression_trigger(self):
        """边界：压缩触发"""
        ltm = LongTermMemory(db_path=self.db_path)
        ltm.max_size = 50
        for i in range(60):
            ltm.store(Experience(action=f"a{i}", importance=i / 60.0))
        ltm._compress()
        assert ltm.count() <= 35  # 70% of 50

    def test_empty_retrieve(self):
        """空入参：空记忆检索"""
        ltm = LongTermMemory(db_path=self.db_path)
        results = ltm.retrieve(count=5)
        assert results == []


class TestMemorySystem:
    """测试记忆系统"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "memory.json")

    def test_store_experience(self):
        """正常值：存储经验"""
        ms = MemorySystem(long_term_path=self.db_path)
        ms.store_experience(
            state={"cpu": 0.5}, action="monitor", result={}, reward=0.5
        )
        assert ms.short_term.count() == 1

    def test_high_importance_to_long_term(self):
        """正常值：高重要性存入长期记忆"""
        ms = MemorySystem(long_term_path=self.db_path)
        ms.store_experience(
            state={}, action="important", result={}, reward=1.0, importance=0.8
        )
        assert ms.short_term.count() == 1
        assert ms.long_term.count() >= 1

    def test_sync_to_long_term(self):
        """正常值：同步到长期记忆"""
        ms = MemorySystem(long_term_path=self.db_path)
        for i in range(10):
            ms.store_experience(
                state={}, action=f"a{i}", result={}, reward=0.5, importance=0.6
            )
        ms.sync_to_long_term()
        assert ms.sync_count == 1

    def test_retrieve_important(self):
        """正常值：检索重要经验"""
        ms = MemorySystem(long_term_path=self.db_path)
        ms.store_experience(
            state={}, action="important", result={}, reward=1.0, importance=0.9
        )
        results = ms.retrieve_important(count=1)
        assert len(results) == 1
        assert results[0].action == "important"

    def test_get_stats(self):
        """正常值：统计信息"""
        ms = MemorySystem(long_term_path=self.db_path)
        ms.store_experience(state={}, action="test", result={}, reward=0.5)
        stats = ms.get_stats()
        assert "short_term_count" in stats
        assert "long_term_count" in stats
        assert stats["short_term_count"] == 1


class TestMemoryBoundaryConditions:
    """测试边界条件"""

    def test_zero_capacity(self):
        """边界极值：零容量"""
        stm = ShortTermMemory(capacity=0)
        stm.store(Experience(action="test"))
        assert stm.count() == 0

    def test_large_capacity(self):
        """边界极值：大容量"""
        stm = ShortTermMemory(capacity=100000)
        for i in range(1000):
            stm.store(Experience(action=f"a{i}"))
        assert stm.count() == 1000

    def test_importance_exact_threshold(self):
        """边界：恰好阈值"""
        stm = ShortTermMemory(capacity=10)
        stm.store(Experience(action="exact", importance=0.5))
        results = stm.retrieve_by_importance(min_importance=0.5, count=10)
        assert len(results) == 1

    def test_negative_reward(self):
        """边界：负奖励"""
        exp = Experience(reward=-1.0)
        assert exp.reward == -1.0


class TestMemoryInvalidInputs:
    """测试非法输入"""

    def test_none_state(self):
        """空入参：None状态"""
        exp = Experience(state=None)
        assert exp.state is None

    def test_empty_action(self):
        """空入参：空动作"""
        exp = Experience(action="")
        assert exp.action == ""

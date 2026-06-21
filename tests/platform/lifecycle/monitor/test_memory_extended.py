"""
记忆系统扩展测试

补充覆盖 LongTermMemory、MemorySystem 统计、归档、压缩等路径
"""

import os
import tempfile

import pytest

from src.platform.lifecycle.monitor.memory import (
    MemorySystem, ShortTermMemory, LongTermMemory, Experience, MemoryLayer,
)


class TestMemoryLayerBase:
    """测试记忆层基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            MemoryLayer()


class TestExperience:
    """测试经验数据类"""

    def test_importance_validation(self):
        with pytest.raises(ValueError):
            Experience(importance=2.0)

    def test_importance_negative(self):
        with pytest.raises(ValueError):
            Experience(importance=-0.1)

    def test_valid_importance(self):
        exp = Experience(importance=0.5)
        assert exp.importance == 0.5

    def test_to_dict(self):
        exp = Experience(action="test", reward=1.0, importance=0.8)
        d = exp.to_dict()
        assert d["action"] == "test"
        assert d["reward"] == 1.0
        assert d["importance"] == 0.8

    def test_from_dict(self):
        data = {"action": "test", "reward": 1.0, "importance": 0.8}
        exp = Experience.from_dict(data)
        assert exp.action == "test"
        assert exp.reward == 1.0


class TestShortTermMemoryExtended:
    """测试短期记忆扩展路径"""

    def test_retrieve_by_importance(self):
        memory = ShortTermMemory()
        memory.store(Experience(action="a", importance=0.9))
        memory.store(Experience(action="b", importance=0.3))
        result = memory.retrieve_by_importance(min_importance=0.7, count=10)
        assert len(result) == 1
        assert result[0].action == "a"

    def test_clear(self):
        memory = ShortTermMemory()
        memory.store(Experience(action="a"))
        memory.clear()
        assert memory.count() == 0

    def test_capacity_limit(self):
        memory = ShortTermMemory(capacity=2)
        memory.store(Experience(action="a"))
        memory.store(Experience(action="b"))
        memory.store(Experience(action="c"))
        assert memory.count() == 2


class TestLongTermMemoryExtended:
    """测试长期记忆扩展路径"""

    def test_retrieve_by_importance_empty(self):
        memory = LongTermMemory()
        result = memory.retrieve_by_importance(min_importance=0.9)
        assert result == []

    def test_retrieve_by_importance_filter(self):
        memory = LongTermMemory()
        memory.store(Experience(action="a", reward=1.0, importance=0.9))
        memory.store(Experience(action="b", reward=1.0, importance=0.5))
        result = memory.retrieve_by_importance(min_importance=0.7, count=10)
        assert len(result) == 1
        assert result[0].action == "a"

    def test_compress(self):
        memory = LongTermMemory()
        memory.max_size = 5
        for i in range(10):
            memory.store(Experience(action=str(i), reward=1.0, importance=float(i)/10))
        assert memory.count() <= 5

    def test_archive_old_memories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "memory.json")
            memory = LongTermMemory(db_path=db_path)
            memory.archive_dir = os.path.join(tmpdir, "archives")
            memory.archive_threshold = 5
            # 存储一些旧记忆
            import time
            old_time = time.time() - 90000  # 超过1天
            for i in range(10):
                memory.store(Experience(timestamp=old_time, action=str(i), importance=0.1))
            # 触发归档
            for i in range(10):
                memory.store(Experience(action=str(i), importance=0.1))
            assert memory.count() < 20

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = LongTermMemory(db_path=path)
            memory.store(Experience(state={"k": 1}, action="a", reward=1.0))
            memory._save()
            memory2 = LongTermMemory(db_path=path)
            assert memory2.count() >= 1

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing.json")
            memory = LongTermMemory(db_path=path)
            assert memory.count() == 0

    def test_load_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            with open(path, "w") as f:
                f.write("not json")
            memory = LongTermMemory(db_path=path)
            assert memory.count() == 0

    def test_save_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "readonly.json")
            memory = LongTermMemory(db_path=path)
            memory.store(Experience(action="a"))
            # 使目录只读
            os.chmod(tmpdir, 0o555)
            try:
                memory._save()
            finally:
                os.chmod(tmpdir, 0o755)

    def test_store_triggers_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = LongTermMemory(db_path=path)
            for i in range(100):
                memory.store(Experience(action=str(i)))
            assert os.path.exists(path)


class TestMemorySystemExtended:
    """测试记忆系统扩展路径"""

    def test_store_high_importance_to_long_term(self):
        system = MemorySystem()
        system.store_experience(state={}, action="a", result={}, reward=1.0, importance=0.9)
        assert system.long_term.count() >= 1

    def test_store_low_importance_only_short(self):
        system = MemorySystem()
        system.store_experience(state={}, action="a", result={}, reward=1.0, importance=0.5)
        assert system.short_term.count() == 1
        assert system.long_term.count() == 0

    def test_get_stats(self):
        system = MemorySystem()
        system.store_experience(state={}, action="a", result={}, reward=1.0)
        stats = system.get_stats()
        assert "short_term_count" in stats
        assert "long_term_count" in stats
        assert "sync_count" in stats
        assert "archive_dir" in stats

    def test_retrieve_important_from_both(self):
        system = MemorySystem()
        system.store_experience(state={}, action="a", result={}, reward=1.0, importance=0.9)
        system.sync_to_long_term()
        result = system.retrieve_important(5)
        assert len(result) >= 1

    def test_sync_to_long_term_empty(self):
        system = MemorySystem()
        system.sync_to_long_term()
        assert system.sync_count == 1

    def test_retrieve_important_falls_back_to_short(self):
        system = MemorySystem()
        system.store_experience(state={}, action="a", result={}, reward=1.0, importance=0.6)
        result = system.retrieve_important(5)
        assert len(result) >= 1

"""
记忆系统集成测试

验证记忆与预测、决策等模块的集成
"""

import tempfile
import os

import pytest

from src.platform.lifecycle.monitor.memory import (
    Experience, ShortTermMemory, LongTermMemory, MemorySystem
)
from src.left.cognition.perception.layered_predictor import (
    LowLevelLayerPredictor, LayerInput, EnvironmentState
)
from src.platform.support.models.base.state import GapState, DriveWeights


class TestMemoryPredictionIntegration:
    """测试记忆与预测集成"""

    def test_predictor_uses_memory(self):
        """正常值：预测器利用历史经验"""
        from src.platform.support.models.base.state import SystemState
        stm = ShortTermMemory(capacity=100)
        for i in range(10):
            stm.store(Experience(
                state={"cpu": 0.1 * i, "memory": 0.2 * i},
                action="monitor",
                reward=0.5,
            ))
        recent = stm.retrieve(count=5)
        states = [EnvironmentState(
            system=SystemState(cpu_overall=r.state.get("cpu", 0.5))
        ) for r in recent]
        predictor = LowLevelLayerPredictor(alpha=0.3)
        input_data = LayerInput(state_sequence=states)
        output = predictor.predict(input_data)
        assert output.confidence > 0.0

    def test_memory_influences_gap(self):
        """正常值：记忆影响缺口计算"""
        ms = MemorySystem()
        for i in range(5):
            ms.store_experience(
                state={"cpu": 0.8, "memory": 0.9},
                action="monitor",
                result={},
                reward=0.2,
                importance=0.8,
            )
        important = ms.retrieve_important(count=5)
        assert len(important) > 0
        avg_cpu = sum(e.state.get("cpu", 0.0) for e in important) / len(important)
        assert avg_cpu > 0.5


class TestMemoryDecisionIntegration:
    """测试记忆与决策集成"""

    def test_decision_uses_past_rewards(self):
        """正常值：决策参考历史奖励"""
        stm = ShortTermMemory(capacity=100)
        for i in range(10):
            stm.store(Experience(
                action="safe_task",
                reward=0.9,
                importance=0.8,
            ))
        recent = stm.retrieve(count=5)
        avg_reward = sum(e.reward for e in recent) / len(recent)
        assert avg_reward > 0.5

    def test_exploration_from_memory(self):
        """正常值：从记忆中提取探索方向"""
        stm = ShortTermMemory(capacity=100)
        for i in range(5):
            stm.store(Experience(
                action="explore",
                result={"novelty": 0.8},
                reward=0.7,
                importance=0.9,
            ))
        explore_memories = [
            e for e in stm.retrieve(count=10)
            if e.action == "explore"
        ]
        assert len(explore_memories) > 0


class TestMemoryFullCycle:
    """测试完整记忆周期"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "memory.json")

    def test_full_memory_cycle(self):
        """正常值：完整记忆周期"""
        ms = MemorySystem(long_term_path=self.db_path)

        for i in range(50):
            ms.store_experience(
                state={"cycle": i},
                action=f"action_{i % 3}",
                result={"success": True},
                reward=0.5 + 0.3 * (i % 2),
                importance=0.6,
            )

        ms.sync_to_long_term()
        stats = ms.get_stats()
        assert stats["short_term_count"] == 50
        assert stats["sync_count"] == 1

        important = ms.retrieve_important(count=10)
        assert len(important) > 0

    def test_persistence_across_instances(self):
        """正常值：跨实例持久化"""
        ms1 = MemorySystem(long_term_path=self.db_path)
        ms1.store_experience(
            state={"key": "value"},
            action="test",
            result={},
            reward=1.0,
            importance=0.9,
        )
        ms1.long_term._save()

        ms2 = MemorySystem(long_term_path=self.db_path)
        results = ms2.long_term.retrieve(count=1)
        assert len(results) == 1
        assert results[0].action == "test"


class TestMemoryBoundaryIntegration:
    """测试边界集成条件"""

    def test_empty_memory_prediction(self):
        """空入参：空记忆时预测仍工作"""
        stm = ShortTermMemory(capacity=10)
        recent = stm.retrieve(count=5)
        assert recent == []

    def test_single_memory_cycle(self):
        """边界：单条记忆周期"""
        ms = MemorySystem()
        ms.store_experience(
            state={}, action="only", result={}, reward=1.0, importance=0.9
        )
        assert ms.short_term.count() == 1
        important = ms.retrieve_important(count=1)
        assert len(important) == 1

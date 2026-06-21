"""
数据质量保障测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.perception.quality import DataQualityAssurance, ValidationResult
from src.platform.support.models.base.state import EnvironmentState, SystemState


class TestDataQualityNormal:
    """正常值测试"""

    def test_validate_normal_state(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=0.5, memory_usage=0.3, disk_usage=0.4)
        )
        result = qa.validate(state)
        assert result.valid is True
        assert result.issues == []

    def test_clean_normal_state(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=0.5, memory_usage=0.3, disk_usage=0.4)
        )
        cleaned = qa.clean(state)
        assert cleaned.system.cpu_overall == 0.5


class TestDataQualityBoundary:
    """边界极值测试"""

    def test_validate_exactly_zero(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=0.0, memory_usage=0.0, disk_usage=0.0)
        )
        result = qa.validate(state)
        assert result.valid is True

    def test_validate_exactly_one(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=1.0, memory_usage=1.0, disk_usage=1.0)
        )
        result = qa.validate(state)
        assert result.valid is True

    def test_clean_clips_high(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=1.0, memory_usage=1.0, disk_usage=1.0)
        )
        cleaned = qa.clean(state)
        assert cleaned.system.cpu_overall == 1.0
        assert cleaned.system.memory_usage == 1.0
        assert cleaned.system.disk_usage == 1.0

    def test_clean_clips_low(self):
        qa = DataQualityAssurance()
        state = EnvironmentState(
            system=SystemState(cpu_overall=0.0, memory_usage=0.0, disk_usage=0.0)
        )
        cleaned = qa.clean(state)
        assert cleaned.system.cpu_overall == 0.0
        assert cleaned.system.memory_usage == 0.0
        assert cleaned.system.disk_usage == 0.0


class TestDataQualityInvalid:
    """非法格式测试——SystemState已内置范围检查，验证器不重复检查"""

    def test_validate_detects_timestamp_backwards(self):
        qa = DataQualityAssurance()
        state1 = EnvironmentState(timestamp=10.0)
        qa.validate(state1)
        state2 = EnvironmentState(timestamp=5.0)
        result = qa.validate(state2)
        assert result.valid is False
        assert any("timestamp" in i for i in result.issues)


class TestDataQualityEmpty:
    """空入参测试"""

    def test_validate_default_state(self):
        qa = DataQualityAssurance()
        state = EnvironmentState()
        result = qa.validate(state)
        assert result.valid is True

    def test_clean_default_state(self):
        qa = DataQualityAssurance()
        state = EnvironmentState()
        cleaned = qa.clean(state)
        assert cleaned.system.cpu_overall == 0.0

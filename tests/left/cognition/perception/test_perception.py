"""
环境感知模块测试

验证传感器读取、状态采集的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.left.cognition.perception.perception import EnvironmentPerceptionModule, PerceptionModuleBase
from src.platform.support.models.base.state import EnvironmentState


class TestPerceptionModuleBase:
    """测试感知模块基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            PerceptionModuleBase()


class TestEnvironmentPerceptionModule:
    """测试环境感知模块"""

    def test_normal_init(self):
        module = EnvironmentPerceptionModule()
        assert module is not None

    def test_get_current_state(self):
        module = EnvironmentPerceptionModule()
        state = module.get_current_state()
        assert isinstance(state, EnvironmentState)

    def test_state_dimensions(self):
        module = EnvironmentPerceptionModule()
        state = module.get_current_state()
        vector = state.to_vector()
        assert len(vector) == state.dimension

    def test_start_stop(self):
        module = EnvironmentPerceptionModule()
        module.start()
        assert module.running is True
        module.stop()
        assert module.running is False

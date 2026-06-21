"""
配置加载器扩展测试

补充覆盖 reload、get、验证、默认配置、热加载、动态调参等路径
X2：更新测试以匹配显式失败行为（不再静默回退）
X3：异常类型由 FileNotFoundError/ValueError 统一为 ValidationError
"""

import os
import tempfile
import time

import pytest
from unittest.mock import patch

from src.platform.lifecycle.memory.config_loader import ConfigLoader, ConfigLoaderBase
from src.platform.support.models.base.error_code import ErrorCode, ValidationError


# X2：提供有效配置文件的 fixture，替代 /nonexistent
@pytest.fixture
def valid_config_path(tmp_path):
    """创建有效配置文件"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "environment: test\n"
        "guardrail:\n"
        "  max_cpu_usage: 0.2\n"
        "  max_memory_usage: 0.2\n"
        "decision:\n"
        "  base_exploration_ratio: 0.3\n"
        "perception:\n"
        "  system_poll_interval: 1.0\n"
    )
    return str(config_file)


@pytest.fixture
def loader(valid_config_path):
    """创建已加载配置的 ConfigLoader"""
    return ConfigLoader(config_path=valid_config_path)


class TestConfigLoaderBase:
    """测试配置加载器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            ConfigLoaderBase()


class TestConfigLoaderExtended:
    """测试配置加载器扩展路径"""

    def test_load_missing_file_raises_error(self, tmp_path):
        """X2/X3：配置文件不存在时抛出 ValidationError(CONFIG_NOT_FOUND)"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.CONFIG_NOT_FOUND

    def test_reload_if_changed_no_change(self, valid_config_path):
        loader = ConfigLoader(config_path=valid_config_path)
        result = loader.reload_if_changed()
        assert result is False

    def test_reload_if_changed_with_change(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("perception:\n  poll: 1\n")
        loader = ConfigLoader(config_path=path)
        time.sleep(0.1)
        with open(path, "w") as f:
            f.write("perception:\n  poll: 2\n")
        result = loader.reload_if_changed()
        assert result is True

    def test_reload_notifies_listeners(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("perception:\n  poll: 1\n")
        loader = ConfigLoader(config_path=path)
        notified = []
        def listener(config):
            notified.append(config)
        loader.add_change_listener(listener)
        time.sleep(0.1)
        with open(path, "w") as f:
            f.write("perception:\n  poll: 2\n")
        loader.reload_if_changed()
        assert len(notified) == 1
        loader.remove_change_listener(listener)

    def test_detect_changes(self, loader):
        old = {"a": 1, "b": {"c": 2}}
        new = {"a": 1, "b": {"c": 3, "d": 4}}
        changes = loader._detect_changes(old, new)
        assert "~b.c" in changes
        assert "+b.d" in changes

    def test_get_nested(self, loader):
        loader.config = {"a": {"b": {"c": 1}}}
        assert loader.get("a.b.c") == 1
        assert loader.get("a.b.x") is None
        assert loader.get("a.b.x", "default") == "default"

    def test_get_perception_config(self, loader):
        assert isinstance(loader.get_perception_config(), dict)

    def test_get_drive_engine_config(self, loader):
        assert isinstance(loader.get_drive_engine_config(), dict)

    def test_get_guardrail_config(self, loader):
        assert isinstance(loader.get_guardrail_config(), dict)

    def test_get_decision_config(self, loader):
        assert isinstance(loader.get_decision_config(), dict)

    def test_get_memory_config(self, loader):
        assert isinstance(loader.get_memory_config(), dict)

    def test_get_snapshot_config(self, loader):
        assert isinstance(loader.get_snapshot_config(), dict)

    def test_validate_cpu_invalid(self, loader):
        loader.config = {"guardrail": {"max_cpu_usage": 2.0}}
        with pytest.raises(ValidationError) as exc_info:
            loader._validate_cpu()
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_validate_memory_invalid(self, loader):
        loader.config = {"guardrail": {"max_memory_usage": -1.0}}
        with pytest.raises(ValidationError) as exc_info:
            loader._validate_memory()
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_validate_exploration_invalid(self, loader):
        loader.config = {"decision": {"base_exploration_ratio": 2.0}}
        with pytest.raises(ValidationError) as exc_info:
            loader._validate_exploration()
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_to_dict(self, loader):
        d = loader.to_dict()
        assert "perception" in d

    def test_validate_cpu_valid(self, loader):
        loader.config = {"guardrail": {"max_cpu_usage": 0.5}}
        loader._validate_cpu()
        assert loader.get("guardrail.max_cpu_usage") == 0.5

    def test_validate_memory_valid(self, loader):
        loader.config = {"guardrail": {"max_memory_usage": 0.5}}
        loader._validate_memory()
        assert loader.get("guardrail.max_memory_usage") == 0.5

    def test_validate_exploration_valid(self, loader):
        loader.config = {"decision": {"base_exploration_ratio": 0.5}}
        loader._validate_exploration()
        assert loader.get("decision.base_exploration_ratio") == 0.5

    def test_load_invalid_yaml_raises_error(self, tmp_path):
        """X2：无效 YAML 抛出异常而非静默回退"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("bad: [")
        with pytest.raises(Exception):
            ConfigLoader(config_path=path)

    def test_load_exception_propagates(self, tmp_path):
        """X2：加载异常传播而非回退"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("good: 1")
        loader = ConfigLoader(config_path=path)
        loader.config = {}
        with patch("builtins.open", side_effect=OSError("read error")):
            with pytest.raises(OSError):
                loader.load()

    def test_set_nested_new_key(self, loader):
        loader.config = {}
        loader._set_nested("a.b.c", 1)
        assert loader.config["a"]["b"]["c"] == 1


class TestConfigLoaderHotReload:
    """测试热加载功能"""

    def test_start_stop_hot_reload(self, loader):
        loader.start_hot_reload(interval=0.1)
        assert loader._hot_reload_enabled is True
        time.sleep(0.15)
        loader.stop_hot_reload()
        assert loader._hot_reload_enabled is False

    def test_hot_reload_detects_change(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("perception:\n  poll: 1\n")
        loader = ConfigLoader(config_path=path)
        loader.start_hot_reload(interval=0.1)
        time.sleep(0.15)
        with open(path, "w") as f:
            f.write("perception:\n  poll: 99\n")
        time.sleep(0.2)
        assert loader.get("perception.poll") == 99
        loader.stop_hot_reload()


class TestConfigLoaderDynamicParams:
    """测试动态调参功能"""

    def test_set_param(self, loader):
        result = loader.set_param("guardrail.max_cpu_usage", 0.5)
        assert result is True
        assert loader.get("guardrail.max_cpu_usage") == 0.5

    def test_set_param_invalid(self, loader):
        result = loader.set_param("guardrail.max_cpu_usage", 2.0)
        assert result is False
        assert loader.get("guardrail.max_cpu_usage") == 0.2

    def test_get_param_info(self, loader):
        info = loader.get_param_info("guardrail.max_cpu_usage")
        assert info["key"] == "guardrail.max_cpu_usage"
        assert "value" in info
        assert "type" in info

    def test_list_params(self, loader):
        keys = loader.list_params()
        assert "perception.system_poll_interval" in keys
        assert "guardrail.max_cpu_usage" in keys

    def test_list_params_with_prefix(self, loader):
        keys = loader.list_params("guardrail")
        assert all(k.startswith("guardrail") for k in keys)


class TestConfigLoaderSnapshot:
    """测试配置快照与回滚"""

    def test_snapshot_config(self, loader):
        snapshot = loader.snapshot_config()
        assert "config" in snapshot
        assert "timestamp" in snapshot
        assert "path" in snapshot
        assert snapshot["config"]["guardrail"]["max_cpu_usage"] == 0.2

    def test_restore_config(self, loader):
        original = loader.get("guardrail.max_cpu_usage")
        snapshot = loader.snapshot_config()
        loader.set_param("guardrail.max_cpu_usage", 0.99)
        result = loader.restore_config(snapshot)
        assert result is True
        assert loader.get("guardrail.max_cpu_usage") == original

    def test_restore_invalid_snapshot(self, loader):
        result = loader.restore_config({"timestamp": 0})
        assert result is False


class TestConfigLoaderAtomicUpdate:
    """测试原子性批量更新"""

    def test_atomic_update_all_valid(self, loader):
        original = loader.get("guardrail.max_cpu_usage")
        result = loader.set_params_atomic({
            "guardrail.max_cpu_usage": 0.5,
            "guardrail.max_memory_usage": 0.6,
        })
        assert result is True
        assert loader.get("guardrail.max_cpu_usage") == 0.5
        assert loader.get("guardrail.max_memory_usage") == 0.6

    def test_atomic_update_rollback_on_invalid(self, loader):
        original_cpu = loader.get("guardrail.max_cpu_usage")
        original_mem = loader.get("guardrail.max_memory_usage")
        result = loader.set_params_atomic({
            "guardrail.max_cpu_usage": 0.5,
            "guardrail.max_memory_usage": 2.0,
        })
        assert result is False
        assert loader.get("guardrail.max_cpu_usage") == original_cpu
        assert loader.get("guardrail.max_memory_usage") == original_mem

    def test_atomic_update_empty(self, loader):
        result = loader.set_params_atomic({})
        assert result is True

    def test_boundary_exact_limits(self, loader):
        result = loader.set_params_atomic({
            "guardrail.max_cpu_usage": 1.0,
            "guardrail.max_memory_usage": 0.01,
        })
        assert result is True
        assert loader.get("guardrail.max_cpu_usage") == 1.0
        assert loader.get("guardrail.max_memory_usage") == 0.01

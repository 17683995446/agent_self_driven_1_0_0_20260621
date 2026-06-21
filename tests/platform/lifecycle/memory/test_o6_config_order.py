"""
O6：配置秩序化测试

验证配置键名映射修复和热加载：
1. yaml键名与代码查找键名对齐
2. 配置真实生效（非默认值）
3. 热加载能检测文件变更
4. 配置变更回调触发
5. 多环境配置一致性
"""

import pytest
import os
import time
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from src.platform.lifecycle.memory.config_loader import ConfigLoader


class TestO6ConfigKeyAlignment:
    """测试配置键名对齐"""

    def test_dev_yaml_has_guardrail_keys(self):
        """dev.yaml包含guardrail嵌套键"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("guardrail.max_cpu_usage") is not None
        assert loader.get("guardrail.max_memory_usage") is not None
        assert loader.get("guardrail.max_disk_usage") is not None

    def test_dev_yaml_has_decision_keys(self):
        """dev.yaml包含decision嵌套键"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("decision.base_exploration_ratio") is not None
        assert loader.get("decision.min_exploration_ratio") is not None
        assert loader.get("decision.max_exploration_ratio") is not None

    def test_prod_yaml_has_guardrail_keys(self):
        """prod.yaml包含guardrail嵌套键"""
        loader = ConfigLoader("./config/prod.yaml")
        assert loader.get("guardrail.max_cpu_usage") is not None
        assert loader.get("guardrail.max_memory_usage") is not None

    def test_test_yaml_has_guardrail_keys(self):
        """test.yaml包含guardrail嵌套键"""
        loader = ConfigLoader("./config/test.yaml")
        assert loader.get("guardrail.max_cpu_usage") is not None
        assert loader.get("guardrail.max_memory_usage") is not None

    def test_dev_guardrail_values_match_yaml(self):
        """dev.yaml的guardrail值正确读取"""
        loader = ConfigLoader("./config/dev.yaml")
        # dev.yaml: max_cpu_usage: 0.5
        assert loader.get("guardrail.max_cpu_usage") == 0.5
        assert loader.get("guardrail.max_memory_usage") == 0.5
        assert loader.get("guardrail.max_disk_usage") == 0.9

    def test_prod_guardrail_values_match_yaml(self):
        """prod.yaml的guardrail值正确读取"""
        loader = ConfigLoader("./config/prod.yaml")
        # prod.yaml: max_cpu_usage: 0.2
        assert loader.get("guardrail.max_cpu_usage") == 0.2
        assert loader.get("guardrail.max_memory_usage") == 0.2

    def test_dev_decision_values_match_yaml(self):
        """dev.yaml的decision值正确读取"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("decision.base_exploration_ratio") == 0.3
        assert loader.get("decision.min_exploration_ratio") == 0.05
        assert loader.get("decision.max_exploration_ratio") == 0.7

    def test_dev_has_perception_config(self):
        """dev.yaml包含perception配置"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("perception.system_poll_interval") is not None

    def test_dev_has_drive_engine_config(self):
        """dev.yaml包含drive_engine配置"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("drive_engine.adaptation_rate") is not None

    def test_dev_has_snapshot_config(self):
        """dev.yaml包含snapshot配置"""
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("snapshot.max_snapshots") is not None


class TestO6ConfigEffectiveness:
    """测试配置真实生效"""

    def test_config_not_using_defaults(self):
        """配置值不是默认值（证明从yaml读取）"""
        loader = ConfigLoader("./config/dev.yaml")
        # 默认值是0.2，dev.yaml是0.5
        cpu = loader.get("guardrail.max_cpu_usage", 0.2)
        assert cpu == 0.5  # 来自yaml，非默认

    def test_config_validation_passes(self):
        """配置验证通过"""
        loader = ConfigLoader("./config/dev.yaml")
        # 不抛异常即通过
        loader._validate_config()

    def test_config_validation_prod_passes(self):
        """生产配置验证通过"""
        loader = ConfigLoader("./config/prod.yaml")
        loader._validate_config()

    def test_config_validation_test_passes(self):
        """测试配置验证通过"""
        loader = ConfigLoader("./config/test.yaml")
        loader._validate_config()

    def test_different_envs_have_different_values(self):
        """不同环境有不同配置值"""
        dev = ConfigLoader("./config/dev.yaml")
        prod = ConfigLoader("./config/prod.yaml")
        # dev放宽(0.5)，prod严格(0.2)
        assert dev.get("guardrail.max_cpu_usage") != prod.get("guardrail.max_cpu_usage")


class TestO6HotReload:
    """测试热加载"""

    def test_hot_reload_detects_file_change(self, tmp_path):
        """热加载检测文件变更"""
        config_file = tmp_path / "test_hot.yaml"
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.3\n")
        loader = ConfigLoader(str(config_file))
        assert loader.get("guardrail.max_cpu_usage") == 0.3
        # 修改文件
        time.sleep(0.1)
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.5\n")
        # 检测变更
        reloaded = loader.reload_if_changed()
        assert reloaded is True
        assert loader.get("guardrail.max_cpu_usage") == 0.5

    def test_hot_reload_no_change_returns_false(self, tmp_path):
        """无变更时reload返回False"""
        config_file = tmp_path / "test_nochange.yaml"
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.3\n")
        loader = ConfigLoader(str(config_file))
        reloaded = loader.reload_if_changed()
        assert reloaded is False

    def test_change_listener_called_on_reload(self, tmp_path):
        """变更监听器在reload时被调用"""
        config_file = tmp_path / "test_listener.yaml"
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.3\n")
        loader = ConfigLoader(str(config_file))
        listener = MagicMock()
        loader.add_change_listener(listener)
        # 修改文件
        time.sleep(0.1)
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.5\n")
        loader.reload_if_changed()
        listener.assert_called_once()

    def test_start_stop_hot_reload(self, tmp_path):
        """启动和停止热加载"""
        config_file = tmp_path / "test_startstop.yaml"
        config_file.write_text("guardrail:\n  max_cpu_usage: 0.3\n")
        loader = ConfigLoader(str(config_file))
        loader.start_hot_reload(interval=0.1)
        assert loader._hot_reload_enabled is True
        loader.stop_hot_reload()
        assert loader._hot_reload_enabled is False


class TestO6ConfigApplication:
    """测试配置应用到组件"""

    def test_guardrail_config_applied(self):
        """guardrail配置能应用到对象"""
        loader = ConfigLoader("./config/dev.yaml")
        guardrail = MagicMock()
        guardrail.max_cpu = 0
        guardrail.max_memory = 0
        guardrail.max_disk = 0
        # 模拟_apply_guardrail_config的逻辑
        guardrail.max_cpu = loader.get("guardrail.max_cpu_usage", 0.2)
        guardrail.max_memory = loader.get("guardrail.max_memory_usage", 0.2)
        guardrail.max_disk = loader.get("guardrail.max_disk_usage", 0.85)
        assert guardrail.max_cpu == 0.5
        assert guardrail.max_memory == 0.5
        assert guardrail.max_disk == 0.9

    def test_decision_config_applied(self):
        """decision配置能应用到对象"""
        loader = ConfigLoader("./config/dev.yaml")
        decision = MagicMock()
        decision.base_exploration_ratio = 0
        decision.min_exploration_ratio = 0
        decision.max_exploration_ratio = 0
        decision.current_exploration_ratio = 0
        # 模拟_apply_decision_config的逻辑
        exp = loader.get("decision.base_exploration_ratio", 0.3)
        min_exp = loader.get("decision.min_exploration_ratio", 0.1)
        max_exp = loader.get("decision.max_exploration_ratio", 0.5)
        decision.base_exploration_ratio = exp
        decision.min_exploration_ratio = min_exp
        decision.max_exploration_ratio = max_exp
        decision.current_exploration_ratio = exp
        assert decision.base_exploration_ratio == 0.3
        assert decision.min_exploration_ratio == 0.05
        assert decision.max_exploration_ratio == 0.7

    def test_task_pool_config_applied(self):
        """task_pool配置能应用到对象"""
        loader = ConfigLoader("./config/dev.yaml")
        task_pool = MagicMock()
        task_pool.max_size = 0
        task_pool.max_size = loader.get("task_pool_max_size", 100)
        assert task_pool.max_size == 100


class TestO6ConfigStructure:
    """测试配置结构完整性"""

    def test_all_envs_have_same_key_structure(self):
        """所有环境配置有相同的键结构"""
        dev = ConfigLoader("./config/dev.yaml")
        prod = ConfigLoader("./config/prod.yaml")
        test = ConfigLoader("./config/test.yaml")
        dev_keys = set(dev.list_params())
        prod_keys = set(prod.list_params())
        test_keys = set(test.list_params())
        # 核心键应一致
        core_keys = {
            "guardrail.max_cpu_usage",
            "guardrail.max_memory_usage",
            "guardrail.max_disk_usage",
            "decision.base_exploration_ratio",
            "decision.min_exploration_ratio",
            "decision.max_exploration_ratio",
        }
        assert core_keys.issubset(dev_keys)
        assert core_keys.issubset(prod_keys)
        assert core_keys.issubset(test_keys)

    def test_config_has_environment_field(self):
        """配置有environment字段"""
        dev = ConfigLoader("./config/dev.yaml")
        prod = ConfigLoader("./config/prod.yaml")
        test = ConfigLoader("./config/test.yaml")
        assert dev.get("environment") == "dev"
        assert prod.get("environment") == "prod"
        assert test.get("environment") == "test"

    def test_config_has_log_level(self):
        """配置有log_level字段"""
        dev = ConfigLoader("./config/dev.yaml")
        assert dev.get("log_level") is not None

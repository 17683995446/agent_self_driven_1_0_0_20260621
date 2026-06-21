"""
U1：配置路径一致性测试

验证配置路径解析逻辑：
1. 环境变量 AGENT_CONFIG_PATH 优先
2. 无环境变量时回退到默认 ./config/dev.yaml
3. ConfigLoader 默认路径正确
4. 启动日志打印实际加载路径

第一性原理：配置路径必须三方一致（代码/脚本/Docker）
"""

import pytest
import os
from unittest.mock import patch

from src.platform.lifecycle.memory.config_loader import ConfigLoader


class TestU1ConfigPathResolution:
    """测试配置路径解析"""

    def test_env_var_overrides_default(self, monkeypatch, tmp_path):
        """环境变量 AGENT_CONFIG_PATH 优先于默认值"""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("environment: custom\nlog_level: INFO\n")
        monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_file))

        from src.main import AgentSystem
        # 只测试路径解析逻辑，不完整初始化
        agent = object.__new__(AgentSystem)
        agent._cli_config_path = None
        path = agent._resolve_config_path()
        assert path == str(config_file)

    def test_default_path_when_no_env(self, monkeypatch):
        """无环境变量时使用默认路径"""
        monkeypatch.delenv("AGENT_CONFIG_PATH", raising=False)
        from src.main import AgentSystem
        agent = object.__new__(AgentSystem)
        agent._cli_config_path = None
        path = agent._resolve_config_path()
        assert path == "./config/dev.yaml"

    def test_empty_env_var_falls_back_to_default(self, monkeypatch):
        """空环境变量回退到默认"""
        monkeypatch.setenv("AGENT_CONFIG_PATH", "")
        from src.main import AgentSystem
        agent = object.__new__(AgentSystem)
        agent._cli_config_path = None
        path = agent._resolve_config_path()
        assert path == "./config/dev.yaml"


class TestU1ConfigLoaderDefaultPath:
    """测试ConfigLoader默认路径"""

    def test_default_path_is_dev_yaml(self):
        """ConfigLoader默认路径是 ./config/dev.yaml"""
        import inspect
        sig = inspect.signature(ConfigLoader.__init__)
        default = sig.parameters["config_path"].default
        assert default == "./config/dev.yaml"

    def test_default_path_not_configs_default(self):
        """默认路径不是错误的 ./configs/default.yaml"""
        import inspect
        sig = inspect.signature(ConfigLoader.__init__)
        default = sig.parameters["config_path"].default
        assert default != "./configs/default.yaml"


class TestU1ConfigLoadingFromEnvVar:
    """测试通过环境变量加载配置"""

    def test_loads_prod_config_via_env(self, monkeypatch, tmp_path):
        """通过环境变量加载prod配置"""
        config_file = tmp_path / "prod.yaml"
        config_file.write_text(
            "environment: prod\n"
            "log_level: WARNING\n"
            "guardrail:\n"
            "  max_cpu_usage: 0.2\n"
        )
        monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_file))
        loader = ConfigLoader(str(config_file))
        assert loader.get("environment") == "prod"
        assert loader.get("log_level") == "WARNING"
        assert loader.get("guardrail.max_cpu_usage") == 0.2

    def test_loads_dev_config_by_default(self):
        """默认加载dev配置"""
        os.chdir("/workspace/self_driven_agent")
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("environment") == "dev"

    def test_config_path_stored(self, tmp_path):
        """配置路径被存储"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("environment: test\n")
        loader = ConfigLoader(str(config_file))
        assert loader.config_path == str(config_file)


class TestU1ConfigPathConsistency:
    """测试配置路径一致性"""

    def test_dev_yaml_exists(self):
        """dev.yaml 存在"""
        os.chdir("/workspace/self_driven_agent")
        assert os.path.isfile("./config/dev.yaml")

    def test_prod_yaml_exists(self):
        """prod.yaml 存在"""
        os.chdir("/workspace/self_driven_agent")
        assert os.path.isfile("./config/prod.yaml")

    def test_test_yaml_exists(self):
        """test.yaml 存在"""
        os.chdir("/workspace/self_driven_agent")
        assert os.path.isfile("./config/test.yaml")

    def test_no_default_yaml(self):
        """不存在 default.yaml（文档不应引用）"""
        os.chdir("/workspace/self_driven_agent")
        assert not os.path.isfile("./config/default.yaml")

    def test_dev_and_prod_have_different_values(self):
        """dev和prod配置值不同"""
        os.chdir("/workspace/self_driven_agent")
        dev = ConfigLoader("./config/dev.yaml")
        prod = ConfigLoader("./config/prod.yaml")
        assert dev.get("environment") != prod.get("environment")

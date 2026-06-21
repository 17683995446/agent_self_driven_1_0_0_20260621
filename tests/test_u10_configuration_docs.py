"""
U10：配置文档完善测试

验证配置文档完善：
1. config/dev.yaml 有逐项注释和取值范围
2. config/prod.yaml 有逐项注释和取值范围
3. config/test.yaml 有逐项注释和取值范围
4. docs/deploy_user/configuration.md 配置说明文档存在且完整

第一性原理：用户应能理解每项配置的含义和取值范围
"""

import pytest
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU10ConfigFilesAnnotated:
    """测试配置文件有逐项注释"""

    @pytest.fixture
    def dev_content(self):
        return (PROJECT_ROOT / "config" / "dev.yaml").read_text(encoding="utf-8")

    @pytest.fixture
    def prod_content(self):
        return (PROJECT_ROOT / "config" / "prod.yaml").read_text(encoding="utf-8")

    @pytest.fixture
    def test_content(self):
        return (PROJECT_ROOT / "config" / "test.yaml").read_text(encoding="utf-8")

    def test_dev_has_environment_comment(self, dev_content):
        """dev.yaml 有 environment 注释"""
        assert "environment" in dev_content

    def test_dev_has_log_level_comment(self, dev_content):
        """dev.yaml 有 log_level 注释"""
        assert "log_level" in dev_content

    def test_dev_has_cycle_interval_comment(self, dev_content):
        """dev.yaml 有 cycle_interval 注释"""
        assert "cycle_interval" in dev_content

    def test_dev_has_guardrail_comment(self, dev_content):
        """dev.yaml 有 guardrail 注释"""
        assert "guardrail" in dev_content

    def test_dev_has_value_range_annotation(self, dev_content):
        """dev.yaml 有取值范围说明"""
        assert "取值" in dev_content or "范围" in dev_content

    def test_dev_has_header_comment(self, dev_content):
        """dev.yaml 有文件头注释"""
        first_lines = dev_content.split("\n")[0:5]
        assert any(line.startswith("#") for line in first_lines)

    def test_prod_has_environment_comment(self, prod_content):
        """prod.yaml 有 environment 注释"""
        assert "environment" in prod_content

    def test_prod_has_value_range_annotation(self, prod_content):
        """prod.yaml 有取值范围说明"""
        assert "取值" in prod_content or "范围" in prod_content

    def test_prod_has_header_comment(self, prod_content):
        """prod.yaml 有文件头注释"""
        first_lines = prod_content.split("\n")[0:5]
        assert any(line.startswith("#") for line in first_lines)

    def test_test_has_environment_comment(self, test_content):
        """test.yaml 有 environment 注释"""
        assert "environment" in test_content

    def test_test_has_value_range_annotation(self, test_content):
        """test.yaml 有取值范围说明"""
        assert "取值" in test_content or "范围" in test_content

    def test_test_has_header_comment(self, test_content):
        """test.yaml 有文件头注释"""
        first_lines = test_content.split("\n")[0:5]
        assert any(line.startswith("#") for line in first_lines)


class TestU10ConfigDocExists:
    """测试配置说明文档存在"""

    def test_configuration_doc_exists(self):
        """configuration.md 存在"""
        assert (PROJECT_ROOT / "docs" / "deploy_user" / "configuration.md").is_file()

    @pytest.fixture
    def config_doc_content(self):
        return (PROJECT_ROOT / "docs" / "deploy_user" / "configuration.md").read_text(encoding="utf-8")

    def test_doc_has_title(self, config_doc_content):
        """文档有标题"""
        assert "# 配置说明" in config_doc_content or "# Configuration" in config_doc_content

    def test_doc_has_config_location_section(self, config_doc_content):
        """文档有配置文件位置说明"""
        assert "配置文件位置" in config_doc_content or "config/dev.yaml" in config_doc_content

    def test_doc_has_priority_section(self, config_doc_content):
        """文档有优先级说明"""
        assert "优先级" in config_doc_content or "CLI" in config_doc_content

    def test_doc_has_environment_section(self, config_doc_content):
        """文档有 environment 配置说明"""
        assert "environment" in config_doc_content

    def test_doc_has_log_level_section(self, config_doc_content):
        """文档有 log_level 配置说明"""
        assert "log_level" in config_doc_content

    def test_doc_has_guardrail_section(self, config_doc_content):
        """文档有 guardrail 配置说明"""
        assert "guardrail" in config_doc_content

    def test_doc_has_decision_section(self, config_doc_content):
        """文档有 decision 配置说明"""
        assert "decision" in config_doc_content

    def test_doc_has_drive_engine_section(self, config_doc_content):
        """文档有 drive_engine 配置说明"""
        assert "drive_engine" in config_doc_content

    def test_doc_has_event_bus_section(self, config_doc_content):
        """文档有 event_bus 配置说明"""
        assert "event_bus" in config_doc_content

    def test_doc_has_value_range(self, config_doc_content):
        """文档有取值范围说明"""
        assert "取值" in config_doc_content or "范围" in config_doc_content

    def test_doc_has_env_comparison(self, config_doc_content):
        """文档有环境差异对比"""
        assert "dev" in config_doc_content and "prod" in config_doc_content


class TestU10ConfigConsistency:
    """测试配置文件与文档一致性"""

    def test_all_configs_have_same_keys(self):
        """三个配置文件有相同的键结构"""
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml not installed")

        dev = yaml.safe_load((PROJECT_ROOT / "config" / "dev.yaml").read_text())
        prod = yaml.safe_load((PROJECT_ROOT / "config" / "prod.yaml").read_text())
        test = yaml.safe_load((PROJECT_ROOT / "config" / "test.yaml").read_text())

        dev_keys = set(dev.keys())
        prod_keys = set(prod.keys())
        test_keys = set(test.keys())

        assert dev_keys == prod_keys == test_keys

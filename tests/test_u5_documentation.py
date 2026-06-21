"""
U5：README和文档修正测试

验证文档修正：
1. README.md 存在且内容完整
2. quick_start.md 不再引用 default.yaml
3. setup.md 目录结构正确
4. testing.md 测试路径正确
5. troubleshooting.md 不再引用 default.yaml

第一性原理：文档是用户的第一入口，必须准确
"""

import pytest
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU5Readme:
    """测试根README.md"""

    def test_readme_exists(self):
        """README.md 存在"""
        assert (PROJECT_ROOT / "README.md").is_file()

    def test_readme_has_title(self):
        """README 有标题"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "# 自驱永续进化Agent系统" in content

    def test_readme_has_quick_start(self):
        """README 有快速开始"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "快速开始" in content
        assert "pip install" in content

    def test_readme_has_cli_usage(self):
        """README 有CLI使用说明"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "self-driven-agent" in content
        assert "--env" in content

    def test_readme_has_env_var(self):
        """README 有环境变量说明"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "AGENT_CONFIG_PATH" in content

    def test_readme_has_project_structure(self):
        """README 有项目结构"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "src/" in content
        assert "left/" in content
        assert "platform/" in content

    def test_readme_has_dependency_section(self):
        """README 有依赖说明"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "pyyaml" in content
        assert "numpy" in content
        assert "psutil" in content

    def test_readme_not_reference_default_yaml(self):
        """README 不引用 default.yaml"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "default.yaml" not in content

    def test_readme_not_reference_src_core(self):
        """README 不引用 src/core（错误目录）"""
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "src/core" not in content


class TestU5QuickStartFixed:
    """测试quick_start.md修正"""

    def test_no_default_yaml_reference(self):
        """不再引用 default.yaml"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "quick_start.md").read_text(encoding="utf-8")
        assert "default.yaml" not in content

    def test_references_dev_yaml(self):
        """引用 dev.yaml"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "quick_start.md").read_text(encoding="utf-8")
        assert "dev.yaml" in content

    def test_has_console_script(self):
        """有console_scripts入口"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "quick_start.md").read_text(encoding="utf-8")
        assert "self-driven-agent" in content

    def test_has_pip_install_e(self):
        """有 pip install -e . 安装方式"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "quick_start.md").read_text(encoding="utf-8")
        assert "pip install -e ." in content

    def test_has_env_var_example(self):
        """有环境变量示例"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "quick_start.md").read_text(encoding="utf-8")
        assert "AGENT_CONFIG_PATH" in content


class TestU5SetupFixed:
    """测试setup.md修正"""

    def test_no_src_core_reference(self):
        """不再引用 src/core"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "setup.md").read_text(encoding="utf-8")
        assert "src/core" not in content

    def test_has_correct_structure(self):
        """有正确的目录结构"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "setup.md").read_text(encoding="utf-8")
        assert "left/" in content
        assert "platform/" in content
        assert "cognition/" in content
        assert "action/" in content

    def test_no_assets_reference(self):
        """不再引用 assets/"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "setup.md").read_text(encoding="utf-8")
        assert "assets/" not in content

    def test_python_version_38(self):
        """Python版本要求3.8+"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "setup.md").read_text(encoding="utf-8")
        assert "3.8" in content

    def test_has_pip_install_e(self):
        """有 pip install -e . 安装方式"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "setup.md").read_text(encoding="utf-8")
        assert "pip install -e ." in content


class TestU5TestingFixed:
    """测试testing.md修正"""

    def test_no_core_test_path(self):
        """不再引用 tests/core/"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "testing.md").read_text(encoding="utf-8")
        assert "tests/core/" not in content

    def test_has_correct_test_path(self):
        """有正确的测试路径"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "testing.md").read_text(encoding="utf-8")
        assert "tests/left/action/decision/" in content


class TestU5TroubleshootingFixed:
    """测试troubleshooting.md修正"""

    def test_no_default_yaml_reference(self):
        """不再引用 default.yaml"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "troubleshooting.md").read_text(encoding="utf-8")
        assert "default.yaml" not in content

    def test_references_dev_yaml(self):
        """引用 dev.yaml"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "troubleshooting.md").read_text(encoding="utf-8")
        assert "dev.yaml" in content

    def test_has_dry_run(self):
        """有 dry-run 验证步骤"""
        content = (PROJECT_ROOT / "docs" / "deploy_user" / "troubleshooting.md").read_text(encoding="utf-8")
        assert "dry-run" in content


class TestU5AllDocsConsistent:
    """测试所有文档一致性"""

    @pytest.mark.parametrize("doc_file", [
        "README.md",
        "docs/deploy_user/quick_start.md",
        "docs/deploy_user/setup.md",
        "docs/deploy_user/troubleshooting.md",
    ])
    def test_no_default_yaml_in_any_doc(self, doc_file):
        """所有文档不引用 default.yaml"""
        content = (PROJECT_ROOT / doc_file).read_text(encoding="utf-8")
        assert "default.yaml" not in content, f"{doc_file} 仍引用 default.yaml"

    @pytest.mark.parametrize("doc_file", [
        "README.md",
        "docs/deploy_user/setup.md",
    ])
    def test_no_src_core_in_any_doc(self, doc_file):
        """关键文档不引用 src/core"""
        content = (PROJECT_ROOT / doc_file).read_text(encoding="utf-8")
        assert "src/core" not in content, f"{doc_file} 仍引用 src/core"

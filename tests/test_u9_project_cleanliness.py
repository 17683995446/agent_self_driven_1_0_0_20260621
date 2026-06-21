"""
U9：项目整洁和.gitignore测试

验证项目整洁性：
1. .gitignore 存在且覆盖所有运行时产物
2. 运行时目录有 .gitkeep 占位
3. 不应入库的文件被忽略

第一性原理：版本控制应只包含源代码和必要配置，运行时产物应被忽略
"""

import pytest
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU9GitignoreExists:
    """测试.gitignore存在"""

    def test_gitignore_exists(self):
        """.gitignore 存在"""
        assert (PROJECT_ROOT / ".gitignore").is_file()

    def test_gitignore_not_empty(self):
        """.gitignore 不为空"""
        content = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert len(content.strip()) > 0


class TestU9GitignoreCoversPythonArtifacts:
    """测试.gitignore覆盖Python产物"""

    @pytest.fixture
    def gitignore_content(self):
        return (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_ignores_pycache(self, gitignore_content):
        """忽略 __pycache__"""
        assert "__pycache__" in gitignore_content

    def test_ignores_pyc_files(self, gitignore_content):
        """忽略 .pyc 文件"""
        assert "*.pyc" in gitignore_content or "*.py[cod]" in gitignore_content

    def test_ignores_egg_info(self, gitignore_content):
        """忽略 egg-info"""
        assert "egg-info" in gitignore_content

    def test_ignores_build_dist(self, gitignore_content):
        """忽略 build/dist"""
        assert "build" in gitignore_content
        assert "dist" in gitignore_content


class TestU9GitignoreCoversTestArtifacts:
    """测试.gitignore覆盖测试产物"""

    @pytest.fixture
    def gitignore_content(self):
        return (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_ignores_pytest_cache(self, gitignore_content):
        """忽略 .pytest_cache"""
        assert ".pytest_cache" in gitignore_content

    def test_ignores_coverage(self, gitignore_content):
        """忽略 .coverage"""
        assert ".coverage" in gitignore_content

    def test_ignores_htmlcov(self, gitignore_content):
        """忽略 htmlcov"""
        assert "htmlcov" in gitignore_content


class TestU9GitignoreCoversRuntimeArtifacts:
    """测试.gitignore覆盖运行时产物"""

    @pytest.fixture
    def gitignore_content(self):
        return (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_ignores_logs(self, gitignore_content):
        """忽略 logs 目录内容"""
        assert "logs" in gitignore_content

    def test_ignores_test_snapshots(self, gitignore_content):
        """忽略 test_snapshots 目录内容"""
        assert "test_snapshots" in gitignore_content

    def test_ignores_data_runtime(self, gitignore_content):
        """忽略 data 目录运行时数据"""
        assert "data" in gitignore_content

    def test_keeps_gitkeep_in_logs(self, gitignore_content):
        """保留 logs/.gitkeep"""
        # .gitignore 应有 !logs/.gitkeep 例外
        assert "!logs/.gitkeep" in gitignore_content

    def test_keeps_gitkeep_in_test_snapshots(self, gitignore_content):
        """保留 test_snapshots/.gitkeep"""
        assert "!test_snapshots/.gitkeep" in gitignore_content

    def test_keeps_gitkeep_in_data(self, gitignore_content):
        """保留 data/.gitkeep"""
        assert "!data/.gitkeep" in gitignore_content


class TestU9GitignoreCoversEnvArtifacts:
    """测试.gitignore覆盖环境产物"""

    @pytest.fixture
    def gitignore_content(self):
        return (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_ignores_venv(self, gitignore_content):
        """忽略虚拟环境"""
        assert ".venv" in gitignore_content or "venv" in gitignore_content

    def test_ignores_env_file(self, gitignore_content):
        """忽略 .env 文件"""
        assert ".env" in gitignore_content


class TestU9DirectoryPlaceholders:
    """测试目录占位文件"""

    def test_logs_gitkeep_exists(self):
        """logs/.gitkeep 存在"""
        assert (PROJECT_ROOT / "logs" / ".gitkeep").exists()

    def test_test_snapshots_gitkeep_exists(self):
        """test_snapshots/.gitkeep 存在"""
        assert (PROJECT_ROOT / "test_snapshots" / ".gitkeep").exists()

    def test_data_gitkeep_exists(self):
        """data/.gitkeep 存在"""
        assert (PROJECT_ROOT / "data" / ".gitkeep").exists()

    def test_data_directory_exists(self):
        """data 目录存在（用于PID文件）"""
        assert (PROJECT_ROOT / "data").is_dir()

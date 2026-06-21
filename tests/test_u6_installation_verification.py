"""
U6：安装验证和测试配置测试

验证安装验证脚本和测试配置：
1. verify_installation.py 脚本存在且可运行
2. conftest.py 存在且配置正确
3. pytest.ini 存在且配置正确
4. test_o10 不再硬编码路径
5. 测试可从任意目录运行

第一性原理：用户应能一键验证安装成功
"""

import pytest
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU6VerifyInstallation:
    """测试安装验证脚本"""

    def test_verify_script_exists(self):
        """verify_installation.py 存在"""
        assert (PROJECT_ROOT / "scripts" / "verify_installation.py").is_file()

    def test_verify_script_runs_successfully(self):
        """verify_installation.py 运行成功"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert result.returncode == 0, f"验证脚本失败: {result.stdout}\n{result.stderr}"
        assert "安装验证通过" in result.stdout

    def test_verify_script_checks_python(self):
        """验证脚本检查Python版本"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert "Python版本" in result.stdout

    def test_verify_script_checks_dependencies(self):
        """验证脚本检查依赖"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert "pyyaml" in result.stdout
        assert "numpy" in result.stdout
        assert "psutil" in result.stdout

    def test_verify_script_checks_imports(self):
        """验证脚本检查包导入"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert "src.main" in result.stdout
        assert "ConfigLoader" in result.stdout

    def test_verify_script_checks_config(self):
        """验证脚本检查配置文件"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert "config/dev.yaml" in result.stdout
        assert "config/prod.yaml" in result.stdout

    def test_verify_script_checks_console_script(self):
        """验证脚本检查console_scripts"""
        result = subprocess.run(
            ["python", "scripts/verify_installation.py"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT)
        )
        assert "self-driven-agent" in result.stdout


class TestU6ConftestPy:
    """测试conftest.py"""

    def test_conftest_exists(self):
        """conftest.py 存在"""
        assert (PROJECT_ROOT / "conftest.py").is_file()

    def test_conftest_sets_project_root(self):
        """conftest.py 设置项目根目录"""
        content = (PROJECT_ROOT / "conftest.py").read_text(encoding="utf-8")
        assert "PROJECT_ROOT" in content
        assert "sys.path" in content

    def test_conftest_changes_to_project_root(self):
        """conftest.py 切换到项目根目录"""
        content = (PROJECT_ROOT / "conftest.py").read_text(encoding="utf-8")
        assert "os.chdir" in content


class TestU6PytestIni:
    """测试pytest.ini"""

    def test_pytest_ini_exists(self):
        """pytest.ini 存在"""
        assert (PROJECT_ROOT / "pytest.ini").is_file()

    def test_pytest_ini_has_testpaths(self):
        """pytest.ini 配置测试路径"""
        content = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")
        assert "testpaths = tests" in content

    def test_pytest_ini_has_patterns(self):
        """pytest.ini 配置文件模式"""
        content = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")
        assert "python_files = test_*.py" in content
        assert "python_classes = Test*" in content
        assert "python_functions = test_*" in content


class TestU6NoHardcodedPaths:
    """测试无硬编码路径"""

    def test_test_o10_no_hardcoded_chdir(self):
        """test_o10 不再硬编码 os.chdir"""
        content = (PROJECT_ROOT / "tests" / "test_o10_orchestration_acceptance.py").read_text(encoding="utf-8")
        assert 'os.chdir("/workspace/self_driven_agent")' not in content

    def test_test_o10_uses_conftest(self):
        """test_o10 依赖conftest"""
        content = (PROJECT_ROOT / "tests" / "test_o10_orchestration_acceptance.py").read_text(encoding="utf-8")
        assert "conftest" in content or "conftest.py 已处理" in content


class TestU6TestRunFromAnyDir:
    """测试从任意目录运行"""

    def test_pytest_runs_from_tmp_dir(self):
        """从临时目录运行pytest成功"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["python", "-m", "pytest", str(PROJECT_ROOT / "tests" / "test_u2_cli_args.py"), "-v", "--tb=short"],
                capture_output=True, text=True, timeout=30,
                cwd=tmpdir
            )
            assert result.returncode == 0, f"从 {tmpdir} 运行失败: {result.stdout}\n{result.stderr}"

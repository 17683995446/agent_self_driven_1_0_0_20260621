"""
X10：dry-run增强与启动就绪测试

验证：
1. dry-run 校验配置值范围、依赖、目录可写（M9）
2. 启动日志有 "System ready" 标志（L4）
3. healthcheck.py 显示更多指标（L7）
4. --version 显示完整构建信息（L10）

第一性原理：dry-run 应充分验证启动条件；启动应有明确就绪标志；
健康检查应提供足够信息；版本应包含运行环境信息
"""

import pytest
import subprocess
import sys
import os
import json
import tempfile
from pathlib import Path

PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestX10DryRunEnhanced:
    """测试 dry-run 增强（M9）"""

    def test_dry_run_validates_config_values(self):
        """dry-run 校验配置值范围"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "配置值范围校验" in result.stdout

    def test_dry_run_checks_core_dependencies(self):
        """dry-run 检查核心依赖"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "核心依赖" in result.stdout
        assert "pyyaml" in result.stdout

    def test_dry_run_checks_optional_dependencies(self):
        """dry-run 检查可选依赖"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "可选依赖" in result.stdout

    def test_dry_run_checks_directory_writable(self):
        """dry-run 检查目录可写"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "目录可写" in result.stdout

    def test_dry_run_passes_with_valid_config(self):
        """dry-run 有效配置通过"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"dry-run 应通过: {result.stdout}\n{result.stderr}"
        assert "所有检查通过" in result.stdout

    def test_dry_run_fails_with_missing_config(self):
        """dry-run 配置文件不存在时失败"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--config", "/nonexistent/config.yaml", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0
        assert "配置文件不存在" in result.stdout

    def test_dry_run_shows_cpu_limit(self):
        """dry-run 显示 CPU 限制"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "CPU限制" in result.stdout

    def test_dry_run_shows_memory_limit(self):
        """dry-run 显示内存限制"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "内存限制" in result.stdout

    def test_dry_run_shows_exploration_ratio(self):
        """dry-run 显示探索率"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        assert "探索率" in result.stdout

    def test_dry_run_checks_all_four_directories(self):
        """dry-run 检查所有四个目录（logs/data/snapshots/memory）"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--env", "dev", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        for dir_name in ["logs", "data", "snapshots", "memory"]:
            assert f"目录可写: {dir_name}" in result.stdout, f"应检查 {dir_name} 目录可写"


class TestX10SystemReady:
    """测试启动就绪标志（L4）"""

    def test_log_start_has_system_ready(self):
        """_log_start 输出 'System ready' 标志"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text()
        assert '"System ready"' in content or "'System ready'" in content

    def test_log_start_has_system_ready_comment(self):
        """_log_start 有 X10 就绪标志注释"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text()
        assert "就绪标志" in content or "X10" in content

    def test_start_script_detects_system_ready(self):
        """启动脚本 wait_for_ready 探测 'System ready' 标志"""
        common_sh = (PROJECT_ROOT / "scripts" / "lib" / "common.sh").read_text()
        assert "System ready" in common_sh


class TestX10HealthcheckEnhanced:
    """测试 healthcheck.py 增强（L7）"""

    def test_healthcheck_has_runtime_status_check(self):
        """healthcheck.py 有运行时状态检查"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "check_runtime_status" in content
        assert "runtime_status.json" in content

    def test_healthcheck_shows_cycle_count(self):
        """healthcheck.py 显示周期数"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "cycle_count" in content
        assert "周期数" in content

    def test_healthcheck_shows_uptime(self):
        """healthcheck.py 显示运行时长"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "运行时长" in content or "uptime" in content

    def test_healthcheck_shows_recent_errors(self):
        """healthcheck.py 显示最近错误"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "recent_errors" in content
        assert "最近错误" in content

    def test_healthcheck_shows_last_cycle_time(self):
        """healthcheck.py 显示最近周期时间"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "last_cycle_time" in content
        assert "最近周期" in content

    def test_healthcheck_has_four_checks(self):
        """healthcheck.py 有四项检查（进程/日志新鲜度/日志错误/运行时状态）"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "进程检查" in content
        assert "日志新鲜度" in content
        assert "日志错误" in content
        assert "运行时状态" in content

    def test_healthcheck_runtime_status_function_exists(self):
        """check_runtime_status 函数存在"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "def check_runtime_status" in content

    def test_healthcheck_runtime_status_reads_json(self):
        """check_runtime_status 读取 JSON"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text()
        assert "json.load" in content

    def test_healthcheck_runnable(self):
        """healthcheck.py 可运行（退出码 0 或 1）"""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "healthcheck.py")],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode in (0, 1)


class TestX10VersionBuildInfo:
    """测试 --version 构建信息（L10）"""

    def test_version_shows_python_version(self):
        """--version 显示 Python 版本"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "Python" in result.stdout

    def test_version_shows_platform(self):
        """--version 显示平台信息"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "Platform" in result.stdout

    def test_version_shows_implementation(self):
        """--version 显示 Python 实现"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "Implementation" in result.stdout

    def test_version_shows_build_time(self):
        """--version 显示构建时间"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "Build time" in result.stdout

    def test_version_shows_version_number(self):
        """--version 显示版本号"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "1.0.0" in result.stdout

    def test_version_exit_code_zero(self):
        """--version 退出码为 0"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0

    def test_get_build_info_function_exists(self):
        """_get_build_info 函数存在"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text()
        assert "def _get_build_info" in content

    def test_get_build_info_uses_platform_module(self):
        """_get_build_info 使用 platform 模块"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text()
        assert "import platform" in content
        assert "platform.python_version" in content
        assert "platform.platform" in content


class TestX10DryRunConfigValidation:
    """测试 dry-run 配置值校验细节（M9）"""

    def test_dry_run_calls_validate_config(self):
        """dry-run 调用 _validate_config"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text()
        assert "_validate_config" in content

    def test_dry_run_validates_cpu_range(self):
        """dry-run 校验 CPU 范围（通过 _validate_config）"""
        # 用一个 CPU 超范围的配置测试
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
environment: test
guardrail:
  max_cpu_usage: 5.0
  max_memory_usage: 0.2
decision:
  base_exploration_ratio: 0.3
""")
            bad_config = f.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.main", "--config", bad_config, "--dry-run"],
                capture_output=True, text=True, timeout=15,
                cwd=str(PROJECT_ROOT),
            )
            assert result.returncode != 0, "CPU 超范围应导致 dry-run 失败"
            assert "配置值范围校验失败" in result.stdout or "parameter_range_error" in result.stdout.lower()
        finally:
            os.unlink(bad_config)

    def test_dry_run_validates_memory_range(self):
        """dry-run 校验内存范围"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
environment: test
guardrail:
  max_cpu_usage: 0.2
  max_memory_usage: 5.0
decision:
  base_exploration_ratio: 0.3
""")
            bad_config = f.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.main", "--config", bad_config, "--dry-run"],
                capture_output=True, text=True, timeout=15,
                cwd=str(PROJECT_ROOT),
            )
            assert result.returncode != 0
        finally:
            os.unlink(bad_config)

    def test_dry_run_validates_exploration_range(self):
        """dry-run 校验探索率范围"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
environment: test
guardrail:
  max_cpu_usage: 0.2
  max_memory_usage: 0.2
decision:
  base_exploration_ratio: 5.0
""")
            bad_config = f.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.main", "--config", bad_config, "--dry-run"],
                capture_output=True, text=True, timeout=15,
                cwd=str(PROJECT_ROOT),
            )
            assert result.returncode != 0
        finally:
            os.unlink(bad_config)

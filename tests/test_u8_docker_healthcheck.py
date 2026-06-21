"""
U8：Docker健康检查修复测试

验证Docker健康检查修复：
1. healthcheck.py 脚本存在且可运行
2. healthcheck.py 不实例化完整AgentSystem
3. Dockerfile 使用轻量健康检查
4. docker-compose.yml 使用轻量健康检查

第一性原理：健康检查应轻量、无副作用
"""

import pytest
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU8HealthcheckScript:
    """测试健康检查脚本"""

    def test_healthcheck_script_exists(self):
        """healthcheck.py 存在"""
        assert (PROJECT_ROOT / "scripts" / "healthcheck.py").is_file()

    def test_healthcheck_script_runs(self):
        """healthcheck.py 可运行"""
        result = subprocess.run(
            ["python", "scripts/healthcheck.py"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT)
        )
        # 可能返回0或1，但不应崩溃
        assert result.returncode in [0, 1]

    def test_healthcheck_not_instantiate_agent_system(self):
        """healthcheck.py 不实例化AgentSystem"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        # 不应实例化AgentSystem
        assert "AgentSystem()" not in content
        # 不应导入AgentSystem
        assert "from src.main import" not in content
        assert "import AgentSystem" not in content

    def test_healthcheck_checks_pid_file(self):
        """healthcheck.py 检查PID文件"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        assert "pid" in content.lower()

    def test_healthcheck_checks_log(self):
        """healthcheck.py 检查日志"""
        content = (PROJECT_ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        assert "log" in content.lower()

    def test_healthcheck_outputs_status(self):
        """healthcheck.py 输出健康状态"""
        result = subprocess.run(
            ["python", "scripts/healthcheck.py"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT)
        )
        assert "healthy" in result.stdout or "unhealthy" in result.stdout


class TestU8DockerfileFixed:
    """测试Dockerfile修复"""

    def test_dockerfile_exists(self):
        """Dockerfile 存在"""
        assert (PROJECT_ROOT / "Dockerfile").is_file()

    def test_dockerfile_uses_healthcheck_script(self):
        """Dockerfile 使用healthcheck.py脚本"""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "healthcheck.py" in content

    def test_dockerfile_not_instantiate_agent_system(self):
        """Dockerfile 不再实例化AgentSystem"""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "AgentSystem()" not in content
        assert "is_healthy()" not in content

    def test_dockerfile_copies_healthcheck_script(self):
        """Dockerfile 复制healthcheck.py"""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "COPY scripts/healthcheck.py" in content

    def test_dockerfile_start_period_10s(self):
        """Dockerfile start-period为10秒"""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "start-period=10s" in content


class TestU8DockerComposeFixed:
    """测试docker-compose.yml修复"""

    def test_docker_compose_exists(self):
        """docker-compose.yml 存在"""
        assert (PROJECT_ROOT / "docker-compose.yml").is_file()

    def test_docker_compose_uses_healthcheck_script(self):
        """docker-compose.yml 使用healthcheck.py脚本"""
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "healthcheck.py" in content

    def test_docker_compose_not_instantiate_agent_system(self):
        """docker-compose.yml 不再实例化AgentSystem"""
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "AgentSystem()" not in content
        assert "is_healthy()" not in content

    def test_docker_compose_start_period_10s(self):
        """docker-compose.yml start_period为10秒"""
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "start_period: 10s" in content


class TestU8HealthcheckLogic:
    """测试健康检查逻辑"""

    def test_check_pid_file_nonexistent(self):
        """PID文件不存在时返回不健康"""
        from scripts.healthcheck import check_pid_file
        ok, msg = check_pid_file("/nonexistent/pid")
        assert ok is False

    def test_check_log_freshness_nonexistent(self):
        """日志文件不存在时返回不健康"""
        from scripts.healthcheck import check_log_freshness
        ok, msg = check_log_freshness("/nonexistent/log")
        assert ok is False

    def test_check_log_errors_nonexistent(self):
        """日志文件不存在时返回不健康"""
        from scripts.healthcheck import check_log_errors
        ok, msg = check_log_errors("/nonexistent/log")
        assert ok is False

    def test_check_log_freshness_recent(self, tmp_path):
        """最近更新的日志返回健康"""
        log_file = tmp_path / "agent.log"
        log_file.write_text("recent log")
        from scripts.healthcheck import check_log_freshness
        ok, msg = check_log_freshness(str(log_file))
        assert ok is True

    def test_check_log_errors_few_errors(self, tmp_path):
        """少量错误的日志返回健康"""
        log_file = tmp_path / "agent.log"
        log_file.write_text("INFO start\nINFO running\n")
        from scripts.healthcheck import check_log_errors
        ok, msg = check_log_errors(str(log_file))
        assert ok is True

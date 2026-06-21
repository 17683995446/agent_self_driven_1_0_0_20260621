"""
X8：脚本体验统一测试

验证脚本体验统一：
1. 公共脚本库 lib/common.sh 存在（M15）
2. start.sh 支持 --env 参数透传（M4, M5）
3. start.sh 使用就绪探测而非固定 sleep（M4）
4. stop.sh 校验 PID 对应进程（M6）
5. monitor_5h.sh 参数化时长（L2）
6. verify_installation.py 使用相对路径（L8）

第一性原理：脚本应统一公共逻辑，参数化可配置项，校验关键操作
"""

import pytest
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspace/self_driven_agent")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class TestX8CommonLib:
    """测试公共脚本库"""

    def test_common_sh_exists(self):
        """lib/common.sh 存在"""
        assert (SCRIPTS_DIR / "lib" / "common.sh").is_file()

    def test_common_sh_has_color_definitions(self):
        """common.sh 有颜色定义"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "RED=" in content
        assert "GREEN=" in content
        assert "YELLOW=" in content

    def test_common_sh_has_log_functions(self):
        """common.sh 有日志函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "log_info()" in content
        assert "log_warn()" in content
        assert "log_error()" in content

    def test_common_sh_has_path_definitions(self):
        """common.sh 有路径定义"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "PROJECT_DIR=" in content
        assert "PID_FILE=" in content
        assert "LOG_DIR=" in content

    def test_common_sh_has_parse_env(self):
        """common.sh 有 parse_env 函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "parse_env()" in content
        assert "--env" in content

    def test_common_sh_has_run_agent(self):
        """common.sh 有 run_agent 函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "run_agent()" in content

    def test_common_sh_has_wait_for_ready(self):
        """common.sh 有 wait_for_ready 函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "wait_for_ready()" in content

    def test_common_sh_has_verify_pid_is_agent(self):
        """common.sh 有 verify_pid_is_agent 函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "verify_pid_is_agent()" in content

    def test_common_sh_has_setup_directories(self):
        """common.sh 有 setup_directories 函数"""
        content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "setup_directories()" in content


class TestX8StartScript:
    """测试 start.sh 改进"""

    def test_start_sh_sources_common(self):
        """start.sh 加载 common.sh"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert "source" in content
        assert "common.sh" in content

    def test_start_sh_supports_env_param(self):
        """start.sh 支持 --env 参数（M5）"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert "parse_env" in content
        assert "--env" in content

    def test_start_sh_no_hardcoded_prod(self):
        """start.sh 不再硬编码 prod 配置（M5）"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        # 不应有 CONFIG_FILE="$PROJECT_DIR/config/prod.yaml" 硬编码
        assert 'config/prod.yaml"' not in content or "parse_env" in content

    def test_start_sh_uses_ready_detection(self):
        """start.sh 使用就绪探测而非固定 sleep（M4）"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert "wait_for_ready" in content
        # 不应有固定的 sleep 2 命令（就绪探测替代）
        # 仅检查非注释行，避免注释中的"sleep 2"误判
        code_lines = [l for l in content.split("\n") if not l.strip().startswith("#")]
        code_text = "\n".join(code_lines)
        assert "sleep 2" not in code_text

    def test_start_sh_passes_args_to_agent(self):
        """start.sh 透传参数到 agent（M4）"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert '"$@"' in content

    def test_start_sh_verifies_pid_is_agent(self):
        """start.sh 校验 PID 对应进程（M6）"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert "verify_pid_is_agent" in content

    def test_start_sh_has_usage_in_comments(self):
        """start.sh 注释中有用法说明"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        assert "--env dev" in content or "--env" in content


class TestX8StopScript:
    """测试 stop.sh 改进"""

    def test_stop_sh_sources_common(self):
        """stop.sh 加载 common.sh"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        assert "source" in content
        assert "common.sh" in content

    def test_stop_sh_verifies_pid(self):
        """stop.sh 校验 PID 对应进程（M6）"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        assert "verify_pid" in content or "verify_pid_is_agent" in content

    def test_stop_sh_refuses_non_agent_pid(self):
        """stop.sh 拒绝非 agent 进程"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        assert "不是 Agent" in content or "拒绝" in content

    def test_stop_sh_no_duplicate_color_definitions(self):
        """stop.sh 不重复定义颜色（M15）"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        # 颜色定义应在 common.sh 中，stop.sh 不应重复定义
        # 允许在 source 之前有少量定义，但不应有完整的颜色块
        lines = content.split("\n")
        color_def_lines = [l for l in lines if l.startswith(("RED=", "GREEN=", "YELLOW="))]
        assert len(color_def_lines) == 0, "stop.sh 不应重复定义颜色（已在 common.sh 中）"

    def test_stop_sh_no_duplicate_log_functions(self):
        """stop.sh 不重复定义日志函数（M15）"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        # 日志函数应在 common.sh 中
        assert "log_info()" not in content
        assert "log_warn()" not in content
        assert "log_error()" not in content


class TestX8MonitorScript:
    """测试 monitor_5h.sh 改进"""

    def test_monitor_sh_sources_common(self):
        """monitor_5h.sh 加载 common.sh"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        assert "source" in content
        assert "common.sh" in content

    def test_monitor_sh_accepts_duration_param(self):
        """monitor_5h.sh 接受时长参数（L2）"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        assert "DURATION" in content
        assert "${2:-" in content or "$2" in content

    def test_monitor_sh_no_hardcoded_18000(self):
        """monitor_5h.sh 不再硬编码 18000（L2）"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        # 18000 应作为默认值而非硬编码在逻辑中
        # 允许 DURATION=${2:-18000} 但不应有 if ELAPSED -ge 18000
        assert "ELAPSED -ge 18000" not in content
        # 接受引号或不带引号的形式（bash 最佳实践是引号包裹变量）
        assert ('ELAPSED" -ge "$DURATION' in content
                or 'ELAPSED -ge "$DURATION"' in content
                or 'ELAPSED -ge $DURATION' in content)

    def test_monitor_sh_no_hardcoded_paths(self):
        """monitor_5h.sh 不再硬编码路径（L2）"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        assert "/workspace/self_driven_agent" not in content

    def test_monitor_sh_has_usage_in_comments(self):
        """monitor_5h.sh 注释中有用法说明"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        assert "用法" in content or "Usage" in content or "duration_seconds" in content


class TestX8VerifyInstallation:
    """测试 verify_installation.py 改进"""

    def test_verify_installation_no_hardcoded_path(self):
        """verify_installation.py 不硬编码绝对路径（L8）"""
        content = (SCRIPTS_DIR / "verify_installation.py").read_text()
        assert "/workspace/self_driven_agent" not in content

    def test_verify_installation_uses_relative_path(self):
        """verify_installation.py 使用相对路径解析项目目录（L8）"""
        content = (SCRIPTS_DIR / "verify_installation.py").read_text()
        assert "os.path.dirname" in content
        assert "os.path.abspath(__file__)" in content

    def test_verify_installation_runs_successfully(self):
        """verify_installation.py 能成功运行"""
        import subprocess
        result = subprocess.run(
            ["python", str(SCRIPTS_DIR / "verify_installation.py")],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"验证脚本失败: {result.stdout}\n{result.stderr}"


class TestX8NoDuplicateColorDefinitions:
    """测试所有脚本不重复定义颜色（M15）"""

    def test_start_sh_no_duplicate_colors(self):
        """start.sh 不重复定义颜色"""
        content = (SCRIPTS_DIR / "start.sh").read_text()
        lines = content.split("\n")
        color_def_lines = [l for l in lines if l.startswith(("RED=", "GREEN=", "YELLOW="))]
        assert len(color_def_lines) == 0

    def test_stop_sh_no_duplicate_colors(self):
        """stop.sh 不重复定义颜色"""
        content = (SCRIPTS_DIR / "stop.sh").read_text()
        lines = content.split("\n")
        color_def_lines = [l for l in lines if l.startswith(("RED=", "GREEN=", "YELLOW="))]
        assert len(color_def_lines) == 0

    def test_monitor_sh_no_duplicate_colors(self):
        """monitor_5h.sh 不重复定义颜色"""
        content = (SCRIPTS_DIR / "monitor_5h.sh").read_text()
        lines = content.split("\n")
        color_def_lines = [l for l in lines if l.startswith(("RED=", "GREEN=", "YELLOW="))]
        assert len(color_def_lines) == 0

    def test_colors_defined_only_in_common(self):
        """颜色定义只在 common.sh 中"""
        common_content = (SCRIPTS_DIR / "lib" / "common.sh").read_text()
        assert "RED=" in common_content
        assert "GREEN=" in common_content
        assert "YELLOW=" in common_content


class TestX8ScriptsExecutable:
    """测试脚本可执行性"""

    def test_start_sh_exists(self):
        """start.sh 存在"""
        assert (SCRIPTS_DIR / "start.sh").is_file()

    def test_stop_sh_exists(self):
        """stop.sh 存在"""
        assert (SCRIPTS_DIR / "stop.sh").is_file()

    def test_monitor_sh_exists(self):
        """monitor_5h.sh 存在"""
        assert (SCRIPTS_DIR / "monitor_5h.sh").is_file()

    def test_verify_installation_exists(self):
        """verify_installation.py 存在"""
        assert (SCRIPTS_DIR / "verify_installation.py").is_file()

"""
X5：运行时可观测性测试

验证运行时状态可观测性：
1. 主循环定期写入 runtime_status.json（H6）
2. --status 命令读取并显示状态
3. 周期反馈日志可配置密度（M2）

第一性原理：用户应能随时查询系统运行状态，无需侵入进程
"""

import pytest
import os
import sys
import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.platform.support.models.base.state import EnvironmentState


def _make_system():
    """创建最小化 AgentSystem 实例"""
    from src.main import AgentSystem
    system = object.__new__(AgentSystem)
    system.running = True
    system.cycle_count = 10
    system.start_time = time.time() - 100
    system.total_tasks_executed = 20
    system.total_tasks_succeeded = 18
    system.config_loader = MagicMock()
    system.config_loader.config = {}
    system.config_loader.config_path = "./config/dev.yaml"
    return system


def _make_state(cpu=0.3, memory=0.4):
    """创建 EnvironmentState"""
    from dataclasses import replace
    base = EnvironmentState()
    return replace(base, system=replace(base.system, cpu_overall=cpu, memory_usage=memory))


class TestX5BuildRuntimeStatus:
    """测试构建运行时状态"""

    def test_build_status_contains_cycle(self):
        """状态包含周期数"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert status["cycle"] == 10

    def test_build_status_contains_running(self):
        """状态包含运行标志"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert status["running"] is True

    def test_build_status_contains_uptime(self):
        """状态包含运行时长"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert status["uptime"] >= 99

    def test_build_status_contains_task_counts(self):
        """状态包含任务计数"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert status["tasks_executed"] == 20
        assert status["tasks_succeeded"] == 18

    def test_build_status_contains_success_rate(self):
        """状态包含成功率"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert status["success_rate"] == 90.0

    def test_build_status_contains_cpu_usage(self):
        """状态包含CPU使用率（百分比）"""
        system = _make_system()
        status = system._build_runtime_status(_make_state(cpu=0.5))
        assert status["cpu_usage"] == 50.0

    def test_build_status_contains_memory_usage(self):
        """状态包含内存使用率（百分比）"""
        system = _make_system()
        status = system._build_runtime_status(_make_state(memory=0.7))
        assert status["memory_usage"] == 70.0

    def test_build_status_contains_config_path(self):
        """状态包含配置文件路径"""
        system = _make_system()
        status = system._build_runtime_status(_make_state())
        assert "dev.yaml" in status["config_path"]

    def test_build_status_contains_last_update(self):
        """状态包含最后更新时间"""
        system = _make_system()
        before = time.time()
        status = system._build_runtime_status(_make_state())
        after = time.time()
        assert before <= status["last_update"] <= after


class TestX5SaveRuntimeStatus:
    """测试保存运行时状态到文件"""

    def test_save_status_creates_file(self, tmp_path):
        """保存状态创建文件"""
        system = _make_system()
        system.config_loader.get.return_value = str(tmp_path)
        status = {"cycle": 1, "running": True}
        system._save_runtime_status(status)
        assert (tmp_path / "runtime_status.json").exists()

    def test_save_status_writes_json(self, tmp_path):
        """保存状态写入JSON"""
        system = _make_system()
        system.config_loader.get.return_value = str(tmp_path)
        status = {"cycle": 42, "running": True}
        system._save_runtime_status(status)
        with open(tmp_path / "runtime_status.json") as f:
            data = json.load(f)
        assert data["cycle"] == 42
        assert data["running"] is True

    def test_save_status_creates_directory(self, tmp_path):
        """保存状态创建目录"""
        system = _make_system()
        nested_dir = str(tmp_path / "nested" / "status")
        system.config_loader.get.return_value = nested_dir
        status = {"cycle": 1}
        system._save_runtime_status(status)
        assert os.path.exists(os.path.join(nested_dir, "runtime_status.json"))


class TestX5WriteRuntimeStatus:
    """测试主循环写入运行时状态"""

    def _make_mock_get(self, tmp_path, interval=1):
        """创建区分 key 的 mock get"""
        def mock_get(key, default=None):
            if key == "status.write_interval":
                return interval
            if key == "status.dir":
                return str(tmp_path)
            return default
        return mock_get

    def test_write_status_at_interval(self, tmp_path):
        """到达间隔时写入状态"""
        system = _make_system()
        system.config_loader.get = self._make_mock_get(tmp_path, interval=1)
        system._write_runtime_status(_make_state())
        assert (tmp_path / "runtime_status.json").exists()

    def test_write_status_respects_interval(self, tmp_path):
        """未到间隔时不写入"""
        system = _make_system()
        system.cycle_count = 7
        system.config_loader.get = self._make_mock_get(tmp_path, interval=10)
        system._write_runtime_status(_make_state())
        assert not (tmp_path / "runtime_status.json").exists()

    def test_write_status_interval_zero_disables(self, tmp_path):
        """间隔为0时禁用"""
        system = _make_system()
        system.config_loader.get = self._make_mock_get(tmp_path, interval=0)
        system._write_runtime_status(_make_state())
        assert not (tmp_path / "runtime_status.json").exists()

    def test_write_status_failure_does_not_crash(self):
        """状态写入失败不影响主循环"""
        system = _make_system()
        system.config_loader.get = MagicMock(side_effect=RuntimeError("boom"))
        # 不应抛出异常
        system._write_runtime_status(_make_state())


class TestX5CycleFeedback:
    """测试周期反馈日志"""

    def test_feedback_logs_at_interval(self, caplog):
        """到达间隔时输出周期反馈"""
        system = _make_system()
        system.cycle_count = 5
        system.config_loader.get.return_value = 5
        with caplog.at_level(logging.INFO):
            system._log_cycle_feedback(_make_state())
        assert "周期 5" in caplog.text
        assert "CPU" in caplog.text

    def test_feedback_not_at_interval(self, caplog):
        """未到间隔时不输出"""
        system = _make_system()
        system.cycle_count = 3
        system.config_loader.get.return_value = 5
        with caplog.at_level(logging.INFO):
            system._log_cycle_feedback(_make_state())
        assert "周期 3" not in caplog.text

    def test_feedback_contains_cpu_and_memory(self, caplog):
        """反馈包含CPU和内存信息"""
        system = _make_system()
        system.cycle_count = 10
        system.config_loader.get.return_value = 10
        with caplog.at_level(logging.INFO):
            system._log_cycle_feedback(_make_state(cpu=0.5, memory=0.6))
        assert "CPU" in caplog.text
        assert "内存" in caplog.text

    def test_feedback_contains_success_rate(self, caplog):
        """反馈包含成功率"""
        system = _make_system()
        system.cycle_count = 5
        system.config_loader.get.return_value = 5
        with caplog.at_level(logging.INFO):
            system._log_cycle_feedback(_make_state())
        assert "成功率" in caplog.text
        assert "90" in caplog.text


class TestX5StatusCLI:
    """测试 --status CLI命令"""

    def test_parse_args_has_status_flag(self):
        """parse_args 支持 --status"""
        from src.main import parse_args
        args = parse_args(["--status"])
        assert args.status is True

    def test_parse_args_status_default_false(self):
        """--status 默认为 False"""
        from src.main import parse_args
        args = parse_args([])
        assert args.status is False

    def test_main_status_calls_run_status_check(self):
        """main() 在 --status 时调用 _run_status_check"""
        from src.main import main
        with patch("src.main._run_status_check") as mock_check:
            main(["--status"])
        mock_check.assert_called_once()

    def test_main_status_does_not_start_agent(self):
        """--status 不启动Agent"""
        from src.main import main
        with patch("src.main._run_status_check"):
            with patch("src.main.AgentSystem") as mock_agent:
                main(["--status"])
        mock_agent.assert_not_called()


class TestX5RunStatusCheck:
    """测试 _run_status_check 函数"""

    def test_status_file_not_found_exits(self, tmp_path, capsys):
        """状态文件不存在时退出"""
        from src.main import _run_status_check
        nonexistent = str(tmp_path / "nonexistent.json")
        with patch.dict(os.environ, {"AGENT_STATUS_PATH": nonexistent}):
            with pytest.raises(SystemExit):
                _run_status_check()
        captured = capsys.readouterr()
        assert "不存在" in captured.out

    def test_status_file_not_found_has_hint(self, tmp_path, capsys):
        """状态文件不存在时提示环境变量"""
        from src.main import _run_status_check
        nonexistent = str(tmp_path / "nonexistent.json")
        with patch.dict(os.environ, {"AGENT_STATUS_PATH": nonexistent}):
            with pytest.raises(SystemExit):
                _run_status_check()
        captured = capsys.readouterr()
        assert "AGENT_STATUS_PATH" in captured.out

    def test_status_reads_and_prints(self, tmp_path, capsys):
        """成功读取并打印状态"""
        from src.main import _run_status_check
        status_file = tmp_path / "runtime_status.json"
        status = {
            "cycle": 42,
            "running": True,
            "uptime": 100.5,
            "cpu_usage": 35.2,
            "memory_usage": 45.0,
            "tasks_executed": 10,
            "tasks_succeeded": 9,
            "success_rate": 90.0,
            "config_path": "./config/dev.yaml",
            "last_update": time.time(),
        }
        status_file.write_text(json.dumps(status))
        with patch.dict(os.environ, {"AGENT_STATUS_PATH": str(status_file)}):
            _run_status_check()
        captured = capsys.readouterr()
        assert "Agent 运行状态" in captured.out
        assert "42" in captured.out
        assert "35.2" in captured.out

    def test_status_invalid_json_exits(self, tmp_path, capsys):
        """无效JSON退出"""
        from src.main import _run_status_check
        status_file = tmp_path / "runtime_status.json"
        status_file.write_text("{invalid json")
        with patch.dict(os.environ, {"AGENT_STATUS_PATH": str(status_file)}):
            with pytest.raises(SystemExit):
                _run_status_check()
        captured = capsys.readouterr()
        assert "读取失败" in captured.out


class TestX5PrintStatus:
    """测试 _print_status 格式化输出"""

    def test_print_status_shows_running(self, capsys):
        """打印运行状态"""
        from src.main import _print_status
        status = {"running": True, "cycle": 5}
        _print_status(status, "data/runtime_status.json")
        captured = capsys.readouterr()
        assert "是" in captured.out
        assert "5" in captured.out

    def test_print_status_shows_not_running(self, capsys):
        """打印未运行状态"""
        from src.main import _print_status
        status = {"running": False, "cycle": 0}
        _print_status(status, "data/runtime_status.json")
        captured = capsys.readouterr()
        assert "否" in captured.out

    def test_print_status_shows_all_metrics(self, capsys):
        """打印所有指标"""
        from src.main import _print_status
        status = {
            "running": True,
            "cycle": 100,
            "uptime": 3600,
            "cpu_usage": 50.0,
            "memory_usage": 60.0,
            "tasks_executed": 200,
            "tasks_succeeded": 180,
            "success_rate": 90.0,
            "config_path": "./config/prod.yaml",
        }
        _print_status(status, "data/runtime_status.json")
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "3600" in captured.out
        assert "50.0" in captured.out
        assert "60.0" in captured.out
        assert "200" in captured.out
        assert "90.0" in captured.out
        assert "prod.yaml" in captured.out

    def test_print_status_shows_last_update(self, capsys):
        """打印最后更新时间"""
        from src.main import _print_status
        status = {"running": True, "last_update": time.time()}
        _print_status(status, "data/runtime_status.json")
        captured = capsys.readouterr()
        assert "最后更新" in captured.out

    def test_print_status_shows_status_path(self, capsys):
        """打印状态文件路径"""
        from src.main import _print_status
        _print_status({"running": True}, "/custom/path.json")
        captured = capsys.readouterr()
        assert "/custom/path.json" in captured.out


class TestX5RunCycleEndIntegration:
    """测试 _run_cycle_end 集成状态写入"""

    def test_run_cycle_end_calls_write_status(self):
        """_run_cycle_end 调用 _write_runtime_status"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._publish_cycle_end = MagicMock()
        system._maybe_auto_snapshot = MagicMock()
        system._maybe_periodic_report = MagicMock()
        system._write_runtime_status = MagicMock()
        system._log_cycle_feedback = MagicMock()
        system._sleep_cycle = MagicMock()
        system._run_cycle_end(_make_state(), time.time())
        system._write_runtime_status.assert_called_once()

    def test_run_cycle_end_calls_log_feedback(self):
        """_run_cycle_end 调用 _log_cycle_feedback"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._publish_cycle_end = MagicMock()
        system._maybe_auto_snapshot = MagicMock()
        system._maybe_periodic_report = MagicMock()
        system._write_runtime_status = MagicMock()
        system._log_cycle_feedback = MagicMock()
        system._sleep_cycle = MagicMock()
        system._run_cycle_end(_make_state(), time.time())
        system._log_cycle_feedback.assert_called_once()


class TestX5SourceCodeStructure:
    """测试源码结构"""

    def test_main_has_status_flag(self):
        """main.py 有 --status 参数"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "--status" in content

    def test_main_has_run_status_check(self):
        """main.py 有 _run_status_check 函数"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_run_status_check" in content
        assert "_print_status" in content

    def test_main_has_write_runtime_status(self):
        """main.py 有 _write_runtime_status 方法"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_write_runtime_status" in content
        assert "_build_runtime_status" in content
        assert "_save_runtime_status" in content

    def test_main_has_cycle_feedback(self):
        """main.py 有 _log_cycle_feedback 方法"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_log_cycle_feedback" in content
        assert "cycle_feedback_interval" in content

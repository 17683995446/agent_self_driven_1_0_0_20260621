"""
X4：优雅停机体验测试

验证信号处理和优雅停机：
1. 信号处理器设置标志位而非直接 sys.exit（H5）
2. 主循环检测标志位后退出
3. 停机时打印进度反馈
4. 运行期间定期落盘报告
5. 第二次信号强制退出

第一性原理：停机过程必须可感知、可追踪、数据不丢失
"""

import pytest
import os
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import signal as signal_module

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.main import (
    signal_handler,
    is_shutdown_requested,
    reset_shutdown_flag,
    _shutdown_requested,
)


class TestX4SignalHandler:
    """测试信号处理器（X4：标志位模式）"""

    def setup_method(self):
        reset_shutdown_flag()

    def teardown_method(self):
        reset_shutdown_flag()

    def test_signal_handler_sets_flag(self):
        """第一次信号设置停机标志位"""
        signal_handler(signal_module.SIGINT, None)
        assert is_shutdown_requested() is True

    def test_signal_handler_does_not_exit_on_first_signal(self):
        """第一次信号不直接退出"""
        # 如果 sys.exit 被调用会抛出 SystemExit
        signal_handler(signal_module.SIGTERM, None)
        # 到这里说明没有退出
        assert is_shutdown_requested() is True

    def test_signal_handler_second_signal_exits(self):
        """第二次信号强制退出"""
        signal_handler(signal_module.SIGINT, None)  # 第一次
        assert is_shutdown_requested() is True
        with pytest.raises(SystemExit):
            signal_handler(signal_module.SIGINT, None)  # 第二次

    def test_signal_handler_logs_shutdown_message(self, caplog):
        """信号处理器记录停机日志"""
        with caplog.at_level(logging.INFO):
            signal_handler(signal_module.SIGINT, None)
        assert "优雅停机" in caplog.text or "停机" in caplog.text

    def test_signal_handler_logs_signal_number(self, caplog):
        """日志包含信号编号"""
        with caplog.at_level(logging.INFO):
            signal_handler(signal_module.SIGTERM, None)
        assert str(signal_module.SIGTERM) in caplog.text

    def test_signal_handler_not_calling_sys_exit_directly(self):
        """signal_handler 函数体不包含直接的 sys.exit(0)（第一次信号时）"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def signal_handler\(signum.*?frame.*?\).*?(?=\n\n\n|\n# X4)', content, re.DOTALL)
        assert match, "signal_handler not found"
        body = match.group()
        # 第一次信号路径不应有 sys.exit(0)
        # 但第二次信号路径应有 sys.exit(1)
        assert "sys.exit(1)" in body, "第二次信号应 sys.exit(1)"
        assert "_shutdown_requested = True" in body, "应设置停机标志"


class TestX4ShutdownFlag:
    """测试停机标志位"""

    def setup_method(self):
        reset_shutdown_flag()

    def teardown_method(self):
        reset_shutdown_flag()

    def test_initial_flag_is_false(self):
        """初始标志为 False"""
        reset_shutdown_flag()
        assert is_shutdown_requested() is False

    def test_flag_can_be_set(self):
        """标志可被设置"""
        signal_handler(signal_module.SIGINT, None)
        assert is_shutdown_requested() is True

    def test_flag_can_be_reset(self):
        """标志可被重置"""
        signal_handler(signal_module.SIGINT, None)
        assert is_shutdown_requested() is True
        reset_shutdown_flag()
        assert is_shutdown_requested() is False


class TestX4MainLoopShutdownCheck:
    """测试主循环检测停机标志"""

    def test_main_loop_exits_on_shutdown_flag(self):
        """主循环检测到停机标志后退出"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.running = True
        system.cycle_count = 0
        call_count = [0]
        def mock_cycle():
            call_count[0] += 1
            system.cycle_count += 1
            if system.cycle_count >= 3:
                signal_handler(signal_module.SIGINT, None)
        system._run_single_cycle = mock_cycle
        system._main_loop()
        assert call_count[0] == 3
        assert is_shutdown_requested() is True
        reset_shutdown_flag()

    def test_main_loop_continues_without_flag(self):
        """无停机标志时主循环继续"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.running = True
        call_count = [0]
        def mock_cycle():
            call_count[0] += 1
            if call_count[0] >= 5:
                system.running = False
        system._run_single_cycle = mock_cycle
        system._main_loop()
        assert call_count[0] == 5
        reset_shutdown_flag()

    def test_main_loop_logs_shutdown_message(self, caplog):
        """主循环退出时记录日志"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.running = True
        system.cycle_count = 0
        def mock_cycle():
            system.cycle_count += 1
            if system.cycle_count >= 2:
                signal_handler(signal_module.SIGINT, None)
        system._run_single_cycle = mock_cycle
        with caplog.at_level(logging.INFO):
            system._main_loop()
        assert "停机标志" in caplog.text or "退出主循环" in caplog.text
        reset_shutdown_flag()


class TestX4GracefulStopProgress:
    """测试优雅停机进度反馈"""

    def _make_system(self):
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.running = True
        system.cycle_count = 10
        system.start_time = 0.0
        system.total_tasks_executed = 5
        system.total_tasks_succeeded = 4
        system.perception = MagicMock()
        system.event_bus = MagicMock()
        system.config_loader = MagicMock()
        system.config_loader.config = {}
        system.snapshot = MagicMock()
        system.plugin_manager = MagicMock()
        system.run_reporter = MagicMock()
        system._feedback_learner = MagicMock()
        system._shutdown_plugins = MagicMock()
        system._stop_hot_reload = MagicMock()
        system._generate_run_report = MagicMock()
        return system

    def test_stop_logs_graceful_shutdown_message(self, caplog):
        """stop() 记录优雅停机消息"""
        system = self._make_system()
        with caplog.at_level(logging.INFO):
            system.stop()
        assert "优雅停机" in caplog.text

    def test_stop_logs_each_step(self, caplog):
        """stop() 记录每个停机步骤"""
        system = self._make_system()
        with caplog.at_level(logging.INFO):
            system.stop()
        text = caplog.text
        assert "停止感知模块" in text
        assert "关闭插件" in text
        assert "停止配置热加载" in text
        assert "保存停机快照" in text
        assert "生成运行报告" in text
        assert "停止事件总线" in text

    def test_stop_calls_all_shutdown_actions(self):
        """stop() 调用所有停机动作"""
        system = self._make_system()
        system.stop()
        system.perception.stop.assert_called_once()
        system._shutdown_plugins.assert_called_once()
        system._stop_hot_reload.assert_called_once()
        system._generate_run_report.assert_called_once()
        system.event_bus.stop.assert_called_once()

    def test_stop_saves_shutdown_snapshot(self):
        """stop() 保存停机快照"""
        system = self._make_system()
        system.stop()
        system.snapshot.create_snapshot.assert_called_once()
        call_kwargs = system.snapshot.create_snapshot.call_args
        metadata = call_kwargs.kwargs.get("metadata") or call_kwargs[1].get("metadata")
        assert metadata["trigger"] == "shutdown"

    def test_stop_sets_running_false(self):
        """stop() 设置 running 为 False"""
        system = self._make_system()
        system.stop()
        assert system.running is False

    def test_stop_continues_on_step_failure(self, caplog):
        """某步失败不影响后续步骤"""
        system = self._make_system()
        system.perception.stop.side_effect = RuntimeError("boom")
        with caplog.at_level(logging.WARNING):
            system.stop()
        # 即使感知停止失败，后续步骤仍执行
        system._generate_run_report.assert_called_once()
        system.event_bus.stop.assert_called_once()
        assert "失败" in caplog.text

    def test_stop_logs_completion(self, caplog):
        """stop() 记录停机完成"""
        system = self._make_system()
        with caplog.at_level(logging.INFO):
            system.stop()
        assert "优雅停机完成" in caplog.text

    def test_shutdown_step_catches_exception(self, caplog):
        """_shutdown_step 捕获异常并记录"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        with caplog.at_level(logging.WARNING):
            system._shutdown_step("测试步骤", MagicMock(side_effect=ValueError("err")))
        assert "测试步骤" in caplog.text
        assert "失败" in caplog.text

    def test_shutdown_step_logs_start_and_complete(self, caplog):
        """_shutdown_step 记录开始和完成"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        action = MagicMock()
        with caplog.at_level(logging.INFO):
            system._shutdown_step("测试步骤", action)
        assert "开始" in caplog.text
        assert "完成" in caplog.text
        action.assert_called_once()


class TestX4SaveShutdownSnapshot:
    """测试停机快照保存"""

    def test_save_shutdown_snapshot_creates_snapshot(self):
        """_save_shutdown_snapshot 创建快照"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 42
        system.total_tasks_executed = 10
        system.total_tasks_succeeded = 8
        system.snapshot = MagicMock()
        system.config_loader = MagicMock()
        system.config_loader.config = {"key": "val"}
        system._save_shutdown_snapshot()
        system.snapshot.create_snapshot.assert_called_once()
        call_kwargs = system.snapshot.create_snapshot.call_args
        metadata = call_kwargs.kwargs.get("metadata") or call_kwargs[1].get("metadata")
        assert metadata["trigger"] == "shutdown"
        assert metadata["cycle"] == 42

    def test_save_shutdown_snapshot_no_snapshot_attr(self):
        """无 snapshot 属性时不报错"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 0
        system.total_tasks_executed = 0
        system.total_tasks_succeeded = 0
        # 不设置 snapshot 属性
        system._save_shutdown_snapshot()  # 不应抛出异常

    def test_save_shutdown_snapshot_none_snapshot(self):
        """snapshot 为 None 时不报错"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 0
        system.total_tasks_executed = 0
        system.total_tasks_succeeded = 0
        system.snapshot = None
        system._save_shutdown_snapshot()  # 不应抛出异常


class TestX4PeriodicReport:
    """测试定期报告落盘"""

    def _make_system(self):
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 100
        system.config_loader = MagicMock()
        system.run_reporter = MagicMock()
        system._feedback_learner = MagicMock()
        return system

    def test_periodic_report_at_interval(self):
        """到达间隔周期时落盘报告"""
        system = self._make_system()
        system.config_loader.get.return_value = 100
        system._maybe_periodic_report()
        system.run_reporter.collect_from_learner.assert_called_once()
        system.run_reporter.save_report.assert_called_once()

    def test_periodic_report_not_at_interval(self):
        """未到间隔周期时不落盘"""
        system = self._make_system()
        system.cycle_count = 99
        system.config_loader.get.return_value = 100
        system._maybe_periodic_report()
        system.run_reporter.collect_from_learner.assert_not_called()

    def test_periodic_report_interval_zero_disables(self):
        """间隔为0时禁用定期报告"""
        system = self._make_system()
        system.config_loader.get.return_value = 0
        system._maybe_periodic_report()
        system.run_reporter.collect_from_learner.assert_not_called()

    def test_periodic_report_negative_interval_disables(self):
        """负间隔禁用定期报告"""
        system = self._make_system()
        system.config_loader.get.return_value = -1
        system._maybe_periodic_report()
        system.run_reporter.collect_from_learner.assert_not_called()

    def test_periodic_report_failure_does_not_crash(self, caplog):
        """定期报告失败不影响主循环"""
        system = self._make_system()
        system.config_loader.get.return_value = 100
        system.run_reporter.collect_from_learner.side_effect = RuntimeError("disk full")
        with caplog.at_level(logging.WARNING):
            system._maybe_periodic_report()
        assert "定期报告落盘失败" in caplog.text or "disk full" in caplog.text

    def test_periodic_report_uses_config_interval(self):
        """定期报告使用配置的间隔值"""
        system = self._make_system()
        system.config_loader.get.return_value = 50
        system.cycle_count = 50
        system._maybe_periodic_report()
        system.run_reporter.save_report.assert_called_once()


class TestX4StartResetsFlag:
    """测试 start() 重置停机标志"""

    def test_start_resets_shutdown_flag(self):
        """start() 重置停机标志"""
        # 先设置标志
        signal_handler(signal_module.SIGINT, None)
        assert is_shutdown_requested() is True
        # start() 应重置
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system._run_start_sequence = MagicMock()
        system._main_loop = MagicMock()
        system.stop = MagicMock()
        system.start()
        assert is_shutdown_requested() is False
        reset_shutdown_flag()


class TestX4NoDirectSysExitInHandler:
    """测试信号处理器不再直接退出（第一次信号）"""

    def test_handler_uses_flag_not_exit(self):
        """源码中 signal_handler 使用 _shutdown_requested 标志"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_shutdown_requested = True" in content
        assert "is_shutdown_requested" in content
        assert "reset_shutdown_flag" in content

    def test_main_loop_checks_flag(self):
        """主循环检查停机标志"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "is_shutdown_requested()" in content

    def test_stop_has_progress_feedback(self):
        """stop() 有进度反馈"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_shutdown_step" in content
        assert "正在优雅停机" in content
        assert "优雅停机完成" in content

    def test_periodic_report_in_cycle_end(self):
        """_run_cycle_end 包含定期报告"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "_maybe_periodic_report" in content

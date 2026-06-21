"""
X1：配置承诺-行为一致性测试

验证配置项实际生效：
1. cycle_interval 配置影响主循环间隔（H3）
2. task_pool_max_size 配置生效（H4）
3. snapshot 配置生效且自动快照被触发（H7）
4. 初始化顺序正确：task_pool 在 _apply_config 之前创建

第一性原理：系统行为必须与配置承诺一致
"""

import pytest
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


class TestX1CycleIntervalConfig:
    """测试 cycle_interval 配置生效（H3）"""

    def test_sleep_cycle_reads_config(self):
        """_sleep_cycle 读取 cycle_interval 配置"""
        from src.main import AgentSystem
        agent = object.__new__(AgentSystem)
        agent.config_loader = MagicMock()
        agent.config_loader.get = lambda key, default=None: {
            "cycle_interval": 0.5
        }.get(key, default)

        # cycle_time 接近 0，sleep_time 应为 0.5
        with patch("src.main.time.sleep") as mock_sleep:
            agent._sleep_cycle(time.time())
            mock_sleep.assert_called_once()
            called_with = mock_sleep.call_args[0][0]
            assert 0.4 <= called_with <= 0.5, f"Expected ~0.5, got {called_with}"

    def test_sleep_cycle_default_when_no_config(self):
        """无配置时默认 1.0 秒"""
        from src.main import AgentSystem
        agent = object.__new__(AgentSystem)
        agent.config_loader = MagicMock()
        agent.config_loader.get = lambda key, default=None: default

        with patch("src.main.time.sleep") as mock_sleep:
            agent._sleep_cycle(time.time())
            mock_sleep.assert_called_once()
            called_with = mock_sleep.call_args[0][0]
            assert 0.9 <= called_with <= 1.0, f"Expected ~1.0, got {called_with}"

    def test_sleep_cycle_zero_when_cycle_slow(self):
        """周期耗时超过 interval 时不睡眠"""
        from src.main import AgentSystem
        agent = object.__new__(AgentSystem)
        agent.config_loader = MagicMock()
        agent.config_loader.get = lambda key, default=None: {
            "cycle_interval": 0.1
        }.get(key, default)

        # 模拟周期已耗时 0.5 秒（超过 0.1）
        past_start = time.time() - 0.5
        with patch("src.main.time.sleep") as mock_sleep:
            agent._sleep_cycle(past_start)
            mock_sleep.assert_not_called()

    def test_sleep_cycle_not_hardcoded(self):
        """_sleep_cycle 不应硬编码 1.0"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        # 查找 _sleep_cycle 方法体
        import re
        match = re.search(r'def _sleep_cycle.*?(?=\n    def |\nclass )', content, re.DOTALL)
        assert match, "_sleep_cycle method not found"
        method_body = match.group()
        # 不应包含硬编码的 1.0（应从配置读取）
        assert "cycle_interval" in method_body, "应读取 cycle_interval 配置"


class TestX1TaskPoolConfig:
    """测试 task_pool_max_size 配置生效（H4）"""

    def test_init_core_order_correct(self):
        """_init_core 中 _init_state 在 _apply_config 之前"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        # 查找 _init_core 方法
        import re
        match = re.search(r'def _init_core\(self\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_init_core method not found"
        init_core_body = match.group()

        init_state_pos = init_core_body.find("_init_state()")
        apply_config_pos = init_core_body.find("_apply_config()")

        assert init_state_pos > 0, "_init_state() should be called"
        assert apply_config_pos > 0, "_apply_config() should be called"
        assert init_state_pos < apply_config_pos, \
            "_init_state() must come before _apply_config()"

    def test_init_modules_not_call_apply_config(self):
        """_init_modules 不应调用 _apply_config（避免顺序问题）"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _init_modules\(self\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_init_modules method not found"
        init_modules_body = match.group()
        assert "_apply_config" not in init_modules_body, \
            "_init_modules should not call _apply_config (now called in _init_core)"

    def test_apply_task_pool_config_logs(self):
        """_apply_task_pool_config 有日志输出"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _apply_task_pool_config\(self\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_apply_task_pool_config method not found"
        method_body = match.group()
        assert "logger.info" in method_body, "应有日志记录配置应用"

    def test_task_pool_max_size_applied(self):
        """task_pool_max_size 配置能应用到 task_pool"""
        from src.main import AgentSystem
        from src.platform.support.models.base.task import TaskPool

        agent = object.__new__(AgentSystem)
        agent.config_loader = MagicMock()
        agent.config_loader.get = lambda key, default=None: {
            "task_pool_max_size": 200
        }.get(key, default)
        agent.task_pool = TaskPool(max_size=100)

        agent._apply_task_pool_config()
        assert agent.task_pool.max_size == 200


class TestX1SnapshotConfig:
    """测试快照配置生效和自动快照触发（H7）"""

    def test_apply_snapshot_config_exists(self):
        """_apply_snapshot_config 方法存在"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "def _apply_snapshot_config" in content

    def test_apply_config_calls_snapshot(self):
        """_apply_config 调用 _apply_snapshot_config"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _apply_config\(self\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_apply_config method not found"
        apply_config_body = match.group()
        assert "_apply_snapshot_config" in apply_config_body

    def test_maybe_auto_snapshot_exists(self):
        """_maybe_auto_snapshot 方法存在"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "def _maybe_auto_snapshot" in content

    def test_run_cycle_end_calls_snapshot(self):
        """_run_cycle_end 调用 _maybe_auto_snapshot"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _run_cycle_end\(self[^)]*\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_run_cycle_end method not found"
        method_body = match.group()
        assert "_maybe_auto_snapshot" in method_body

    def test_snapshot_config_applied(self):
        """快照配置能应用到 SnapshotManager"""
        from src.main import AgentSystem
        from src.platform.lifecycle.monitor.snapshot import SnapshotManager

        agent = object.__new__(AgentSystem)
        agent.config_loader = MagicMock()
        agent.config_loader.get = lambda key, default=None: {
            "snapshot.snapshot_dir": "/tmp/test_snapshots",
            "snapshot.max_snapshots": 5,
            "snapshot.interval": 60,
        }.get(key, default)
        agent.snapshot = SnapshotManager(snapshot_dir="/tmp/test_snapshots_x1", max_snapshots=10)

        agent._apply_snapshot_config()
        assert agent.snapshot.snapshot_dir == "/tmp/test_snapshots"
        assert agent.snapshot.max_snapshots == 5
        assert agent.snapshot.auto_snapshot_interval == 60

    def test_auto_snapshot_triggered_when_due(self):
        """到期时触发自动快照"""
        from src.main import AgentSystem

        agent = object.__new__(AgentSystem)
        agent.cycle_count = 100
        agent.total_tasks_executed = 50
        agent.total_tasks_succeeded = 45
        agent.config_loader = MagicMock()
        agent.config_loader.config = {"environment": "test"}

        # mock snapshot
        agent.snapshot = MagicMock()
        agent.snapshot.should_auto_snapshot.return_value = True

        # mock state（不用 spec，允许任意属性）
        state = MagicMock()
        state.system.cpu_overall = 0.3
        state.system.memory_usage = 0.4

        agent._maybe_auto_snapshot(state)

        agent.snapshot.create_snapshot.assert_called_once()
        call_kwargs = agent.snapshot.create_snapshot.call_args
        assert call_kwargs[1]["metadata"]["trigger"] == "auto"
        assert call_kwargs[1]["metadata"]["cycle"] == 100

    def test_auto_snapshot_not_triggered_when_not_due(self):
        """未到期时不触发快照"""
        from src.main import AgentSystem

        agent = object.__new__(AgentSystem)
        agent.cycle_count = 1
        agent.total_tasks_executed = 0
        agent.total_tasks_succeeded = 0
        agent.config_loader = MagicMock()
        agent.config_loader.config = {}

        agent.snapshot = MagicMock()
        agent.snapshot.should_auto_snapshot.return_value = False

        state = MagicMock()
        state.system.cpu_overall = 0.1
        state.system.memory_usage = 0.2

        agent._maybe_auto_snapshot(state)
        agent.snapshot.create_snapshot.assert_not_called()

    def test_auto_snapshot_handles_error(self):
        """快照失败不影响主循环"""
        from src.main import AgentSystem

        agent = object.__new__(AgentSystem)
        agent.cycle_count = 1
        agent.total_tasks_executed = 0
        agent.total_tasks_succeeded = 0
        agent.config_loader = MagicMock()
        agent.config_loader.config = {}

        agent.snapshot = MagicMock()
        agent.snapshot.should_auto_snapshot.side_effect = Exception("test error")

        state = MagicMock()
        state.system.cpu_overall = 0.1
        state.system.memory_usage = 0.2

        # 不应抛出异常
        agent._maybe_auto_snapshot(state)


class TestX1ConfigConsistency:
    """测试配置一致性整体验证"""

    def test_all_documented_configs_are_referenced(self):
        """所有文档承诺的配置项在代码中被引用"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")

        documented_configs = [
            "cycle_interval",       # H3 修复
            "task_pool_max_size",   # H4 修复
            "snapshot.snapshot_dir",  # H7 修复
            "snapshot.max_snapshots",
            "snapshot.interval",
            "guardrail.max_cpu_usage",
            "guardrail.max_memory_usage",
            "decision.base_exploration_ratio",
        ]

        for config_key in documented_configs:
            assert config_key in content, \
                f"配置项 {config_key} 应在 main.py 中被引用"

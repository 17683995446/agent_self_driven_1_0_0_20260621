"""
O9：状态回填闭环测试

验证任务执行结果回填到感知层的完整闭环：
1. StateFeedbackChannel基础功能（更新、查询、清空）
2. DecisionEngine接入（执行后记录到通道）
3. Perception接入（构建状态时读取回填数据）
4. 端到端闭环（任务输出影响下一轮感知）

第一性原理：数据流必须闭环
任务执行 → 结果数据 → StateFeedbackChannel → 感知层读取 → 决策依据
"""

import pytest
import threading
from unittest.mock import MagicMock

from src.left.cognition.perception.state_feedback_channel import StateFeedbackChannel
from src.left.action.decision.decision import DecisionEngine
from src.left.cognition.perception.perception import EnvironmentPerceptionModule
from src.platform.support.models.base.task import Task, TaskResult, TaskPriority


def make_system_task(cpu=50.0, memory=60.0, disk=70.0):
    """创建系统健康检查任务"""
    def execute_fn():
        return TaskResult(
            success=True,
            message="system health ok",
            data={"cpu_percent": cpu, "memory_percent": memory, "disk_percent": disk},
        )
    return Task(
        name="system_health_check",
        description="check system health",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


def make_log_task(error_rate=0.1, warning_rate=0.2):
    """创建日志扫描任务"""
    def execute_fn():
        return TaskResult(
            success=True,
            message="log scan ok",
            data={"error_rate": error_rate, "warning_rate": warning_rate},
        )
    return Task(
        name="log_scan",
        description="scan logs",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


def make_log_counts_task(counts=None):
    """创建带counts的日志扫描任务"""
    if counts is None:
        counts = {"ERROR": 5, "WARNING": 10, "INFO": 80, "OTHER": 5}
    def execute_fn():
        return TaskResult(
            success=True,
            message="log scan ok",
            data={"counts": counts},
        )
    return Task(
        name="log_scan_with_counts",
        description="scan logs with counts",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


def make_file_task(total_files=100):
    """创建文件扫描任务"""
    def execute_fn():
        return TaskResult(
            success=True,
            message="file scan ok",
            data={"total_files": total_files},
        )
    return Task(
        name="file_scan",
        description="scan files",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


def make_failed_task():
    """创建失败任务"""
    def execute_fn():
        return TaskResult(success=False, message="failed", data={"cpu_percent": 50.0})
    return Task(
        name="failed_task",
        description="fails",
        target_drive="safe",
        priority=TaskPriority.NORMAL,
        execute_fn=execute_fn,
    )


class TestO9StateFeedbackChannelBasic:
    """测试StateFeedbackChannel基础功能"""

    def test_channel_exists(self):
        """通道类可实例化"""
        channel = StateFeedbackChannel()
        assert channel is not None

    def test_empty_channel_has_no_feedback(self):
        """空通道无反馈"""
        channel = StateFeedbackChannel()
        assert channel.has_feedback() is False

    def test_update_system_feedback(self):
        """更新系统反馈数据"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"cpu_percent": 50.0, "memory_percent": 60.0})
        channel.update_from_result("system_task", result)
        sys_fb = channel.get_system_feedback()
        assert sys_fb["cpu_overall"] == pytest.approx(0.5)
        assert sys_fb["memory_usage"] == pytest.approx(0.6)

    def test_update_system_feedback_with_disk(self):
        """系统反馈包含磁盘"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"cpu_percent": 30.0, "disk_percent": 80.0})
        channel.update_from_result("system_task", result)
        sys_fb = channel.get_system_feedback()
        assert sys_fb["disk_usage"] == pytest.approx(0.8)

    def test_update_log_feedback_with_error_rate(self):
        """更新日志反馈（直接error_rate）"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"error_rate": 0.15})
        channel.update_from_result("log_task", result)
        log_fb = channel.get_log_feedback()
        assert log_fb["error_rate"] == pytest.approx(0.15)

    def test_update_log_feedback_with_counts(self):
        """更新日志反馈（从counts计算）"""
        channel = StateFeedbackChannel()
        counts = {"ERROR": 10, "WARNING": 20, "INFO": 70, "OTHER": 0}
        result = TaskResult(success=True, data={"counts": counts})
        channel.update_from_result("log_task", result)
        log_fb = channel.get_log_feedback()
        assert log_fb["error_rate"] == pytest.approx(0.1)
        assert log_fb["warning_rate"] == pytest.approx(0.2)

    def test_update_file_feedback(self):
        """更新文件反馈"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"total_files": 42})
        channel.update_from_result("file_task", result)
        file_fb = channel.get_file_feedback()
        assert file_fb["total_files"] == 42

    def test_update_file_feedback_with_file_count(self):
        """文件反馈支持file_count字段"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"file_count": 99})
        channel.update_from_result("file_task", result)
        file_fb = channel.get_file_feedback()
        assert file_fb["total_files"] == 99

    def test_failed_result_not_recorded(self):
        """失败任务不记录反馈"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=False, data={"cpu_percent": 50.0})
        channel.update_from_result("failed_task", result)
        assert channel.has_feedback() is False

    def test_empty_data_not_recorded(self):
        """空数据不记录"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={})
        channel.update_from_result("empty_task", result)
        assert channel.has_feedback() is False

    def test_has_feedback_after_update(self):
        """更新后有反馈"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"cpu_percent": 50.0})
        channel.update_from_result("task", result)
        assert channel.has_feedback() is True

    def test_get_last_task_name(self):
        """获取最后更新任务名"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"cpu_percent": 50.0})
        channel.update_from_result("my_task", result)
        assert channel.get_last_task_name() == "my_task"

    def test_clear_resets_all(self):
        """清空重置所有反馈"""
        channel = StateFeedbackChannel()
        result = TaskResult(success=True, data={"cpu_percent": 50.0, "total_files": 10})
        channel.update_from_result("task", result)
        assert channel.has_feedback() is True
        channel.clear()
        assert channel.has_feedback() is False
        assert channel.get_last_task_name() == ""

    def test_multiple_updates_accumulate(self):
        """多次更新累积"""
        channel = StateFeedbackChannel()
        r1 = TaskResult(success=True, data={"cpu_percent": 30.0})
        channel.update_from_result("task1", r1)
        r2 = TaskResult(success=True, data={"total_files": 50})
        channel.update_from_result("task2", r2)
        assert channel.get_system_feedback()["cpu_overall"] == pytest.approx(0.3)
        assert channel.get_file_feedback()["total_files"] == 50
        assert channel.get_last_task_name() == "task2"


class TestO9DecisionEngineIntegration:
    """测试DecisionEngine接入StateFeedbackChannel"""

    def test_backward_compatible_without_channel(self):
        """未注入通道时向后兼容"""
        engine = DecisionEngine()
        task = make_system_task()
        result = engine.execute_task(task)
        assert result.success is True

    def test_successful_task_records_to_channel(self):
        """成功任务记录到通道"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)
        task = make_system_task(cpu=40.0, memory=50.0)
        engine.execute_task(task)
        sys_fb = channel.get_system_feedback()
        assert sys_fb["cpu_overall"] == pytest.approx(0.4)
        assert sys_fb["memory_usage"] == pytest.approx(0.5)

    def test_failed_task_not_recorded(self):
        """失败任务不记录到通道"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)
        task = make_failed_task()
        engine.execute_task(task)
        assert channel.has_feedback() is False

    def test_log_task_records_to_channel(self):
        """日志任务记录到通道"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)
        task = make_log_task(error_rate=0.25)
        engine.execute_task(task)
        log_fb = channel.get_log_feedback()
        assert log_fb["error_rate"] == pytest.approx(0.25)

    def test_file_task_records_to_channel(self):
        """文件任务记录到通道"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)
        task = make_file_task(total_files=77)
        engine.execute_task(task)
        file_fb = channel.get_file_feedback()
        assert file_fb["total_files"] == 77

    def test_last_task_name_updated(self):
        """通道记录最后任务名"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)
        task = make_system_task()
        engine.execute_task(task)
        assert channel.get_last_task_name() == "system_health_check"

    def test_exception_path_does_not_crash(self):
        """任务异常时通道记录不崩溃"""
        channel = StateFeedbackChannel()
        engine = DecisionEngine(state_feedback_channel=channel)

        def boom():
            raise RuntimeError("boom")
        task = Task(
            name="boom_task",
            description="raises",
            target_drive="safe",
            priority=TaskPriority.NORMAL,
            execute_fn=boom,
        )
        result = engine.execute_task(task)
        assert result.success is False


class TestO9PerceptionIntegration:
    """测试感知层接入StateFeedbackChannel"""

    def test_perception_accepts_channel(self):
        """感知模块接受通道注入"""
        perception = EnvironmentPerceptionModule()
        channel = StateFeedbackChannel()
        perception.set_state_feedback_channel(channel)
        assert perception._state_feedback_channel is channel

    def test_perception_without_channel_uses_sensors(self):
        """无通道时使用传感器数据"""
        perception = EnvironmentPerceptionModule()
        state = perception.get_current_state()
        assert state is not None
        assert state.system is not None

    def test_system_feedback_overrides_sensor(self):
        """系统反馈覆盖传感器数据"""
        perception = EnvironmentPerceptionModule()
        channel = StateFeedbackChannel()
        channel.update_from_result("sys_task", TaskResult(
            success=True, data={"cpu_percent": 90.0, "memory_percent": 80.0}
        ))
        perception.set_state_feedback_channel(channel)
        state = perception.get_current_state()
        assert state.system.cpu_overall == pytest.approx(0.9)
        assert state.system.memory_usage == pytest.approx(0.8)

    def test_log_feedback_overrides_scan(self):
        """日志反馈覆盖扫描数据"""
        perception = EnvironmentPerceptionModule()
        channel = StateFeedbackChannel()
        channel.update_from_result("log_task", TaskResult(
            success=True, data={"error_rate": 0.33, "warning_rate": 0.44}
        ))
        perception.set_state_feedback_channel(channel)
        state = perception.get_current_state()
        assert state.logs.error_rate == pytest.approx(0.33)
        assert state.logs.warning_rate == pytest.approx(0.44)

    def test_file_feedback_overrides_scan(self):
        """文件反馈覆盖扫描数据"""
        perception = EnvironmentPerceptionModule()
        channel = StateFeedbackChannel()
        channel.update_from_result("file_task", TaskResult(
            success=True, data={"total_files": 123}
        ))
        perception.set_state_feedback_channel(channel)
        state = perception.get_current_state()
        assert state.files.total_files == 123

    def test_no_feedback_uses_scanned_data(self):
        """无反馈时使用扫描数据"""
        perception = EnvironmentPerceptionModule()
        channel = StateFeedbackChannel()
        perception.set_state_feedback_channel(channel)
        state = perception.get_current_state()
        assert state is not None


class TestO9EndToEndClosedLoop:
    """测试端到端闭环：任务执行 → 反馈 → 感知"""

    def test_task_output_influences_next_perception(self):
        """任务输出影响下一轮感知"""
        channel = StateFeedbackChannel()
        perception = EnvironmentPerceptionModule()
        perception.set_state_feedback_channel(channel)
        engine = DecisionEngine(state_feedback_channel=channel)

        # 执行前感知
        state_before = perception.get_current_state()
        cpu_before = state_before.system.cpu_overall

        # 执行系统任务
        task = make_system_task(cpu=95.0, memory=85.0)
        engine.execute_task(task)

        # 执行后感知应反映任务结果
        state_after = perception.get_current_state()
        assert state_after.system.cpu_overall == pytest.approx(0.95)
        assert state_after.system.memory_usage == pytest.approx(0.85)

    def test_log_task_influences_next_perception(self):
        """日志任务影响下一轮感知"""
        channel = StateFeedbackChannel()
        perception = EnvironmentPerceptionModule()
        perception.set_state_feedback_channel(channel)
        engine = DecisionEngine(state_feedback_channel=channel)

        task = make_log_task(error_rate=0.5, warning_rate=0.3)
        engine.execute_task(task)

        state = perception.get_current_state()
        assert state.logs.error_rate == pytest.approx(0.5)
        assert state.logs.warning_rate == pytest.approx(0.3)

    def test_file_task_influences_next_perception(self):
        """文件任务影响下一轮感知"""
        channel = StateFeedbackChannel()
        perception = EnvironmentPerceptionModule()
        perception.set_state_feedback_channel(channel)
        engine = DecisionEngine(state_feedback_channel=channel)

        task = make_file_task(total_files=256)
        engine.execute_task(task)

        state = perception.get_current_state()
        assert state.files.total_files == 256

    def test_multiple_tasks_accumulate_in_perception(self):
        """多个任务结果累积影响感知"""
        channel = StateFeedbackChannel()
        perception = EnvironmentPerceptionModule()
        perception.set_state_feedback_channel(channel)
        engine = DecisionEngine(state_feedback_channel=channel)

        engine.execute_task(make_system_task(cpu=40.0, memory=50.0))
        engine.execute_task(make_log_task(error_rate=0.2))
        engine.execute_task(make_file_task(total_files=300))

        state = perception.get_current_state()
        assert state.system.cpu_overall == pytest.approx(0.4)
        assert state.logs.error_rate == pytest.approx(0.2)
        assert state.files.total_files == 300

    def test_failed_task_does_not_pollute_perception(self):
        """失败任务不污染感知"""
        channel = StateFeedbackChannel()
        perception = EnvironmentPerceptionModule()
        perception.set_state_feedback_channel(channel)
        engine = DecisionEngine(state_feedback_channel=channel)

        engine.execute_task(make_failed_task())
        state = perception.get_current_state()
        assert channel.has_feedback() is False


class TestO9ThreadSafety:
    """测试线程安全"""

    def test_concurrent_updates(self):
        """并发更新不崩溃"""
        channel = StateFeedbackChannel()
        results = []

        def worker(i):
            result = TaskResult(success=True, data={"cpu_percent": float(i)})
            channel.update_from_result(f"task_{i}", result)
            results.append(channel.get_system_feedback())

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 10

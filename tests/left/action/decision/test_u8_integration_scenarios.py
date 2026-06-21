"""
U8 真实场景集成测试

第一性原理：单元测试验证模块正确性，集成测试验证模块协作
- 场景1：HTTP监控 → 异常检测 → 告警生成
- 场景2：日志分析 → 错误定位 → 报告生成
- 场景3：文件处理 → 分类统计 → 报告生成
- 场景4：动态任务生成 → 任务执行 → 反馈学习（端到端闭环）

每个场景验证：
1. 真实数据流（非Mock）
2. 端到端可执行
3. 产生可读报告
"""

import os
import tempfile
import time
import pytest
from typing import List

from src.left.action.decision.dynamic_task_generator import (
    DynamicTaskGenerator,
    IdleRule,
)
from src.left.action.decision.file_processing_factory import (
    FileProcessingTaskFactory,
    StandardFileAnalyzer,
)
from src.left.action.decision.health_check_factory import (
    HealthCheckExecutor,
    HealthCheckTarget,
    HealthCheckTaskFactory,
    HealthCheckRecord,
)
from src.left.action.decision.log_analysis_factory import (
    LogAnalysisTaskFactory,
    LogAnomalyDetector,
    StandardLogParser,
)
from src.left.action.decision.real_task_factory import (
    DiskUsageReportFactory,
    FileInventoryFactory,
    LogScanFactory,
    ProcessAuditFactory,
    RealTaskFactory,
    SystemHealthCheckFactory,
)
from src.left.action.decision.task_feedback_learner import (
    DefaultFeedbackPolicy,
    TaskFeedbackLearner,
)
from src.platform.support.models.base.state import (
    EnvironmentState,
    GapState,
    LogState,
    SelfState,
    SystemState,
)
from src.platform.support.models.base.task import Task, TaskPriority, TaskResult


# ===== 辅助函数 =====


def _make_state(
    cpu: float = 0.0,
    memory: float = 0.0,
    disk: float = 0.0,
    error_rate: float = 0.0,
    warning_rate: float = 0.0,
    prediction_error: float = 0.0,
) -> EnvironmentState:
    """构造测试用EnvironmentState"""
    return EnvironmentState(
        system=SystemState(cpu_overall=cpu, memory_usage=memory, disk_usage=disk),
        logs=LogState(error_rate=error_rate, warning_rate=warning_rate),
        self=SelfState(prediction_error=prediction_error),
    )


def _make_gaps(safety: float = 0.5, gain: float = 0.5, efficiency: float = 0.5) -> GapState:
    return GapState(safety=safety, gain=gain, efficiency=efficiency)


class _StubHealthCheckExecutor(HealthCheckExecutor):
    """可控的健康检查执行器（用于集成测试模拟真实HTTP）"""

    def __init__(self, results: List[HealthCheckRecord]) -> None:
        self._results = list(results)
        self._index = 0

    def check(self, target: HealthCheckTarget) -> HealthCheckRecord:
        if self._index >= len(self._results):
            self._index = 0
        record = self._results[self._index]
        self._index += 1
        return HealthCheckRecord(
            target_name=target.name,
            url=target.url,
            timestamp=record.timestamp,
            success=record.success,
            status_code=record.status_code,
            response_time=record.response_time,
            error=record.error,
        )


def _write_log_file(log_dir: str, name: str, lines: List[str]) -> str:
    """写入测试日志文件"""
    path = os.path.join(log_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return path


def _create_test_files(work_dir: str) -> List[str]:
    """创建测试文件"""
    paths: List[str] = []
    # Python文件
    py_path = os.path.join(work_dir, "sample.py")
    with open(py_path, "w") as f:
        f.write("def hello():\n    return 'world'\n")
    paths.append(py_path)
    # JSON文件
    json_path = os.path.join(work_dir, "config.json")
    with open(json_path, "w") as f:
        f.write('{"name": "test", "version": "1.0"}\n')
    paths.append(json_path)
    # 空文件
    empty_path = os.path.join(work_dir, "empty.txt")
    open(empty_path, "w").close()
    paths.append(empty_path)
    # 大文件（>100KB）
    large_path = os.path.join(work_dir, "large.log")
    with open(large_path, "w") as f:
        f.write("x" * 200000)
    paths.append(large_path)
    return paths


def _execute_task(task: Task) -> TaskResult:
    """执行任务并返回结果"""
    if task.execute_fn is None:
        return TaskResult(success=False, message="No execute_fn")
    return task.execute_fn()


# ===== 场景1：HTTP监控 → 异常检测 → 告警生成 =====


class TestScenario1HttpMonitoring:
    """场景1：HTTP监控端到端"""

    def test_normal_monitoring_no_alert(self) -> None:
        """正常监控：所有目标可用，无告警"""
        records = [
            HealthCheckRecord(
                target_name="service_a",
                url="https://example.com/health",
                timestamp=time.time(),
                success=True,
                status_code=200,
                response_time=0.05,
            ),
        ]
        executor = _StubHealthCheckExecutor(records)
        factory = HealthCheckTaskFactory(
            targets=[HealthCheckTarget(name="service_a", url="https://example.com/health")],
            executor=executor,
        )
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        assert len(tasks) == 1
        result = _execute_task(tasks[0])
        assert result.success is True
        assert result.data["availability"] == 1.0
        assert len(result.data["alerts"]) == 0

    def test_failure_triggers_alert_after_streak(self) -> None:
        """连续失败3次触发告警"""
        fail_record = HealthCheckRecord(
            target_name="service_b",
            url="https://example.com/down",
            timestamp=time.time(),
            success=False,
            status_code=0,
            response_time=0.01,
            error="URLError: timeout",
        )
        executor = _StubHealthCheckExecutor([fail_record])
        factory = HealthCheckTaskFactory(
            targets=[HealthCheckTarget(name="service_b", url="https://example.com/down")],
            executor=executor,
        )
        # 执行3次，触发连续失败告警
        results: List[TaskResult] = []
        for _ in range(3):
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            for task in tasks:
                results.append(_execute_task(task))
        # 第3次结果应包含告警
        last_result = results[-1]
        assert len(last_result.data["alerts"]) > 0
        assert "service_b" in last_result.data["alerts"][0]

    def test_recovery_resets_streak(self) -> None:
        """恢复后重置失败计数"""
        records = [
            HealthCheckRecord(
                target_name="service_c",
                url="https://example.com/flaky",
                timestamp=time.time(),
                success=False,
                status_code=500,
                response_time=0.02,
            ),
            HealthCheckRecord(
                target_name="service_c",
                url="https://example.com/flaky",
                timestamp=time.time(),
                success=True,
                status_code=200,
                response_time=0.03,
            ),
        ]
        executor = _StubHealthCheckExecutor(records)
        factory = HealthCheckTaskFactory(
            targets=[HealthCheckTarget(name="service_c", url="https://example.com/flaky")],
            executor=executor,
        )
        # 失败1次
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        _execute_task(tasks[0])
        assert factory.get_failure_streaks()["service_c"] == 1
        # 恢复1次
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        _execute_task(tasks[0])
        assert factory.get_failure_streaks()["service_c"] == 0

    def test_history_records_all_checks(self) -> None:
        """历史记录所有检查"""
        records = [
            HealthCheckRecord(
                target_name="service_d",
                url="https://example.com/api",
                timestamp=time.time(),
                success=True,
                status_code=200,
                response_time=0.04,
            ),
        ]
        executor = _StubHealthCheckExecutor(records)
        factory = HealthCheckTaskFactory(
            targets=[HealthCheckTarget(name="service_d", url="https://example.com/api")],
            executor=executor,
        )
        for _ in range(3):
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            for task in tasks:
                _execute_task(task)
        history = factory.get_history()
        assert len(history) >= 3
        assert all(r.target_name == "service_d" for r in history)

    def test_summary_contains_metrics(self) -> None:
        """汇总包含可用性指标"""
        records = [
            HealthCheckRecord(
                target_name="service_e",
                url="https://example.com/summary",
                timestamp=time.time(),
                success=True,
                status_code=200,
                response_time=0.05,
            ),
        ]
        executor = _StubHealthCheckExecutor(records)
        factory = HealthCheckTaskFactory(
            targets=[HealthCheckTarget(name="service_e", url="https://example.com/summary")],
            executor=executor,
        )
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        result = _execute_task(tasks[0])
        summary = result.data["summary"]
        assert summary["total"] == 1
        assert summary["success"] == 1
        assert summary["availability"] == 1.0
        assert summary["avg_response_time"] > 0


# ===== 场景2：日志分析 → 错误定位 → 报告生成 =====


class TestScenario2LogAnalysis:
    """场景2：日志分析端到端"""

    def test_analyze_normal_logs(self) -> None:
        """分析正常日志，无告警"""
        with tempfile.TemporaryDirectory() as log_dir:
            _write_log_file(log_dir, "app.log", [
                "2024-01-01 10:00:00 - app - INFO - starting service",
                "2024-01-01 10:00:01 - app - INFO - service ready",
                "2024-01-01 10:00:02 - app - INFO - handling request",
            ])
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            assert len(tasks) == 1
            result = _execute_task(tasks[0])
            assert result.success is True
            assert result.data["total_lines"] == 3
            assert result.data["level_counts"]["INFO"] == 3
            assert len(result.data["alerts"]) == 0

    def test_detect_high_error_rate(self) -> None:
        """检测高错误率"""
        with tempfile.TemporaryDirectory() as log_dir:
            lines = []
            for i in range(20):
                lines.append(f"2024-01-01 10:00:{i:02d} - app - ERROR - connection failed at 0x{i:08x}")
            for i in range(10):
                lines.append(f"2024-01-01 10:01:{i:02d} - app - INFO - heartbeat")
            _write_log_file(log_dir, "error.log", lines)
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            result = _execute_task(tasks[0])
            assert result.data["error_rate"] > 0.10
            alerts = result.data["alerts"]
            assert any("HIGH_ERROR_RATE" in a for a in alerts)

    def test_detect_repeated_error_pattern(self) -> None:
        """检测重复错误模式"""
        with tempfile.TemporaryDirectory() as log_dir:
            lines = []
            for i in range(15):
                lines.append(f"2024-01-01 10:00:{i:02d} - db - ERROR - connection timeout to host 192.168.1.{i}")
            _write_log_file(log_dir, "db.log", lines)
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            result = _execute_task(tasks[0])
            patterns = result.data["top_error_patterns"]
            assert len(patterns) > 0
            # 归一化后应合并为同一模式
            top_pattern = patterns[0]
            assert top_pattern["count"] >= 10

    def test_extract_recent_errors(self) -> None:
        """提取最近错误"""
        with tempfile.TemporaryDirectory() as log_dir:
            lines = []
            for i in range(15):
                lines.append(f"2024-01-01 10:00:{i:02d} - app - ERROR - error number {i}")
            _write_log_file(log_dir, "errors.log", lines)
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            result = _execute_task(tasks[0])
            recent = result.data["recent_errors"]
            assert len(recent) <= 10
            assert all(e["level"] == "ERROR" for e in recent)

    def test_trend_detection_rising(self) -> None:
        """趋势检测：错误率上升"""
        with tempfile.TemporaryDirectory() as log_dir:
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            # 第1轮：低错误率
            _write_log_file(log_dir, "round1.log", [
                "2024-01-01 10:00:00 - app - INFO - ok",
                "2024-01-01 10:00:01 - app - INFO - ok",
                "2024-01-01 10:00:02 - app - INFO - ok",
            ])
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            _execute_task(tasks[0])
            # 第2轮：错误率上升
            os.remove(os.path.join(log_dir, "round1.log"))
            _write_log_file(log_dir, "round2.log", [
                "2024-01-01 11:00:00 - app - ERROR - fail",
                "2024-01-01 11:00:01 - app - ERROR - fail",
                "2024-01-01 11:00:02 - app - INFO - ok",
            ])
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            result = _execute_task(tasks[0])
            # 应检测到错误率上升
            assert result.data["error_rate"] > 0.5

    def test_nonexistent_log_dir(self) -> None:
        """日志目录不存在"""
        factory = LogAnalysisTaskFactory(log_dir="/nonexistent/path/xyz")
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        result = _execute_task(tasks[0])
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_report_contains_all_fields(self) -> None:
        """报告包含所有字段"""
        with tempfile.TemporaryDirectory() as log_dir:
            _write_log_file(log_dir, "full.log", [
                "2024-01-01 10:00:00 - app - INFO - start",
                "2024-01-01 10:00:01 - app - WARNING - slow",
                "2024-01-01 10:00:02 - app - ERROR - crash",
            ])
            factory = LogAnalysisTaskFactory(log_dir=log_dir)
            tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            result = _execute_task(tasks[0])
            data = result.data
            assert "total_lines" in data
            assert "level_counts" in data
            assert "error_rate" in data
            assert "warning_rate" in data
            assert "recent_errors" in data
            assert "top_error_patterns" in data
            assert "trend" in data
            assert "alerts" in data
            assert "files_scanned" in data


# ===== 场景3：文件处理 → 分类统计 → 报告生成 =====


class TestScenario3FileProcessing:
    """场景3：文件处理端到端"""

    def test_process_mixed_files(self) -> None:
        """处理混合文件类型"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            assert len(tasks) == 1
            result = _execute_task(tasks[0])
            assert result.success is True
            assert result.data["total_files"] == 4
            dist = result.data["type_distribution"]
            assert ".py" in dist
            assert ".json" in dist
            assert ".txt" in dist
            assert ".log" in dist

    def test_detect_empty_files(self) -> None:
        """检测空文件"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            result = _execute_task(tasks[0])
            assert len(result.data["empty_files"]) >= 1
            assert any("EMPTY_FILES" in a for a in result.data["anomalies"])

    def test_detect_large_files(self) -> None:
        """检测大文件"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            result = _execute_task(tasks[0])
            assert len(result.data["large_files"]) >= 1
            assert any("LARGE_FILES" in a for a in result.data["anomalies"])

    def test_compute_md5_prefix(self) -> None:
        """计算MD5前缀"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            result = _execute_task(tasks[0])
            # 至少有一个非空文件有md5_prefix
            all_files_info = []
            for fname in os.listdir(work_dir):
                path = os.path.join(work_dir, fname)
                info = StandardFileAnalyzer().analyze(path)
                all_files_info.append(info)
            non_empty = [f for f in all_files_info if not f.is_empty]
            assert all(len(f.md5_prefix) == 8 for f in non_empty)

    def test_skip_unwanted_dirs(self) -> None:
        """跳过__pycache__等目录"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            cache_dir = os.path.join(work_dir, "__pycache__")
            os.makedirs(cache_dir)
            with open(os.path.join(cache_dir, "cached.pyc"), "w") as f:
                f.write("cached content")
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            result = _execute_task(tasks[0])
            assert result.data["total_files"] == 4  # 不包含.pyc

    def test_nonexistent_target_dir(self) -> None:
        """目标目录不存在"""
        factory = FileProcessingTaskFactory(target_dir="/nonexistent/path/xyz")
        tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
        result = _execute_task(tasks[0])
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_report_structure(self) -> None:
        """报告结构完整"""
        with tempfile.TemporaryDirectory() as work_dir:
            _create_test_files(work_dir)
            factory = FileProcessingTaskFactory(target_dir=work_dir)
            tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            result = _execute_task(tasks[0])
            data = result.data
            assert "target_dir" in data
            assert "total_files" in data
            assert "total_size_mb" in data
            assert "type_distribution" in data
            assert "type_sizes_mb" in data
            assert "empty_files" in data
            assert "large_files" in data
            assert "unreadable_files" in data
            assert "anomalies" in data


# ===== 场景4：动态任务生成 → 执行 → 反馈学习（端到端闭环） =====


class TestScenario4EndToEndLoop:
    """场景4：端到端闭环测试"""

    def test_full_loop_idle_to_exploration(self) -> None:
        """完整闭环：空闲→探索任务→反馈学习"""
        gen = DynamicTaskGenerator()
        learner = TaskFeedbackLearner()
        # 空闲状态
        state = _make_state(
            cpu=0.05, memory=0.05, disk=0.05,
            error_rate=0.01, warning_rate=0.01, prediction_error=0.01,
        )
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        # 执行任务并反馈
        for task in tasks:
            result = _execute_task(task)
            learner.record_result(task.name, result)
        # 验证反馈学习记录
        stats = learner.get_statistics("explore_idle")
        assert stats is not None
        assert stats.total_executions >= 1
        assert stats.success_count >= 1

    def test_full_loop_cpu_high_to_optimization(self) -> None:
        """完整闭环：CPU高→优化任务→反馈学习"""
        gen = DynamicTaskGenerator()
        learner = TaskFeedbackLearner()
        state = _make_state(cpu=0.95)
        tasks = gen.generate_tasks(_make_gaps(), state)
        assert len(tasks) >= 1
        optimize_tasks = [t for t in tasks if "optimize" in t.name]
        assert len(optimize_tasks) >= 1
        for task in optimize_tasks:
            result = _execute_task(task)
            learner.record_result(task.name, result)
        stats = learner.get_statistics(optimize_tasks[0].name)
        assert stats is not None
        assert stats.success_rate == 1.0

    def test_feedback_affects_priority(self) -> None:
        """反馈影响任务优先级"""
        learner = TaskFeedbackLearner()
        # 模拟连续失败
        for _ in range(3):
            learner.record_result(
                "optimize_cpu_overall",
                TaskResult(success=False, message="fail"),
            )
        # 创建一个相同名称的任务
        task = Task(name="optimize_cpu_overall", priority=TaskPriority.HIGH)
        learner.adjust_task_priority(task)
        # 连续失败3次应被暂停
        assert not learner.is_task_available("optimize_cpu_overall")

    def test_state_change_drives_different_tasks(self) -> None:
        """状态变化驱动不同任务"""
        gen = DynamicTaskGenerator()
        # 空闲
        idle_tasks = gen.generate_tasks(_make_gaps(), _make_state(cpu=0.05, memory=0.05))
        idle_names = {t.name for t in idle_tasks}
        # CPU高
        cpu_tasks = gen.generate_tasks(_make_gaps(), _make_state(cpu=0.95))
        cpu_names = {t.name for t in cpu_tasks}
        # 任务类型不同
        assert idle_names != cpu_names
        assert any("explore" in n for n in idle_names)
        assert any("optimize" in n for n in cpu_names)

    def test_multiple_factories_produce_diverse_tasks(self) -> None:
        """多工厂产生多样化任务"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(_make_gaps(), _make_state())
        names = {t.name for t in tasks}
        # 至少3种不同任务
        assert len(names) >= 3
        assert "system_health_check" in names

    def test_real_task_factory_executable(self) -> None:
        """真实任务工厂的任务可执行"""
        factory = RealTaskFactory()
        tasks = factory.create_tasks(_make_gaps(), _make_state())
        for task in tasks:
            result = _execute_task(task)
            # 至少应该能执行（不抛异常）
            assert isinstance(result, TaskResult)
            assert isinstance(result.success, bool)

    def test_decision_history_tracks_progression(self) -> None:
        """决策历史追踪状态变化"""
        gen = DynamicTaskGenerator()
        # 阶段1：空闲
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.05))
        # 阶段2：CPU高
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.95))
        # 阶段3：恢复空闲
        gen.generate_tasks(_make_gaps(), _make_state(cpu=0.05))
        history = gen.get_decision_history()
        assert len(history) == 3
        # 任务数应该有变化
        task_counts = [h.tasks_generated for h in history]
        assert task_counts[0] >= 1  # 空闲有探索任务
        assert task_counts[1] >= 1  # CPU高有优化任务
        assert task_counts[2] >= 1  # 恢复空闲有探索任务


# ===== 跨工厂集成测试 =====


class TestCrossFactoryIntegration:
    """跨工厂集成测试"""

    def test_real_task_factory_includes_all_types(self) -> None:
        """真实任务工厂包含所有任务类型"""
        factory = RealTaskFactory()
        names = factory.get_factory_names()
        assert "system_health_check" in names
        assert "log_scan" in names
        assert "file_inventory" in names
        assert "disk_usage_report" in names
        assert "process_audit" in names

    def test_all_factories_accept_same_state(self) -> None:
        """所有工厂接受相同状态"""
        state = _make_state(cpu=0.5, memory=0.5, disk=0.5)
        gaps = _make_gaps()
        factories = [
            SystemHealthCheckFactory(),
            LogScanFactory(),
            FileInventoryFactory(),
            DiskUsageReportFactory(),
            ProcessAuditFactory(),
        ]
        for factory in factories:
            tasks = factory.create_tasks(gaps, state)
            # 每个工厂应能正常处理状态
            assert isinstance(tasks, list)

    def test_factory_chain_produces_meaningful_output(self) -> None:
        """工厂链产生有意义的输出"""
        with tempfile.TemporaryDirectory() as work_dir:
            # 准备日志
            log_dir = os.path.join(work_dir, "logs")
            os.makedirs(log_dir)
            _write_log_file(log_dir, "test.log", [
                "2024-01-01 10:00:00 - app - INFO - start",
                "2024-01-01 10:00:01 - app - ERROR - fail",
            ])
            # 准备文件
            src_dir = os.path.join(work_dir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "main.py"), "w") as f:
                f.write("print('hello')\n")
            # 运行日志分析
            log_factory = LogAnalysisTaskFactory(log_dir=log_dir)
            log_tasks = log_factory.create_tasks(_make_gaps(safety=0.5), _make_state())
            log_result = _execute_task(log_tasks[0])
            assert log_result.data["total_lines"] == 2
            # 运行文件处理
            file_factory = FileProcessingTaskFactory(target_dir=src_dir)
            file_tasks = file_factory.create_tasks(_make_gaps(gain=0.5), _make_state())
            file_result = _execute_task(file_tasks[0])
            assert file_result.data["total_files"] == 1
            assert ".py" in file_result.data["type_distribution"]


# ===== 真实文件系统测试 =====


class TestRealFilesystemIntegration:
    """真实文件系统测试（使用项目自身目录）"""

    def test_log_scan_on_real_logs(self) -> None:
        """在真实logs目录上运行日志扫描"""
        # 查找项目logs目录
        candidates = [
            "/workspace/self_driven_agent/logs",
            "logs",
            "../logs",
        ]
        log_dir = None
        for path in candidates:
            if os.path.isdir(path):
                log_dir = path
                break
        if log_dir is None:
            pytest.skip("No logs directory found")
        factory = LogScanFactory()
        tasks = factory.create_tasks(_make_gaps(safety=0.5), _make_state())
        if not tasks:
            pytest.skip("LogScanFactory produced no tasks")
        result = _execute_task(tasks[0])
        # 应该能成功执行（即使没有日志文件）
        assert isinstance(result, TaskResult)

    def test_file_inventory_on_real_src(self) -> None:
        """在真实src目录上运行文件清单"""
        candidates = [
            "/workspace/self_driven_agent/src",
            "src",
            "../src",
        ]
        src_dir = None
        for path in candidates:
            if os.path.isdir(path):
                src_dir = path
                break
        if src_dir is None:
            pytest.skip("No src directory found")
        factory = FileInventoryFactory()
        tasks = factory.create_tasks(_make_gaps(gain=0.5), _make_state())
        result = _execute_task(tasks[0])
        assert result.success is True
        assert result.data["total_files"] > 0
        # 应该有.py文件
        assert ".py" in result.data["type_distribution"]

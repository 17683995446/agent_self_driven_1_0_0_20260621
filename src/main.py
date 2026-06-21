#!/usr/bin/env python3
"""
自驱永续进化Agent系统 - MVP主程序

第一性原理：智能 = 持续预测 + 实时修正 + 误差驱动进化

MVP核心循环：
while True:
    state = perceive()          # 感知环境
    gaps = compute_gaps(state)  # 计算缺口
    task = select_task(gaps)    # 选择任务
    execute(task)               # 执行任务
    learn(state, prediction)    # 学习更新
    sleep(1)                    # 等待
"""

import time
import signal
import sys
import os
import argparse
import logging
import json
from logging.handlers import RotatingFileHandler
from abc import ABC
from types import FrameType
from typing import Optional, Dict, Any, List, Callable

from src.platform.support.models.base.state import EnvironmentState, DriveWeights, ResourceUsage, GapState
from src.platform.support.models.base.task import TaskPool, Task
from src.left.cognition.perception.perception import EnvironmentPerceptionModule
from src.left.cognition.prediction.drive_engine import DriveEngineModule
from src.left.action.decision.decision import DecisionEngine
from src.platform.lifecycle.memory.guardrail import SafetyGuardrail
from src.platform.support.infra.event.event_bus import EventBus, EventType, ModuleConnector, EventListener, Event
from src.left.action.execution.monitor import EvolutionMonitor
from src.platform.lifecycle.monitor.snapshot import SnapshotManager
from src.left.cognition.prediction.exploration import AdaptiveExplorationBalancer
from src.platform.lifecycle.memory.plugin_manager import PluginManager
from src.platform.lifecycle.memory.config_loader import ConfigLoader
from src.platform.support.models.base.error_code import ErrorCode, ValidationError
from src.left.action.execution.file_plugin import FilePlugin
from src.left.action.execution.http_plugin import HttpPlugin
from src.left.action.execution.database_plugin import DatabasePlugin
from src.left.action.execution.llm_plugin import LLMPlugin
from src.left.action.execution.code_plugin import CodePlugin
from src.left.action.execution.tool_plugin import ToolPlugin


# 配置日志（X6：彩色终端输出 + 详细文件日志，区分用户面向和技术面向）
_log_dir = os.environ.get("AGENT_LOG_DIR", "logs")
os.makedirs(_log_dir, exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（X6：终端检测，非TTY时纯文本）

    第一性原理：终端输出应视觉区分级别，文件日志应保持纯文本可检索
    """

    _COLORS = {
        logging.DEBUG: "\033[36m",     # 青色
        logging.INFO: "\033[32m",      # 绿色
        logging.WARNING: "\033[33m",   # 黄色
        logging.ERROR: "\033[31m",     # 红色
        logging.CRITICAL: "\033[1;31m", # 加粗红色
    }
    _RESET = "\033[0m"

    def __init__(self, use_color: bool, fmt: str = None) -> None:
        super().__init__(fmt or "%(asctime)s - %(levelname)s - %(message)s")
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        if not self._use_color:
            return super().format(record)
        color = self._COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{self._RESET}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON日志格式化器（X7：结构化日志，便于机器解析）

    第一性原理：日志应同时面向人（文本）和机器（JSON），按需选择
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def _setup_logging(log_format: str = "text") -> None:
    """配置日志系统（X6：区分终端和文件日志，X7：日志轮转+JSON格式）

    Args:
        log_format: 日志格式，"text" 或 "json"
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 清除可能已有的 handlers（避免重复）
    root_logger.handlers.clear()
    # 文件日志：RotatingFileHandler（X7：按大小轮转，保留N份）
    file_handler = RotatingFileHandler(
        os.path.join(_log_dir, 'agent.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8',
    )
    if log_format == "json":
        file_handler.setFormatter(JsonFormatter())
    else:
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    root_logger.addHandler(file_handler)
    # 终端日志：彩色（TTY时）或简洁格式
    stream_handler = logging.StreamHandler(sys.stdout)
    use_color = sys.stdout.isatty() and os.environ.get("AGENT_NO_COLOR", "") == ""
    if log_format == "json":
        stream_handler.setFormatter(JsonFormatter())
    else:
        stream_handler.setFormatter(ColoredFormatter(use_color))
    root_logger.addHandler(stream_handler)


_setup_logging()
logger = logging.getLogger(__name__)


class StatusLogger(EventListener, ABC):
    """状态日志监听器"""

    def __init__(self, agent: 'AgentSystem'):
        super().__init__("status_logger")
        self.agent = agent
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        for et in [
            EventType.CYCLE_END,
            EventType.SAFETY_VIOLATION,
            EventType.TASK_COMPLETED,
            EventType.TASK_FAILED,
        ]:
            self.subscribe(et)

    def on_event(self, event: Event) -> None:
        if event.event_type == EventType.CYCLE_END:
            self._log_cycle_end(event)
        elif event.event_type == EventType.SAFETY_VIOLATION:
            self._log_safety(event)

    def _log_cycle_end(self, event) -> None:
        payload = event.payload
        logger.info(
            f"Cycle {payload.get('cycle')}: "
            f"CPU={payload.get('cpu', 0):.1%} "
            f"Tasks={payload.get('tasks_executed', 0)}"
        )

    def _log_safety(self, event) -> None:
        logger.warning(f"Safety violation: {event.payload.get('reason')}")


class TaskFailureEventListener(EventListener, ABC):
    """任务失败事件监听器（秩序化O7：事件总线双向化）

    订阅TASK_FAILED事件，主动检查任务是否需要暂停
    """

    def __init__(self, agent: 'AgentSystem'):
        super().__init__("task_failure_listener")
        self.agent = agent
        self.failure_events_received: List[str] = []
        self.subscribe(EventType.TASK_FAILED)

    def on_event(self, event: Event) -> None:
        if event.event_type != EventType.TASK_FAILED:
            return
        task_name = event.payload.get("task_name", "unknown")
        self.failure_events_received.append(task_name)
        logger.info(f"TaskFailureListener received: {task_name}")


class SafetyViolationEventListener(EventListener, ABC):
    """安全违规事件监听器（秩序化O7：事件总线双向化）

    订阅SAFETY_VIOLATION事件，记录违规历史
    """

    def __init__(self, agent: 'AgentSystem'):
        super().__init__("safety_violation_listener")
        self.agent = agent
        self.violation_count: int = 0
        self.violation_reasons: List[str] = []
        self.subscribe(EventType.SAFETY_VIOLATION)

    def on_event(self, event: Event) -> None:
        if event.event_type != EventType.SAFETY_VIOLATION:
            return
        self.violation_count += 1
        reason = event.payload.get("reason", "unknown")
        self.violation_reasons.append(reason)
        logger.warning(f"SafetyViolationListener recorded #{self.violation_count}: {reason}")


class CycleMetricsEventListener(EventListener, ABC):
    """周期指标事件监听器（秩序化O7：事件总线双向化）

    订阅CYCLE_END事件，收集周期指标
    """

    def __init__(self, agent: 'AgentSystem'):
        super().__init__("cycle_metrics_listener")
        self.agent = agent
        self.cycle_count: int = 0
        self.last_cpu: float = 0.0
        self.last_success_rate: float = 0.0
        self.subscribe(EventType.CYCLE_END)

    def on_event(self, event: Event) -> None:
        if event.event_type != EventType.CYCLE_END:
            return
        self.cycle_count += 1
        self.last_cpu = event.payload.get("cpu", 0.0)
        self.last_success_rate = event.payload.get("success_rate", 0.0)
        logger.debug(f"CycleMetricsListener: cycle={self.cycle_count}, cpu={self.last_cpu:.1%}")


class AgentSystem:
    """
    自驱永续进化Agent系统

    核心闭环：感知 → 驱力计算 → 缺口评估 → 任务生成 → 决策选择 → 执行 → 学习

    第一性原理：
    - 无外部任务驱动
    - 原生驱力自驱
    - 永续进化能力
    - 安全可控进化
    """

    def __init__(self, config_path: Optional[str] = None, log_level: Optional[str] = None,
                 log_dir: Optional[str] = None, log_format: Optional[str] = None):
        self._cli_config_path = config_path
        self._cli_log_level = log_level
        self._cli_log_dir = log_dir
        self._cli_log_format = log_format
        self._init_core()
        logger.info("Agent system initialized")

    def _init_core(self) -> None:
        self._init_logging()
        self._init_event_bus()
        self._init_connectors()
        self._init_modules()
        self._init_state()
        self._apply_config()
        self._init_listeners()

    def _init_logging(self) -> None:
        # X7：支持 --log-format 重新配置日志格式
        if self._cli_log_format:
            _setup_logging(self._cli_log_format)
            logger.info(f"Log format set to {self._cli_log_format}")
        if self._cli_log_level:
            level = getattr(logging, self._cli_log_level.upper(), logging.INFO)
            logging.getLogger().setLevel(level)
            logger.info(f"Log level set to {self._cli_log_level.upper()}")
        if self._cli_log_dir:
            self._reconfigure_log_dir(self._cli_log_dir)
        logger.info("=" * 60)
        logger.info("自驱永续进化Agent系统启动")
        logger.info("=" * 60)

    def _reconfigure_log_dir(self, log_dir: str) -> None:
        """重新配置日志目录（秩序化U2/U3，X7：使用 RotatingFileHandler）"""
        os.makedirs(log_dir, exist_ok=True)
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'agent.log'),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        # 保持与当前格式一致
        log_format = self._cli_log_format or "text"
        if log_format == "json":
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(file_handler)
        logger.info(f"Log dir set to {log_dir}")

    def _init_event_bus(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.start()

    def _init_connectors(self) -> None:
        self.perception_conn = ModuleConnector(self.event_bus, "perception")
        self.drive_conn = ModuleConnector(self.event_bus, "drive_engine")
        self.decision_conn = ModuleConnector(self.event_bus, "decision")
        self.guardrail_conn = ModuleConnector(self.event_bus, "guardrail")

    def _init_modules(self) -> None:
        self._init_perception_modules()
        self._init_support_modules()
        self._init_decision_modules()

    def _init_perception_modules(self) -> None:
        config_path = self._resolve_config_path()
        self.config_loader = ConfigLoader(config_path)
        self.perception = EnvironmentPerceptionModule()
        self.drive_engine = DriveEngineModule()

    def _resolve_config_path(self) -> str:
        """解析配置文件路径（秩序化U1：配置路径一致性，U2：CLI参数）

        优先级：CLI参数 > 环境变量 AGENT_CONFIG_PATH > 默认 ./config/dev.yaml
        """
        if self._cli_config_path:
            logger.info(f"Config path from CLI: {self._cli_config_path}")
            return self._cli_config_path
        env_path = os.environ.get("AGENT_CONFIG_PATH")
        if env_path:
            logger.info(f"Config path from AGENT_CONFIG_PATH: {env_path}")
            return env_path
        default_path = "./config/dev.yaml"
        logger.info(f"Config path using default: {default_path}")
        return default_path

    def _init_support_modules(self) -> None:
        self.guardrail = SafetyGuardrail()
        self.monitor = EvolutionMonitor()
        self.snapshot = SnapshotManager()
        self.exploration = AdaptiveExplorationBalancer()

    def _init_decision_modules(self) -> None:
        self._init_plugins()
        self._init_real_task_sources()
        self._init_feedback_learner()
        self._init_prediction_correction_loop()
        self._init_run_reporter()
        self._init_state_feedback_channel()
        self.decision = DecisionEngine(
            plugin_manager=self.plugin_manager,
            real_task_factory=self._real_task_factory,
            dynamic_task_generator=self._dynamic_task_generator,
            feedback_learner=self._feedback_learner,
            prediction_correction_loop=self._prediction_correction_loop,
            circuit_breaker=self.guardrail.get_circuit_breaker("task_execution"),
            state_feedback_channel=self._state_feedback_channel,
        )
        self.perception.set_state_feedback_channel(self._state_feedback_channel)

    def _init_real_task_sources(self) -> None:
        """初始化真实任务源（秩序化O1）"""
        from src.left.action.decision.real_task_factory import RealTaskFactory
        from src.left.action.decision.dynamic_task_generator import DynamicTaskGenerator
        self._real_task_factory = RealTaskFactory()
        self._dynamic_task_generator = DynamicTaskGenerator()

    def _init_feedback_learner(self) -> None:
        """初始化反馈学习器（秩序化O3）"""
        from src.left.action.decision.task_feedback_learner import TaskFeedbackLearner
        self._feedback_learner = TaskFeedbackLearner()

    def _init_prediction_correction_loop(self) -> None:
        """初始化预测修正闭环（秩序化O4）"""
        from src.left.action.decision.prediction_correction_loop import PredictionCorrectionLoop
        self._prediction_correction_loop = PredictionCorrectionLoop()

    def _init_run_reporter(self) -> None:
        """初始化运行报告器（秩序化O5）"""
        from src.left.action.decision.run_reporter import RunReporter
        self.run_reporter = RunReporter()

    def _init_state_feedback_channel(self) -> None:
        """初始化状态反馈通道（秩序化O9）"""
        from src.left.cognition.perception.state_feedback_channel import StateFeedbackChannel
        self._state_feedback_channel = StateFeedbackChannel()

    def _apply_config(self) -> None:
        """应用配置到各模块（秩序化O6，X1：增加快照配置）"""
        self._apply_guardrail_config()
        self._apply_decision_config()
        self._apply_task_pool_config()
        self._apply_snapshot_config()
        self._start_hot_reload()
        self._print_config_summary()

    def _print_config_summary(self) -> None:
        """打印配置摘要（秩序化U7：启动反馈）"""
        env = self.config_loader.get("environment", "unknown")
        log_level = self.config_loader.get("log_level", "INFO")
        max_cpu = self.config_loader.get("guardrail.max_cpu_usage", "N/A")
        max_mem = self.config_loader.get("guardrail.max_memory_usage", "N/A")
        config_path = self.config_loader.config_path
        logger.info("=" * 60)
        logger.info("配置摘要:")
        logger.info(f"  配置文件: {config_path}")
        logger.info(f"  环境: {env}")
        logger.info(f"  日志级别: {log_level}")
        logger.info(f"  CPU上限: {max_cpu}")
        logger.info(f"  内存上限: {max_mem}")
        logger.info("=" * 60)

    def _apply_guardrail_config(self) -> None:
        """应用安全护栏配置"""
        max_cpu = self.config_loader.get("guardrail.max_cpu_usage", 0.2)
        max_mem = self.config_loader.get("guardrail.max_memory_usage", 0.2)
        max_disk = self.config_loader.get("guardrail.max_disk_usage", 0.85)
        self.guardrail.max_cpu = max_cpu
        self.guardrail.max_memory = max_mem
        self.guardrail.max_disk = max_disk

    def _apply_decision_config(self) -> None:
        """应用决策引擎配置"""
        exp = self.config_loader.get("decision.base_exploration_ratio", 0.3)
        min_exp = self.config_loader.get("decision.min_exploration_ratio", 0.1)
        max_exp = self.config_loader.get("decision.max_exploration_ratio", 0.5)
        self.decision.base_exploration_ratio = exp
        self.decision.min_exploration_ratio = min_exp
        self.decision.max_exploration_ratio = max_exp
        self.decision.current_exploration_ratio = exp

    def _apply_task_pool_config(self) -> None:
        """应用任务池配置（秩序化O6，X1：修复H4初始化顺序）"""
        max_size = self.config_loader.get("task_pool_max_size", 100)
        if hasattr(self, 'task_pool') and self.task_pool is not None:
            self.task_pool.max_size = max_size
            logger.info(f"Task pool max_size set to {max_size}")

    def _apply_snapshot_config(self) -> None:
        """应用快照配置（X1：修复H7，快照配置生效）"""
        snapshot_dir = self.config_loader.get("snapshot.snapshot_dir", "./logs/snapshots")
        max_snapshots = self.config_loader.get("snapshot.max_snapshots", 10)
        interval = self.config_loader.get("snapshot.interval", 3600)
        if hasattr(self, 'snapshot') and self.snapshot is not None:
            self.snapshot.snapshot_dir = snapshot_dir
            self.snapshot.max_snapshots = max_snapshots
            self.snapshot.auto_snapshot_interval = interval
            logger.info(f"Snapshot config: dir={snapshot_dir}, max={max_snapshots}, interval={interval}s")

    def _start_hot_reload(self) -> None:
        """启动配置热加载（秩序化O6）"""
        try:
            self.config_loader.start_hot_reload(interval=5.0)
            self.config_loader.add_change_listener(self._on_config_changed)
            logger.info("Config hot reload enabled")
        except Exception as e:
            logger.warning(f"Failed to start hot reload: {e}")

    def _on_config_changed(self, new_config: Dict[str, Any]) -> None:
        """配置变更回调（秩序化O6，X1：增加快照配置）"""
        logger.info("Config changed, re-applying...")
        try:
            self._apply_guardrail_config()
            self._apply_decision_config()
            self._apply_task_pool_config()
            self._apply_snapshot_config()
        except Exception as e:
            logger.warning(f"Config re-apply failed: {e}")

    def _init_plugins(self) -> None:
        self.plugin_manager = PluginManager()
        self.plugin_manager.initialize()
        self._register_plugins()
        self._load_plugins()

    def _register_plugins(self) -> None:
        self.plugin_manager.register("file_plugin", FilePlugin(), {"base_path": "."})
        self.plugin_manager.register("http_plugin", HttpPlugin(), {})
        self.plugin_manager.register("database_plugin", DatabasePlugin(), {"db_path": ":memory:"})
        self.plugin_manager.register("llm_plugin", LLMPlugin(), {"api_url": "https://api.openai.com/v1/chat/completions", "api_key": ""})
        self.plugin_manager.register("code_plugin", CodePlugin(), {})
        self.plugin_manager.register("tool_plugin", ToolPlugin(), {})

    def _load_plugins(self) -> None:
        results = self.plugin_manager.load_all()
        for name, success in results.items():
            if success:
                logger.info(f"Plugin {name} loaded")
            else:
                logger.warning(f"Plugin {name} failed to load")

    def _init_state(self) -> None:
        self.task_pool = TaskPool(max_size=100)
        self.running = False
        self.cycle_count = 0
        self.start_time = time.time()
        self.total_tasks_executed = 0
        self.total_tasks_succeeded = 0

    def _init_listeners(self) -> None:
        self.status_logger = StatusLogger(self)
        self.event_bus.subscribe(self.status_logger)
        self._init_event_listeners()

    def _init_event_listeners(self) -> None:
        """初始化事件监听器（秩序化O7：事件总线双向化）"""
        self.task_failure_listener = TaskFailureEventListener(self)
        self.safety_violation_listener = SafetyViolationEventListener(self)
        self.cycle_metrics_listener = CycleMetricsEventListener(self)
        self.event_bus.subscribe(self.task_failure_listener)
        self.event_bus.subscribe(self.safety_violation_listener)
        self.event_bus.subscribe(self.cycle_metrics_listener)
        logger.info("Event listeners initialized (O7: bidirectional event bus)")

    def start(self) -> None:
        """启动Agent系统（X4：重置停机标志，确保干净启动）"""
        reset_shutdown_flag()
        self._run_start_sequence()
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def _run_start_sequence(self) -> None:
        self.running = True
        self.perception.start()
        self._publish_system_start()
        self._log_start()

    def _publish_system_start(self) -> None:
        self.event_bus.publish_simple(
            EventType.SYSTEM_START,
            payload={"timestamp": time.time()},
        )

    def _log_start(self) -> None:
        logger.info("Agent system started")
        logger.info("Entering main loop...")
        # X10：显式就绪标志，供启动脚本探测（L4）
        logger.info("System ready")

    def _main_loop(self):
        """
        主循环

        第一性原理：系统终身唯一运行闭环
        感知环境 → 内生动机 → 自主确定行为 → 多层预测 → 比对现实误差 → 修正模型 → 迭代进化

        X4：检测停机标志位，收到信号后优雅退出循环
        """
        while self.running and not is_shutdown_requested():
            self._run_single_cycle()
        if is_shutdown_requested():
            logger.info("停机标志已设置，退出主循环")

    def _run_single_cycle(self) -> None:
        self.cycle_count += 1
        cycle_start = time.time()
        self._set_cycle(self.cycle_count)
        self._try_execute_steps(cycle_start)

    def _try_execute_steps(self, cycle_start: float) -> None:
        try:
            self._execute_cycle_steps(cycle_start)
        except Exception as e:
            self._handle_cycle_error(e)

    def _execute_cycle_steps(self, cycle_start: float) -> None:
        state, rewards, gaps, weights = self._run_cognition()
        self._run_prediction_correction(state)
        task = self._decide_and_execute(gaps, state, weights)
        self._run_monitor_and_safety(state, rewards, gaps, task)
        self._run_cycle_end(state, cycle_start)

    def _run_prediction_correction(self, state: EnvironmentState) -> None:
        """运行预测-修正闭环（秩序化O4）"""
        predicted = self.decision.predict_next_error(state)
        actual = self.decision.compute_state_error(state)
        self.decision.correct_prediction(predicted, actual, state.timestamp)
        self.decision.adjust_exploration_by_error()
        self.perception.set_prediction_error(self.decision.get_current_prediction_error())

    def _run_cognition(self):
        self._publish_cycle_start()
        state = self._perceive()
        rewards = self._compute_rewards(state)
        gaps = self._compute_gaps(rewards)
        weights = self._compute_weights(state, gaps)
        return state, rewards, gaps, weights

    def _run_monitor_and_safety(self, state, rewards, gaps, task) -> None:
        self._monitor(state, rewards, gaps, task)
        self._safety_check(state)

    def _run_cycle_end(self, state: EnvironmentState, cycle_start: float) -> None:
        self._publish_cycle_end(state, cycle_start)
        self._maybe_auto_snapshot(state)
        self._maybe_periodic_report()
        self._write_runtime_status(state)
        self._log_cycle_feedback(state)
        self._sleep_cycle(cycle_start)

    def _write_runtime_status(self, state: EnvironmentState) -> None:
        """写入运行时状态文件（X5：可观测性，供 status 命令读取）

        第一性原理：运行时状态必须可外部查询，无需侵入进程
        """
        try:
            interval = self.config_loader.get("status.write_interval", 1)
            if interval <= 0:
                return
            if self.cycle_count % interval != 0:
                return
            status = self._build_runtime_status(state)
            self._save_runtime_status(status)
        except Exception as e:
            logger.debug(f"运行时状态写入失败: {e}")

    def _build_runtime_status(self, state: EnvironmentState) -> Dict[str, Any]:
        """构建运行时状态字典（X5）"""
        return {
            "cycle": self.cycle_count,
            "running": self.running,
            "uptime": round(time.time() - self.start_time, 1),
            "tasks_executed": self.total_tasks_executed,
            "tasks_succeeded": self.total_tasks_succeeded,
            "success_rate": round(self._calc_success_rate(), 2),
            "cpu_usage": round(state.system.cpu_overall * 100, 2),
            "memory_usage": round(state.system.memory_usage * 100, 2),
            "config_path": getattr(self.config_loader, 'config_path', 'unknown'),
            "last_update": time.time(),
        }

    def _save_runtime_status(self, status: Dict[str, Any]) -> None:
        """保存运行时状态到文件（X5）"""
        import json
        status_dir = self.config_loader.get("status.dir", "data")
        os.makedirs(status_dir, exist_ok=True)
        status_path = os.path.join(status_dir, "runtime_status.json")
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)

    def _log_cycle_feedback(self, state: EnvironmentState) -> None:
        """周期反馈日志（X5：可配置密度）

        第一性原理：用户应能感知系统运行节奏，但不应被日志淹没
        - DEBUG：每周期输出
        - INFO：每N周期输出（可配置，默认5）
        """
        interval = self.config_loader.get("cycle_feedback_interval", 5)
        if self.cycle_count % interval != 0:
            return
        logger.info(
            f"周期 {self.cycle_count} | "
            f"CPU {state.system.cpu_overall:.1%} | "
            f"内存 {state.system.memory_usage:.1%} | "
            f"任务 {self.total_tasks_executed} | "
            f"成功率 {self._calc_success_rate():.1f}%"
        )

    def _maybe_periodic_report(self) -> None:
        """定期落盘运行报告（X4：每N周期保存一次，防止异常退出丢失数据）

        第一性原理：运行时数据应定期持久化，而非仅在停机时生成
        """
        interval = self.config_loader.get("report.periodic_interval", 100)
        if interval <= 0:
            return
        if self.cycle_count % interval != 0:
            return
        try:
            self.run_reporter.collect_from_learner(self._feedback_learner)
            self.run_reporter.save_report("logs/run_report.txt")
            logger.debug(f"周期报告已落盘 (cycle={self.cycle_count})")
        except Exception as e:
            logger.warning(f"定期报告落盘失败: {e}")

    def _maybe_auto_snapshot(self, state: EnvironmentState) -> None:
        """自动快照检查（X1：修复H7，主循环触发快照）"""
        try:
            if self.snapshot.should_auto_snapshot():
                metrics = self._build_snapshot_metrics(state)
                self.snapshot.create_snapshot(
                    model_state={"cycle": self.cycle_count},
                    config_state=self.config_loader.config,
                    metrics=metrics,
                    metadata={"trigger": "auto", "cycle": self.cycle_count},
                )
        except Exception as e:
            logger.warning(f"Auto snapshot failed: {e}")

    def _build_snapshot_metrics(self, state: EnvironmentState) -> Dict[str, float]:
        """构建快照指标"""
        return {
            "cpu": state.system.cpu_overall,
            "memory": state.system.memory_usage,
            "cycle": float(self.cycle_count),
            "tasks_executed": float(self.total_tasks_executed),
            "success_rate": self.total_tasks_succeeded / max(self.total_tasks_executed, 1),
        }

    def _set_cycle(self, cycle: int) -> None:
        self.perception_conn.set_cycle(cycle)
        self.drive_conn.set_cycle(cycle)
        self.decision_conn.set_cycle(cycle)
        self.guardrail_conn.set_cycle(cycle)

    def _publish_cycle_start(self) -> None:
        self.event_bus.publish_simple(
            EventType.CYCLE_START,
            payload={"cycle": self.cycle_count},
            source="main",
            cycle=self.cycle_count,
        )

    def _perceive(self) -> EnvironmentState:
        state = self.perception.get_current_state()
        self._publish_state(state)
        return state

    def _publish_state(self, state: EnvironmentState) -> None:
        payload = self._build_state_payload(state)
        self.perception_conn.publish(EventType.STATE_UPDATED, payload=payload, async_mode=True)

    def _build_state_payload(self, state: EnvironmentState) -> Dict[str, Any]:
        return {
            "cpu": state.system.cpu_overall,
            "memory": state.system.memory_usage,
            "disk": state.system.disk_usage,
        }

    def _compute_rewards(self, state: EnvironmentState):
        rewards = self.drive_engine.compute_drive_rewards(state)
        self._publish_rewards(rewards)
        return rewards

    def _publish_rewards(self, rewards) -> None:
        payload = self._build_rewards_payload(rewards)
        self.drive_conn.publish(EventType.REWARD_RECEIVED, payload=payload, async_mode=True)

    def _build_rewards_payload(self, rewards) -> Dict[str, Any]:
        return {
            "safety": rewards.safety,
            "gain": rewards.gain,
            "efficiency": rewards.efficiency,
        }

    def _compute_gaps(self, rewards):
        gaps = self.drive_engine.compute_gaps(rewards)
        self._publish_gaps(gaps)
        return gaps

    def _publish_gaps(self, gaps) -> None:
        payload = self._build_gaps_payload(gaps)
        self.drive_conn.publish(EventType.GAPS_COMPUTED, payload=payload, async_mode=True)

    def _build_gaps_payload(self, gaps) -> Dict[str, Any]:
        return {
            "safety": gaps.safety,
            "gain": gaps.gain,
            "efficiency": gaps.efficiency,
        }

    def _compute_weights(self, state: EnvironmentState, gaps: GapState) -> DriveWeights:
        weights = self.drive_engine.compute_weights(state, gaps)
        self._publish_weights(weights)
        return weights

    def _publish_weights(self, weights: DriveWeights) -> None:
        payload = self._build_weights_payload(weights)
        self.drive_conn.publish(EventType.WEIGHTS_UPDATED, payload=payload, async_mode=True)

    def _build_weights_payload(self, weights: DriveWeights) -> Dict[str, Any]:
        return {
            "safe": weights.safe,
            "gain": weights.gain,
            "eff": weights.eff,
        }

    def _decide_and_execute(
        self,
        gaps: GapState,
        state: EnvironmentState,
        weights: DriveWeights,
    ) -> Optional[Task]:
        self._generate_and_add_tasks(gaps, state)
        return self._select_and_execute_task(gaps, weights)

    def _generate_and_add_tasks(self, gaps: GapState, state: EnvironmentState) -> None:
        new_tasks = self.decision.generate_tasks(gaps, state)
        for task in new_tasks:
            self._add_task(task)

    def _add_task(self, task: Task) -> None:
        self.task_pool.add_task(task)
        self.decision_conn.publish(
            EventType.TASK_GENERATED,
            payload={"task_name": task.name},
            async_mode=True,
        )

    def _select_and_execute_task(
        self, gaps: GapState, weights: DriveWeights
    ) -> Optional[Task]:
        task = self.decision.select_next_task(self.task_pool, gaps, weights)
        if task is None:
            return None
        self._publish_task_selected(task)
        self._execute_and_record_task(task)
        return task

    def _publish_task_selected(self, task: Task) -> None:
        self.decision_conn.publish(
            EventType.TASK_SELECTED,
            payload={"task_name": task.name},
            async_mode=True,
        )

    def _execute_and_record_task(self, task: Task) -> None:
        result = self.decision.execute_task(task)
        self.task_pool.record_execution(task)
        self._record_execution_to_reporter(task, result)
        self._record_result(task, result)

    def _record_execution_to_reporter(self, task: Task, result) -> None:
        """记录执行到运行报告器（秩序化O5）"""
        try:
            self.run_reporter.record_execution(
                task.name, result, result.execution_time,
            )
        except Exception as e:
            logger.warning(f"Run reporter record failed: {e}")

    def _record_result(self, task: Task, result) -> None:
        self.total_tasks_executed += 1
        if result.success:
            self.total_tasks_succeeded += 1
            self._publish_task_completed(task, result)
        else:
            self._publish_task_failed(task, result)

    def _publish_task_completed(self, task: Task, result) -> None:
        self.decision_conn.publish(
            EventType.TASK_COMPLETED,
            payload={"task_name": task.name, "result": result.message},
            async_mode=True,
        )

    def _publish_task_failed(self, task: Task, result) -> None:
        self.decision_conn.publish(
            EventType.TASK_FAILED,
            payload={"task_name": task.name, "error": result.message},
            async_mode=True,
        )

    def _monitor(
        self,
        state: EnvironmentState,
        rewards,
        gaps: GapState,
        task: Optional[Task],
    ) -> None:
        executed = task is not None
        success = executed and task.status.name == "COMPLETED"
        self.monitor.update(state, rewards, gaps, task_executed=executed, task_success=success)

    def _safety_check(self, state: EnvironmentState) -> None:
        usage = self._build_usage(state)
        result = self.guardrail.check_resource_usage(usage)
        if not result.allowed:
            self._publish_guardrail(result, usage)
            self._throttle_if_needed(state, result)

    def _build_usage(self, state: EnvironmentState) -> ResourceUsage:
        return ResourceUsage(
            cpu=state.system.cpu_overall,
            memory=state.system.memory_usage,
            disk=state.system.disk_usage,
        )

    def _publish_guardrail(self, result, usage: ResourceUsage) -> None:
        self.guardrail_conn.publish(
            EventType.SAFETY_VIOLATION,
            payload={"reason": result.reason, "usage": usage.to_dict()},
        )

    def _throttle_if_needed(self, state: EnvironmentState, result) -> None:
        """节流（X6：添加节流说明日志，M3）

        第一性原理：节流时用户必须知道发生了什么，而非系统"卡住"
        """
        if state.system.cpu_overall > self.guardrail.max_cpu:
            throttle_duration = 2
            logger.warning(
                f"CPU超限 ({state.system.cpu_overall:.1%} > {self.guardrail.max_cpu:.1%})，"
                f"节流 {throttle_duration} 秒"
            )
            time.sleep(throttle_duration)

    def _publish_cycle_end(self, state: EnvironmentState, cycle_start: float) -> None:
        if self.cycle_count % 10 == 0:
            self._do_publish_cycle_end(state)

    def _do_publish_cycle_end(self, state: EnvironmentState) -> None:
        payload = self._build_cycle_payload(state)
        self.event_bus.publish_simple(
            EventType.CYCLE_END,
            payload=payload,
            source="main",
            cycle=self.cycle_count,
        )

    def _build_cycle_payload(self, state: EnvironmentState) -> Dict[str, Any]:
        return {
            "cycle": self.cycle_count,
            "cpu": state.system.cpu_overall,
            "memory": state.system.memory_usage,
            "tasks_executed": self.total_tasks_executed,
            "success_rate": self.total_tasks_succeeded / max(self.total_tasks_executed, 1),
        }

    def _sleep_cycle(self, cycle_start: float) -> None:
        """睡眠到下一周期（X1：读取 cycle_interval 配置）"""
        cycle_interval = self.config_loader.get("cycle_interval", 1.0)
        cycle_time = time.time() - cycle_start
        sleep_time = max(0, cycle_interval - cycle_time)
        if sleep_time > 0:
            time.sleep(sleep_time)

    def _handle_cycle_error(self, error: Exception) -> None:
        """处理周期错误（X3：按错误码分类处理）

        第一性原理：不同错误类别需要不同的恢复策略
        - 配置类错误(2xxxxx)：配置在运行时变为无效，需较长退避等待修复
        - 资源类错误(3xxxxx)：资源超限，需退避等待资源释放
        - 任务类错误(5xxxxx)：任务执行失败，快速重试
        - 其他错误：默认退避
        """
        error_info = self._extract_error_info(error)
        self._log_cycle_error(error, error_info)
        self._publish_cycle_error(error, error_info)
        backoff = self._compute_error_backoff(error_info)
        time.sleep(backoff)

    def _extract_error_info(self, error: Exception) -> Dict[str, Any]:
        """从异常中提取错误码信息（X3）"""
        if isinstance(error, ValidationError):
            return {
                "has_code": True,
                "code": error.error_code.code,
                "message_key": error.error_code.message_key,
                "field": error.field,
                "category": error.error_code.code // 100000,
            }
        return {"has_code": False, "category": 0}

    def _compute_error_backoff(self, error_info: Dict[str, Any]) -> float:
        """根据错误类别计算退避时间（X3）"""
        category = error_info.get("category", 0)
        if category == 2:  # 系统/配置类
            return 5.0
        if category == 3:  # 资源类
            return 3.0
        if category == 5:  # 任务类
            return 0.5
        return 1.0

    def _log_cycle_error(self, error: Exception, error_info: Dict[str, Any]) -> None:
        """记录周期错误（X3：包含错误码）"""
        if error_info.get("has_code"):
            logger.error(
                f"Cycle error [{error_info['code']}/{error_info['message_key']}] "
                f"field={error_info.get('field', '')}: {error}",
                exc_info=True,
            )
        else:
            logger.error(f"Cycle error: {error}", exc_info=True)

    def _publish_cycle_error(self, error: Exception, error_info: Dict[str, Any]) -> None:
        """发布周期错误事件（X3：携带错误码）"""
        payload: Dict[str, Any] = {"error": str(error)}
        if error_info.get("has_code"):
            payload["error_code"] = error_info["code"]
            payload["error_key"] = error_info["message_key"]
            payload["error_field"] = error_info.get("field", "")
        self.event_bus.publish_simple(
            EventType.SYSTEM_STOP,
            payload=payload,
            source="main",
            cycle=self.cycle_count,
        )

    def stop(self) -> None:
        """停止Agent系统（X4：优雅停机进度反馈）

        第一性原理：停机过程必须可感知，每一步都有进度反馈
        顺序：停止感知 → 关闭插件 → 停止热加载 → 保存快照 → 生成报告 → 停止事件总线
        """
        logger.info("=" * 60)
        logger.info("正在优雅停机...")
        self.running = False
        self._shutdown_step("停止感知模块", self.perception.stop)
        self._shutdown_step("关闭插件", self._shutdown_plugins)
        self._shutdown_step("停止配置热加载", self._stop_hot_reload)
        self._shutdown_step("保存停机快照", self._save_shutdown_snapshot)
        self._shutdown_step("生成运行报告", self._generate_run_report)
        self._shutdown_step("停止事件总线", self.event_bus.stop)
        self._log_stop_stats()
        logger.info("优雅停机完成")
        logger.info("=" * 60)

    def _shutdown_step(self, name: str, action: Callable) -> None:
        """执行停机步骤并打印进度（X4）"""
        logger.info(f"  [{name}] 开始...")
        try:
            action()
            logger.info(f"  [{name}] 完成")
        except Exception as e:
            logger.warning(f"  [{name}] 失败: {e}")

    def _save_shutdown_snapshot(self) -> None:
        """停机时保存快照（X4）"""
        if not hasattr(self, 'snapshot') or self.snapshot is None:
            return
        metrics = {
            "cycle": float(self.cycle_count),
            "tasks_executed": float(self.total_tasks_executed),
            "success_rate": self.total_tasks_succeeded / max(self.total_tasks_executed, 1),
        }
        self.snapshot.create_snapshot(
            model_state={"cycle": self.cycle_count},
            config_state=self.config_loader.config,
            metrics=metrics,
            metadata={"trigger": "shutdown", "cycle": self.cycle_count},
        )

    def _stop_hot_reload(self) -> None:
        """停止配置热加载（秩序化O6）"""
        try:
            if hasattr(self, 'config_loader'):
                self.config_loader.stop_hot_reload()
        except Exception as e:
            logger.warning(f"Failed to stop hot reload: {e}")

    def _generate_run_report(self) -> None:
        """生成运行报告（秩序化O5）"""
        try:
            self.run_reporter.collect_from_learner(self._feedback_learner)
            report_path = self.run_reporter.save_report("logs/run_report.txt")
            logger.info(f"Run report saved to {report_path}")
        except Exception as e:
            logger.warning(f"Failed to generate run report: {e}")

    def _shutdown_plugins(self) -> None:
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.shutdown_all()
            logger.info("All plugins shut down")

    def _log_stop_stats(self) -> None:
        uptime = time.time() - self.start_time
        rate = self._calc_success_rate()
        self._print_stop_banner(uptime, rate)

    def _print_stop_banner(self, uptime: float, rate: float) -> None:
        logger.info("=" * 60)
        logger.info("Agent system stopped")
        logger.info(f"Total cycles: {self.cycle_count}")
        logger.info(f"Total uptime: {uptime:.0f}s")
        logger.info(f"Tasks executed: {self.total_tasks_executed}")
        logger.info(f"Success rate: {rate:.1f}%")
        logger.info("=" * 60)

    def _calc_success_rate(self) -> float:
        return (self.total_tasks_succeeded / max(self.total_tasks_executed, 1)) * 100

    def is_healthy(self) -> bool:
        """健康检查"""
        return self.perception.is_running


def signal_handler(signum: int, frame: Optional[FrameType]) -> None:
    """信号处理（X4：优雅停机，设置标志位而非直接退出）

    第一性原理：信号应触发优雅停机流程，而非粗暴中断
    - 第一次信号：设置停机标志，主循环检测后走优雅停机
    - 第二次信号：强制退出（用户明确要求立即停止）
    """
    global _shutdown_requested
    if _shutdown_requested:
        logger.warning("第二次信号收到，强制退出")
        sys.exit(1)
    _shutdown_requested = True
    logger.info(f"收到信号 {signum}，正在优雅停机...（再次按 Ctrl+C 强制退出）")


# X4：模块级停机标志位
_shutdown_requested = False


def is_shutdown_requested() -> bool:
    """检查是否收到停机信号（X4）"""
    return _shutdown_requested


def reset_shutdown_flag() -> None:
    """重置停机标志（X4：测试用）"""
    global _shutdown_requested
    _shutdown_requested = False


__version__ = "1.0.0"


def _get_build_info() -> str:
    """获取完整构建信息（X10：--version 显示构建信息，L10）"""
    import platform
    info_lines = [
        f"self-driven-agent {__version__}",
        f"  Python:      {platform.python_version()}",
        f"  Platform:    {platform.platform()}",
        f"  Implementation: {platform.python_implementation()}",
    ]
    # 尝试获取包安装时间（基于源文件 mtime）
    try:
        main_file = os.path.abspath(__file__)
        build_time = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(main_file))
        )
        info_lines.append(f"  Build time:  {build_time}")
    except OSError:
        pass
    return "\n".join(info_lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """解析命令行参数（秩序化U2：CLI参数入口，X9：epilog 示例与文档链接）"""
    parser = argparse.ArgumentParser(
        prog="self-driven-agent",
        description="自驱永续进化Agent系统",
        epilog=(
            "示例:\n"
            "  # 启动（默认 prod 环境）\n"
            "  self-driven-agent\n"
            "  self-driven-agent --env dev\n\n"
            "  # 验证配置不启动\n"
            "  self-driven-agent --dry-run\n\n"
            "  # 查询运行状态\n"
            "  self-driven-agent --status\n\n"
            "  # 使用 JSON 结构化日志\n"
            "  self-driven-agent --log-format json\n\n"
            "  # 指定配置文件与日志级别\n"
            "  self-driven-agent --config config/prod.yaml --log-level DEBUG\n\n"
            "文档: docs/deploy_user/README.md\n"
            "故障排查: docs/deploy_user/troubleshooting.md\n"
            "常见问答: docs/deploy_user/FAQ.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        dest="config_path",
        help="配置文件路径（覆盖环境变量 AGENT_CONFIG_PATH）",
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod", "test"],
        help="快捷选择环境配置（等价于 --config config/<env>.yaml）",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--log-dir",
        help="日志输出目录",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="日志格式：text（默认，人类可读）或 json（结构化，机器可解析）",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=_get_build_info(),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="验证配置不启动主循环",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="查询运行中Agent的状态（读取 data/runtime_status.json）",
    )
    return parser.parse_args(argv)


def resolve_config_from_args(args: argparse.Namespace) -> Optional[str]:
    """从CLI参数解析配置路径（秩序化U2）"""
    if args.config_path:
        return args.config_path
    if args.env:
        return f"./config/{args.env}.yaml"
    return None


def main(argv: Optional[List[str]] = None) -> None:
    """主函数（秩序化U2：支持CLI参数，X5：支持status查询）"""
    args = parse_args(argv)

    if args.status:
        _run_status_check()
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config_path = resolve_config_from_args(args)

    if args.dry_run:
        _run_dry_check(config_path, args.log_level)
        return

    agent = AgentSystem(
        config_path=config_path,
        log_level=args.log_level,
        log_dir=args.log_dir,
        log_format=args.log_format,
    )
    agent.start()


def _run_status_check() -> None:
    """查询运行中Agent的状态（X5：读取 runtime_status.json）

    第一性原理：用户应能随时查询系统运行状态，无需侵入进程
    """
    import json
    status_path = os.environ.get("AGENT_STATUS_PATH", "data/runtime_status.json")
    if not os.path.exists(status_path):
        print(f"[STATUS] 状态文件不存在: {status_path}")
        print("[STATUS] Agent 可能未在运行，或状态文件路径不正确")
        print("[STATUS] 提示: 设置环境变量 AGENT_STATUS_PATH 指定状态文件路径")
        sys.exit(1)
    try:
        with open(status_path, "r") as f:
            status = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[STATUS] 状态文件读取失败: {e}")
        sys.exit(1)
    _print_status(status, status_path)


def _print_status(status: Dict[str, Any], status_path: str) -> None:
    """格式化打印运行时状态（X5）"""
    print("=" * 50)
    print("Agent 运行状态")
    print("=" * 50)
    print(f"  运行中:    {'是' if status.get('running') else '否'}")
    print(f"  周期数:    {status.get('cycle', 'N/A')}")
    print(f"  运行时长:  {status.get('uptime', 'N/A')}s")
    print(f"  CPU使用率: {status.get('cpu_usage', 'N/A')}%")
    print(f"  内存使用率: {status.get('memory_usage', 'N/A')}%")
    print(f"  任务执行:  {status.get('tasks_executed', 'N/A')}")
    print(f"  任务成功:  {status.get('tasks_succeeded', 'N/A')}")
    print(f"  成功率:    {status.get('success_rate', 'N/A')}%")
    print(f"  配置文件:  {status.get('config_path', 'N/A')}")
    import datetime
    last_update = status.get('last_update')
    if last_update:
        update_str = datetime.datetime.fromtimestamp(last_update).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  最后更新:  {update_str}")
    print("=" * 50)
    print(f"  状态文件: {status_path}")


def _run_dry_check(config_path: Optional[str], log_level: Optional[str]) -> None:
    """
    dry-run模式：验证配置不启动主循环（X10：增强校验，M9）

    校验项：
    1. 配置文件存在
    2. 配置值范围合法（CPU/内存/探索率）
    3. 核心依赖可用（pyyaml）
    4. 可选依赖状态（numpy/psutil）
    5. 运行目录可写（logs/data/snapshots/memory）
    """
    print("[DRY-RUN] 验证配置...")
    all_ok = True

    # 1. 配置文件存在
    if config_path is None:
        env_path = os.environ.get("AGENT_CONFIG_PATH")
        config_path = env_path or "./config/dev.yaml"
    if not os.path.exists(config_path):
        print(f"[DRY-RUN] ✗ 错误：配置文件不存在: {config_path}")
        print(f"[DRY-RUN]   提示：使用 --env dev/prod/test 或 --config <path> 指定")
        sys.exit(1)
    print(f"[DRY-RUN] ✓ 配置文件: {config_path}")

    # 2. 配置值范围校验（X10：调用 ConfigLoader 的 _validate_config，M9）
    try:
        loader = ConfigLoader(config_path)
        loader._validate_config()
        env = loader.get("environment", "unknown")
        log_lvl = loader.get("log_level", "INFO")
        max_cpu = loader.get("guardrail.max_cpu_usage", "未设置")
        max_mem = loader.get("guardrail.max_memory_usage", "未设置")
        exploration = loader.get("decision.base_exploration_ratio", "未设置")
        print(f"[DRY-RUN] ✓ 配置值范围校验通过")
        print(f"[DRY-RUN]   环境: {env}")
        print(f"[DRY-RUN]   日志级别: {log_lvl}" + (f"（CLI覆盖: {log_level}）" if log_level else ""))
        print(f"[DRY-RUN]   CPU限制: {max_cpu}")
        print(f"[DRY-RUN]   内存限制: {max_mem}")
        print(f"[DRY-RUN]   探索率: {exploration}")
    except Exception as e:
        print(f"[DRY-RUN] ✗ 配置值范围校验失败: {e}")
        all_ok = False

    # 3. 核心依赖检查（X10：M9）
    core_deps_ok = True
    try:
        import yaml  # noqa: F401
        print(f"[DRY-RUN] ✓ 核心依赖: pyyaml")
    except ImportError:
        print(f"[DRY-RUN] ✗ 核心依赖缺失: pyyaml（必需）")
        print(f"[DRY-RUN]   安装: pip install pyyaml")
        core_deps_ok = False
        all_ok = False

    # 4. 可选依赖检查（X10：M9）
    for dep_name in ["numpy", "psutil"]:
        try:
            __import__(dep_name)
            print(f"[DRY-RUN] ✓ 可选依赖: {dep_name}")
        except ImportError:
            print(f"[DRY-RUN] ⚠ 可选依赖缺失: {dep_name}（系统将降级运行）")

    # 5. 目录可写检查（X10：M9）
    project_dir = os.path.dirname(os.path.abspath(config_path))
    project_dir = os.path.dirname(project_dir) if os.path.basename(project_dir) == "config" else project_dir
    for dir_name in ["logs", "data", "snapshots", "memory"]:
        dir_path = os.path.join(project_dir, dir_name)
        try:
            os.makedirs(dir_path, exist_ok=True)
            test_file = os.path.join(dir_path, ".dry_run_write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            print(f"[DRY-RUN] ✓ 目录可写: {dir_name}/")
        except OSError as e:
            print(f"[DRY-RUN] ✗ 目录不可写: {dir_name}/ ({e})")
            all_ok = False

    # 总结
    print("-" * 50)
    if all_ok:
        print("[DRY-RUN] ✓ 所有检查通过，配置有效")
    else:
        print("[DRY-RUN] ✗ 存在检查失败项，请根据上述提示修复")
        sys.exit(1)


if __name__ == "__main__":
    main()

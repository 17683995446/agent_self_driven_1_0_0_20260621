"""
环境感知模块

第一性原理：感知是系统与环境的边界，必须标准化以便替换和扩展
类比：生物的感官系统——视觉、听觉、触觉等
"""

import time
import threading
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

from ....platform.support.models.base.state import (
    EnvironmentState, SystemState, LogState,
    FileState, SelfState
)


logger = logging.getLogger(__name__)


@dataclass
class SensorReading:
    """传感器读数"""
    timestamp: float
    value: float
    unit: str
    confidence: float


@dataclass
class SensorHealth:
    """传感器健康状态"""
    healthy: bool
    last_error: Optional[str]
    error_count: int


class Sensor(ABC):
    """
    传感器抽象基类

    第一性原理：传感器是系统与环境的边界，必须标准化
    """

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """传感器类型标识"""
        pass

    @property
    @abstractmethod
    def sampling_rate(self) -> float:
        """采样频率（Hz）"""
        pass

    @abstractmethod
    def read(self) -> SensorReading:
        """读取当前值"""
        pass

    @abstractmethod
    def calibrate(self) -> bool:
        """校准传感器"""
        pass

    def health_check(self) -> SensorHealth:
        """健康检查"""
        return SensorHealth(healthy=True, last_error=None, error_count=0)


class CPUSensor(Sensor):
    """CPU传感器"""

    @property
    def sensor_type(self) -> str:
        return "cpu"

    @property
    def sampling_rate(self) -> float:
        return 1.0

    def calibrate(self) -> bool:
        return True

    def read(self) -> SensorReading:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            return SensorReading(
                timestamp=time.time(),
                value=cpu_percent / 100.0,
                unit="ratio",
                confidence=0.95,
            )
        except Exception as e:
            logger.warning(f"CPU sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class MemorySensor(Sensor):
    """内存传感器"""

    @property
    def sensor_type(self) -> str:
        return "memory"

    @property
    def sampling_rate(self) -> float:
        return 1.0

    def calibrate(self) -> bool:
        return True

    def read(self) -> SensorReading:
        try:
            mem = psutil.virtual_memory()
            return SensorReading(
                timestamp=time.time(),
                value=mem.percent / 100.0,
                unit="ratio",
                confidence=0.95,
            )
        except Exception as e:
            logger.warning(f"Memory sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class DiskSensor(Sensor):
    """磁盘传感器"""

    @property
    def sensor_type(self) -> str:
        return "disk"

    @property
    def sampling_rate(self) -> float:
        return 0.1

    def calibrate(self) -> bool:
        return True

    def read(self) -> SensorReading:
        try:
            disk = psutil.disk_usage('/')
            return SensorReading(
                timestamp=time.time(),
                value=disk.percent / 100.0,
                unit="ratio",
                confidence=0.95,
            )
        except Exception as e:
            logger.warning(f"Disk sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class ProcessSensor(Sensor):
    """进程传感器"""

    @property
    def sensor_type(self) -> str:
        return "process"

    @property
    def sampling_rate(self) -> float:
        return 0.2

    def calibrate(self) -> bool:
        return True

    def _get_processes(self) -> List[psutil.Process]:
        return list(psutil.process_iter())

    def _count_zombies(self, processes: List[psutil.Process]) -> int:
        return sum(1 for p in processes if p.status() == psutil.STATUS_ZOMBIE)

    def _compute_ratios(self, processes: List[psutil.Process]) -> Tuple[float, float]:
        total = len(processes)
        zombies = self._count_zombies(processes)
        process_ratio = min(total / 1000.0, 1.0)
        zombie_ratio = min(zombies / max(total, 1), 1.0)
        return process_ratio, zombie_ratio

    def read(self) -> SensorReading:
        try:
            processes = self._get_processes()
            process_ratio, _ = self._compute_ratios(processes)
            return SensorReading(
                timestamp=time.time(),
                value=process_ratio,
                unit="ratio",
                confidence=0.9,
            )
        except Exception as e:
            logger.warning(f"Process sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class NetworkSensor(Sensor):
    """网络传感器"""

    @property
    def sensor_type(self) -> str:
        return "network"

    @property
    def sampling_rate(self) -> float:
        return 0.5

    def calibrate(self) -> bool:
        return True

    def _get_io_counters(self):
        return psutil.net_io_counters()

    def _compute_rate(self, counters) -> float:
        total = counters.bytes_sent + counters.bytes_recv
        return min(total / (100 * 1024 * 1024), 1.0)

    def read(self) -> SensorReading:
        try:
            counters = self._get_io_counters()
            rate = self._compute_rate(counters)
            return SensorReading(
                timestamp=time.time(),
                value=rate,
                unit="ratio",
                confidence=0.85,
            )
        except Exception as e:
            logger.warning(f"Network sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class IOSensor(Sensor):
    """IO传感器"""

    @property
    def sensor_type(self) -> str:
        return "io"

    @property
    def sampling_rate(self) -> float:
        return 0.5

    def calibrate(self) -> bool:
        return True

    def _get_disk_io(self):
        return psutil.disk_io_counters()

    def _compute_io_rate(self, counters) -> float:
        total = counters.read_bytes + counters.write_bytes
        return min(total / (500 * 1024 * 1024), 1.0)

    def read(self) -> SensorReading:
        try:
            counters = self._get_disk_io()
            rate = self._compute_io_rate(counters)
            return SensorReading(
                timestamp=time.time(),
                value=rate,
                unit="ratio",
                confidence=0.85,
            )
        except Exception as e:
            logger.warning(f"IO sensor error: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)


class PerceptionModuleBase(ABC):
    """感知模块抽象基类"""

    @abstractmethod
    def get_current_state(self) -> EnvironmentState:
        """获取当前环境状态"""
        pass

    @abstractmethod
    def start(self) -> None:
        """启动感知模块"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止感知模块"""
        pass


class EnvironmentPerceptionModule(PerceptionModuleBase):
    """
    环境感知模块

    系统的"感官系统"，负责采集本机全维度状态

    第一性原理：
    - 感知必须全面（系统、日志、文件、自身）
    - 感知必须实时（高频轮询 + 事件触发）
    - 感知必须可靠（故障隔离、数据验证）
    """

    def __init__(self) -> None:
        self.sensors: Dict[str, Sensor] = {}
        self.readings_history: deque = deque(maxlen=1000)
        self.running = False
        self._lock = threading.Lock()
        self._state_feedback_channel = None
        self._register_default_sensors()

    def set_state_feedback_channel(self, channel: Any) -> None:
        """注入状态反馈通道（秩序化O9）"""
        self._state_feedback_channel = channel
        logger.info("State feedback channel injected into perception")

    def _register_default_sensors(self) -> None:
        """注册默认传感器"""
        self.register_sensor(CPUSensor())
        self.register_sensor(MemorySensor())
        self.register_sensor(DiskSensor())
        self.register_sensor(ProcessSensor())
        self.register_sensor(NetworkSensor())
        self.register_sensor(IOSensor())

    def register_sensor(self, sensor: Sensor) -> None:
        """注册传感器"""
        self.sensors[sensor.sensor_type] = sensor
        logger.info(f"Registered sensor: {sensor.sensor_type}")

    def _read_sensor(self, name: str, sensor: Sensor) -> SensorReading:
        """读取单个传感器"""
        try:
            return sensor.read()
        except Exception as e:
            logger.error(f"Sensor {name} failed: {e}")
            return SensorReading(time.time(), 0.0, "ratio", 0.0)

    def _read_all_sensors(self) -> Dict[str, SensorReading]:
        """读取所有传感器"""
        readings: Dict[str, SensorReading] = {}
        for name, sensor in self.sensors.items():
            readings[name] = self._read_sensor(name, sensor)
        return readings

    def _build_system_state(self, readings: Dict[str, SensorReading]) -> SystemState:
        """构建系统状态（秩序化O9：合并任务回填数据）"""
        cpu = readings.get("cpu", SensorReading(0, 0.0, "ratio", 0)).value
        memory = readings.get("memory", SensorReading(0, 0.0, "ratio", 0)).value
        disk = readings.get("disk", SensorReading(0, 0.0, "ratio", 0)).value
        feedback = self._get_system_feedback()
        if feedback:
            cpu = feedback.get("cpu_overall", cpu)
            memory = feedback.get("memory_usage", memory)
            disk = feedback.get("disk_usage", disk)
        return SystemState(
            cpu_overall=cpu,
            memory_usage=memory,
            memory_pressure=memory,
            disk_usage=disk,
            io_wait=readings.get("io", SensorReading(0, 0.0, "ratio", 0)).value,
            network_rate=readings.get("network", SensorReading(0, 0.0, "ratio", 0)).value,
            process_count=readings.get("process", SensorReading(0, 0.0, "ratio", 0)).value,
        )

    def _get_system_feedback(self) -> Dict[str, float]:
        """获取系统状态反馈（秩序化O9）"""
        if self._state_feedback_channel is None:
            return {}
        try:
            return self._state_feedback_channel.get_system_feedback()
        except Exception as e:
            logger.warning(f"Get system feedback failed: {e}")
            return {}

    def _build_log_state(self) -> LogState:
        """构建日志状态（秩序化O2：真实采集 + O9：合并回填）"""
        scanned = self._scan_logs_for_state()
        feedback = self._get_log_feedback()
        if not feedback:
            return scanned
        return LogState(
            error_rate=feedback.get("error_rate", scanned.error_rate),
            warning_rate=feedback.get("warning_rate", scanned.warning_rate),
        )

    def _get_log_feedback(self) -> Dict[str, float]:
        """获取日志状态反馈（秩序化O9）"""
        if self._state_feedback_channel is None:
            return {}
        try:
            return self._state_feedback_channel.get_log_feedback()
        except Exception as e:
            logger.warning(f"Get log feedback failed: {e}")
            return {}

    def _scan_logs_for_state(self) -> LogState:
        """扫描日志目录计算错误率和警告率"""
        log_dir = self._find_log_dir()
        if not os.path.isdir(log_dir):
            return LogState()
        counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "OTHER": 0}
        try:
            for fname in os.listdir(log_dir):
                if not fname.endswith(".log"):
                    continue
                self._count_log_levels(os.path.join(log_dir, fname), counts)
        except (OSError, IOError):
            return LogState()
        return self._compute_log_state(counts)

    def _find_log_dir(self) -> str:
        """查找日志目录"""
        candidates = ["logs", "../logs", "../../logs", "/workspace/self_driven_agent/logs"]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return "logs"

    def _count_log_levels(self, path: str, counts: Dict[str, int]) -> None:
        """统计日志级别"""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    upper = line.upper()
                    if "ERROR" in upper:
                        counts["ERROR"] += 1
                    elif "WARNING" in upper or "WARN" in upper:
                        counts["WARNING"] += 1
                    elif "INFO" in upper:
                        counts["INFO"] += 1
                    else:
                        counts["OTHER"] += 1
        except (OSError, IOError):
            pass

    def _compute_log_state(self, counts: Dict[str, int]) -> LogState:
        """计算日志状态"""
        total = sum(counts.values())
        if total == 0:
            return LogState()
        error_rate = counts["ERROR"] / total
        warning_rate = counts["WARNING"] / total
        return LogState(error_rate=error_rate, warning_rate=warning_rate)

    def _build_file_state(self) -> FileState:
        """构建文件状态（秩序化O2：真实采集 + O9：合并回填）"""
        scanned = self._scan_files_for_state()
        feedback = self._get_file_feedback()
        if not feedback:
            return scanned
        total_files = feedback.get("total_files", scanned.total_files)
        return FileState(total_files=total_files)

    def _get_file_feedback(self) -> Dict[str, Any]:
        """获取文件状态反馈（秩序化O9）"""
        if self._state_feedback_channel is None:
            return {}
        try:
            return self._state_feedback_channel.get_file_feedback()
        except Exception as e:
            logger.warning(f"Get file feedback failed: {e}")
            return {}

    def _scan_files_for_state(self) -> FileState:
        """扫描工作目录统计文件数"""
        target_dir = self._find_target_dir()
        if not os.path.isdir(target_dir):
            return FileState()
        total_files = 0
        try:
            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".pytest_cache")]
                total_files += len(files)
        except (OSError, IOError):
            return FileState()
        return FileState(total_files=total_files)

    def _find_target_dir(self) -> str:
        """查找目标目录"""
        candidates = ["src", "../src", "/workspace/self_driven_agent/src"]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return "src"

    def _build_self_state(self) -> SelfState:
        """构建自身状态（秩序化O2：真实采集）"""
        agent_cpu, agent_memory = self._collect_self_metrics()
        prediction_error = self._get_prediction_error()
        return SelfState(
            agent_cpu=agent_cpu,
            agent_memory=agent_memory,
            prediction_error=prediction_error,
        )

    def _collect_self_metrics(self) -> Tuple[float, float]:
        """采集Agent自身CPU和内存"""
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            cpu = proc.cpu_percent(interval=0.01) / 100.0
            mem = proc.memory_percent() / 100.0
            return (max(0.0, min(1.0, cpu)), max(0.0, min(1.0, mem)))
        except (ImportError, Exception):
            return (0.0, 0.0)

    def _get_prediction_error(self) -> float:
        """获取预测误差（从外部注入或默认0）"""
        return getattr(self, "_injected_prediction_error", 0.0)

    def set_prediction_error(self, error: float) -> None:
        """注入预测误差（供PredictionCorrectionLoop调用）"""
        self._injected_prediction_error = max(0.0, min(1.0, error))

    def _build_state(self, readings: Dict[str, SensorReading]) -> EnvironmentState:
        """构建完整环境状态"""
        return EnvironmentState(
            timestamp=time.time(),
            system=self._build_system_state(readings),
            logs=self._build_log_state(),
            files=self._build_file_state(),
            self=self._build_self_state(),
        )

    def _update_and_return(self, state: EnvironmentState) -> EnvironmentState:
        """更新历史并返回状态"""
        self.readings_history.append(state)
        return state

    def get_current_state(self) -> EnvironmentState:
        """
        获取当前环境状态

        第一性原理：状态必须包含预测下一状态所需的全部信息
        """
        with self._lock:
            readings = self._read_all_sensors()
            state = self._build_state(readings)
            return self._update_and_return(state)

    def get_recent_history(self, n: int = 10) -> List[EnvironmentState]:
        """获取最近n个状态"""
        with self._lock:
            return list(self.readings_history)[-n:]

    def start(self) -> None:
        """启动感知模块"""
        self.running = True
        logger.info("Perception module started")

    def stop(self) -> None:
        """停止感知模块"""
        self.running = False
        logger.info("Perception module stopped")

    @property
    def is_running(self) -> bool:
        return self.running


class SensorManager:
    """
    传感器管理器

    统一管理所有传感器，确保采样同步、故障隔离、资源控制
    """

    def __init__(self) -> None:
        self.sensors: Dict[str, Sensor] = {}
        self.readings_buffer: deque = deque(maxlen=10000)
        self.running = False

    def register_sensor(self, sensor: Sensor) -> None:
        """注册传感器"""
        self.sensors[sensor.sensor_type] = sensor

    def unregister_sensor(self, sensor_type: str) -> None:
        """注销传感器"""
        self.sensors.pop(sensor_type, None)

    def get_sensor(self, sensor_type: str) -> Optional[Sensor]:
        """获取指定传感器"""
        return self.sensors.get(sensor_type)

    def list_sensors(self) -> List[str]:
        """列出所有传感器类型"""
        return list(self.sensors.keys())

    def calibrate_all(self) -> Dict[str, bool]:
        """校准所有传感器"""
        return {name: sensor.calibrate() for name, sensor in self.sensors.items()}

    def health_check_all(self) -> Dict[str, SensorHealth]:
        """检查所有传感器健康状态"""
        return {name: sensor.health_check() for name, sensor in self.sensors.items()}

    def read_all(self) -> Dict[str, SensorReading]:
        """读取所有传感器"""
        readings: Dict[str, SensorReading] = {}
        for name, sensor in self.sensors.items():
            readings[name] = sensor.read()
        return readings

    def start_sampling(self) -> None:
        """开始采样"""
        self.running = True

    def stop_sampling(self) -> None:
        """停止采样"""
        self.running = False

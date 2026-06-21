"""
日志审计与可追溯性系统

第一性原理：操作必须可追溯，状态必须可复现
- 每条审计记录包含Trace ID，支持跨模块追踪
- 日志追加-only，带完整性校验链
- 支持按时间/类型/严重级别查询

类比：生物的"记忆痕迹"——每个经历都有时间戳和上下文，
支持事后回溯和经验提取
"""

import hashlib
import json
import time
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type


class AuditLevel(Enum):
    """审计级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """审计事件类型"""
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    CYCLE_START = auto()
    CYCLE_END = auto()
    TASK_EXECUTE = auto()
    TASK_COMPLETE = auto()
    TASK_FAIL = auto()
    SAFETY_VIOLATION = auto()
    SNAPSHOT_CREATE = auto()
    SNAPSHOT_ROLLBACK = auto()
    CONFIG_CHANGE = auto()
    SLEEP_ENTER = auto()
    SLEEP_WAKE = auto()
    EXPLORE_START = auto()
    EXPLORE_STOP = auto()
    AGENT_REGISTER = auto()
    AGENT_UNREGISTER = auto()
    PREDICTION_UPDATE = auto()
    MEMORY_ARCHIVE = auto()


@dataclass
class AuditRecord:
    """审计记录"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""
    cycle: int = 0
    severity: str = "info"
    details: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    record_hash: str = ""

    def compute_hash(self) -> str:
        """计算记录哈希"""
        data = {
            "record_id": self.record_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "cycle": self.cycle,
            "severity": self.severity,
            "details": self.details,
            "prev_hash": self.prev_hash,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type,
            "cycle": self.cycle,
            "severity": self.severity,
            "details": self.details,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
        }

    @classmethod
    def from_dict(cls: Type["AuditRecord"], data: Dict[str, Any]) -> "AuditRecord":
        record = cls(
            record_id=data.get("record_id", ""),
            trace_id=data.get("trace_id", ""),
            timestamp=data.get("timestamp", 0.0),
            event_type=data.get("event_type", ""),
            cycle=data.get("cycle", 0),
            severity=data.get("severity", "info"),
            details=data.get("details", {}),
            prev_hash=data.get("prev_hash", ""),
            record_hash=data.get("record_hash", ""),
        )
        return record


class AuditTrailBase(ABC):
    """审计追踪抽象基类"""

    @abstractmethod
    def record(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        severity: AuditLevel = AuditLevel.INFO,
        trace_id: str = "",
    ) -> str:
        """记录审计事件，返回record_id"""
        pass

    @abstractmethod
    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditLevel] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """查询审计记录"""
        pass

    @abstractmethod
    def verify_integrity(self) -> bool:
        """验证日志完整性"""
        pass


class AuditTrail(AuditTrailBase):
    """
    审计追踪系统

    职责：
    1. 记录所有关键操作，带Trace ID和哈希链
    2. 支持按条件查询审计记录
    3. 验证日志未被篡改
    4. 与事件总线集成，自动记录系统事件

    第一性原理：
    - 不可抵赖：每条记录有唯一ID和哈希
    - 不可篡改：哈希链确保顺序和完整性
    - 可追溯：Trace ID串联跨模块操作
    """

    def _init_file(self, audit_dir: Path) -> None:
        self._audit_file = audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self._last_hash = self._load_last_hash()

    def _init_context(self) -> None:
        self._trace_context: threading.local = threading.local()
        self._trace_context.trace_id = ""

    def __init__(self, audit_dir: str = "./logs/audit") -> None:
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cycle = 0
        self._init_context()
        self._listeners: List[Callable[[AuditRecord], None]] = []
        self._init_file(self.audit_dir)

    def _read_last_hash_from_lines(self, lines: List[str]) -> str:
        """从行列表中读取最后一条记录的哈希"""
        if not lines:
            return "0" * 16
        try:
            last = json.loads(lines[-1].strip())
            return last.get("record_hash", "0" * 16)
        except (json.JSONDecodeError, KeyError):
            return "0" * 16

    def _load_last_hash(self) -> str:
        """加载最后一条记录的哈希"""
        if not self._audit_file.exists():
            return "0" * 16
        with open(self._audit_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return self._read_last_hash_from_lines(lines)

    def set_cycle(self, cycle: int) -> None:
        """设置当前循环周期"""
        self._cycle = cycle

    def set_trace_id(self, trace_id: str) -> None:
        """设置当前线程的Trace ID"""
        self._trace_context.trace_id = trace_id

    def get_trace_id(self) -> str:
        """获取当前线程的Trace ID"""
        return getattr(self._trace_context, "trace_id", "")

    def generate_trace_id(self) -> str:
        """生成新的Trace ID并设置到当前线程"""
        trace_id = str(uuid.uuid4())[:8]
        self.set_trace_id(trace_id)
        return trace_id

    def add_listener(self, listener: Callable[[AuditRecord], None]) -> None:
        """添加审计记录监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[AuditRecord], None]) -> None:
        """移除审计记录监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _validate_record_args(self, event_type: AuditEventType, details: Dict[str, Any]) -> None:
        """验证记录参数"""
        if not isinstance(event_type, AuditEventType):
            raise ValueError("event_type must be AuditEventType")
        if not isinstance(details, dict):
            raise ValueError("details must be dict")

    def _resolve_trace_id(self, trace_id: str) -> str:
        """解析追踪ID"""
        tid = trace_id or self.get_trace_id()
        if not tid:
            tid = self.generate_trace_id()
        return tid

    def _build_record(self, tid: str, event_type: AuditEventType, severity: AuditLevel, details: Dict[str, Any]) -> AuditRecord:
        """构建审计记录"""
        record = AuditRecord(
            trace_id=tid,
            event_type=event_type.name,
            cycle=self._cycle,
            severity=severity.value,
            details=details,
            prev_hash=self._last_hash,
        )
        record.record_hash = record.compute_hash()
        self._last_hash = record.record_hash
        return record

    def _write_record(self, record: AuditRecord) -> None:
        """写入审计记录到文件"""
        with self._lock:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False, default=str) + "\n")

    def _notify_listeners(self, record: AuditRecord) -> None:
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(record)
            except Exception:
                pass

    def record(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        severity: AuditLevel = AuditLevel.INFO,
        trace_id: str = "",
    ) -> str:
        """
        记录审计事件

        Args:
            event_type: 事件类型
            details: 事件详情
            severity: 严重级别
            trace_id: 追踪ID，为空则使用当前线程的trace_id

        Returns:
            record_id: 记录唯一标识
        """
        self._validate_record_args(event_type, details)
        tid = self._resolve_trace_id(trace_id)
        record = self._build_record(tid, event_type, severity, details)
        self._write_record(record)
        self._notify_listeners(record)
        return record.record_id

    def _read_audit_lines(self) -> List[str]:
        """读取审计文件所有行"""
        with self._lock:
            with open(self._audit_file, "r", encoding="utf-8") as f:
                return f.readlines()

    def _matches_filters(
        self,
        record: AuditRecord,
        event_type: Optional[AuditEventType],
        severity: Optional[AuditLevel],
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> bool:
        """检查记录是否匹配过滤条件"""
        if event_type and record.event_type != event_type.name:
            return False
        if severity and record.severity != severity.value:
            return False
        if start_time and record.timestamp < start_time:
            return False
        if end_time and record.timestamp > end_time:
            return False
        return True

    def _parse_audit_line(self, line: str) -> Optional[AuditRecord]:
        """解析单行审计记录"""
        try:
            data = json.loads(line.strip())
            return AuditRecord.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditLevel] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """
        查询审计记录

        Args:
            event_type: 按事件类型过滤
            severity: 按严重级别过滤
            start_time: 开始时间戳
            end_time: 结束时间戳
            limit: 最大返回条数

        Returns:
            匹配的审计记录列表
        """
        if limit < 1:
            raise ValueError("limit must be >= 1")

        results: List[AuditRecord] = []
        if not self._audit_file.exists():
            return results

        lines = self._read_audit_lines()
        for line in reversed(lines):
            if len(results) >= limit:
                break
            record = self._parse_audit_line(line)
            if record is None:
                continue
            if self._matches_filters(record, event_type, severity, start_time, end_time):
                results.append(record)

        return results

    def _read_records_for_trace(self, trace_id: str) -> List[AuditRecord]:
        """读取所有匹配追踪ID的记录"""
        results: List[AuditRecord] = []
        lines = self._read_audit_lines()
        for line in lines:
            record = self._parse_audit_line(line)
            if record and record.trace_id == trace_id:
                results.append(record)
        return results

    def query_by_trace_id(self, trace_id: str) -> List[AuditRecord]:
        """
        按追踪ID查询所有相关记录

        Args:
            trace_id: 追踪ID

        Returns:
            该追踪ID下的所有记录，按时间排序
        """
        if not trace_id:
            raise ValueError("trace_id is required")

        if not self._audit_file.exists():
            return []

        results = self._read_records_for_trace(trace_id)
        results.sort(key=lambda r: r.timestamp)
        return results

    def _verify_single_record(
        self,
        record: AuditRecord,
        prev_hash: str,
        issues: List[str]
    ) -> Tuple[str, int]:
        """验证单条记录，返回(新prev_hash, 无效数)"""
        invalid = 0
        if record.prev_hash != prev_hash:
            invalid += 1
            issues.append(f"Hash chain broken at {record.record_id}")
        expected_hash = record.compute_hash()
        if record.record_hash != expected_hash:
            invalid += 1
            issues.append(f"Hash mismatch at {record.record_id}")
        return record.record_hash, invalid

    def verify_integrity(self) -> bool:
        """
        验证审计记录的完整性

        检查：
        1. 每条记录的哈希是否正确
        2. 记录链是否连续（prev_hash匹配）
        3. 损坏行被跳过
        """
        if not self._audit_file.exists():
            return True

        lines = self._read_audit_lines()
        prev_hash = "0" * 16

        for line in lines:
            record = self._parse_audit_line(line)
            if record is None:
                continue
            if record.prev_hash != prev_hash:
                return False
            expected_hash = record.compute_hash()
            if record.record_hash != expected_hash:
                return False
            prev_hash = record.record_hash

        return True

    def _accumulate_stats(
        self,
        record: AuditRecord,
        event_types: Dict[str, int],
        severity_dist: Dict[str, int],
        timestamps: List[float]
    ) -> None:
        """累加单条记录的统计信息"""
        event_types[record.event_type] = event_types.get(record.event_type, 0) + 1
        severity_dist[record.severity] = severity_dist.get(record.severity, 0) + 1
        timestamps.append(record.timestamp)

    def _build_stats_result(
        self,
        total: int,
        event_types: Dict[str, int],
        severity_dist: Dict[str, int],
        timestamps: List[float]
    ) -> Dict[str, Any]:
        """构建统计结果"""
        return {
            "total_records": total,
            "by_type": event_types,
            "by_severity": severity_dist,
            "time_range": {
                "start": min(timestamps) if timestamps else None,
                "end": max(timestamps) if timestamps else None,
            },
            "integrity_ok": self.verify_integrity(),
        }

    def _empty_stats(self) -> Dict[str, Any]:
        return {
            "total_records": 0,
            "by_type": {},
            "by_severity": {},
            "time_range": {"start": None, "end": None},
            "integrity_ok": True,
        }

    def _collect_stats(self, lines: List[str]) -> Tuple[int, Dict[str, int], Dict[str, int], List[float]]:
        total = 0
        event_types: Dict[str, int] = {}
        severity_dist: Dict[str, int] = {}
        timestamps: List[float] = []
        for line in lines:
            record = self._parse_audit_line(line)
            if record is None:
                continue
            total += 1
            self._accumulate_stats(record, event_types, severity_dist, timestamps)
        return total, event_types, severity_dist, timestamps

    def get_stats(self) -> Dict[str, Any]:
        """
        获取审计统计

        Returns:
            包含各类统计信息的字典
        """
        if not self._audit_file.exists():
            return self._empty_stats()
        lines = self._read_audit_lines()
        total, event_types, severity_dist, timestamps = self._collect_stats(lines)
        return self._build_stats_result(total, event_types, severity_dist, timestamps)

    def export_to_file(self, output_path: str, start_time: Optional[float] = None, end_time: Optional[float] = None) -> int:
        """导出审计记录到文件"""
        records = self.query(start_time=start_time, end_time=end_time, limit=100000)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False, default=str) + "\n")
        return len(records)

    def _should_rotate_by_size(self, max_size_mb: float) -> bool:
        """检查是否应按大小轮转"""
        if not self._audit_file.exists():
            return False
        return self._audit_file.stat().st_size > max_size_mb * 1024 * 1024

    def _perform_rotation(self) -> Path:
        """执行日志轮转"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rotated = self.audit_dir / f"audit_{timestamp}.jsonl"
        self._audit_file.rename(rotated)
        self._last_hash = "0" * 16
        self._audit_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self._audit_file.touch()
        return rotated

    def rotate_if_needed(self, max_size_mb: float = 10.0) -> Optional[Path]:
        """
        按需轮转审计日志

        Args:
            max_size_mb: 单文件最大大小（MB）

        Returns:
            轮转后的文件路径，未轮转则返回None
        """
        with self._lock:
            if self._should_rotate_by_size(max_size_mb):
                return self._perform_rotation()
            return None

    def _build_filter_sets(
        self,
        event_types: Optional[List[AuditEventType]],
        severities: Optional[List[AuditLevel]],
    ) -> tuple:
        """构建过滤集合"""
        type_names = {et.name for et in event_types} if event_types else None
        severity_values = {sv.value for sv in severities} if severities else None
        return type_names, severity_values

    def _match_batch_filters(
        self,
        record: AuditRecord,
        type_names: Optional[set],
        severity_values: Optional[set],
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> bool:
        """检查记录是否匹配批量过滤条件"""
        if type_names and record.event_type not in type_names:
            return False
        if severity_values and record.severity not in severity_values:
            return False
        if start_time and record.timestamp < start_time:
            return False
        if end_time and record.timestamp > end_time:
            return False
        return True

    def query_batch(
        self,
        event_types: Optional[List[AuditEventType]] = None,
        severities: Optional[List[AuditLevel]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """
        批量查询（支持多类型/多级别过滤）

        Args:
            event_types: 事件类型列表
            severities: 严重级别列表
            start_time: 开始时间戳
            end_time: 结束时间戳
            limit: 最大返回条数
        """
        if limit < 1:
            raise ValueError("limit must be >= 1")

        results: List[AuditRecord] = []
        if not self._audit_file.exists():
            return results

        type_names, severity_values = self._build_filter_sets(event_types, severities)
        lines = self._read_audit_lines()
        for line in reversed(lines):
            if len(results) >= limit:
                break
            record = self._parse_audit_line(line)
            if record is None:
                continue
            if self._match_batch_filters(record, type_names, severity_values, start_time, end_time):
                results.append(record)

        return results

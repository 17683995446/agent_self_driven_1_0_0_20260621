"""
日志异常检测任务工厂

第一性原理：系统必须能从自身运行日志中发现异常模式
- 采集：读取真实日志文件
- 分类：按级别统计（ERROR/WARNING/INFO/DEBUG）
- 检测：识别错误率突增、重复错误、新错误类型
- 告警：超阈值时生成告警

类比：生物的"疼痛反射"——感知到组织损伤信号后立即做出反应

核心功能：
1. 读取日志目录下所有.log文件
2. 统计各级别数量和错误率
3. 提取最近N条ERROR摘要
4. 计算错误率趋势（上升/下降/稳定）
5. 超阈值触发告警
"""

import os
import re
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState, GapState
from ....platform.support.models.base.task import Task, TaskPriority, TaskResult


logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    message: str
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }


@dataclass
class LogAnalysisResult:
    """日志分析结果"""
    total_lines: int = 0
    level_counts: Dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0
    warning_rate: float = 0.0
    recent_errors: List[LogEntry] = field(default_factory=list)
    top_error_patterns: List[Tuple[str, int]] = field(default_factory=list)
    trend: str = "stable"
    alerts: List[str] = field(default_factory=list)
    files_scanned: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "level_counts": self.level_counts,
            "error_rate": round(self.error_rate, 4),
            "warning_rate": round(self.warning_rate, 4),
            "recent_errors": [e.to_dict() for e in self.recent_errors],
            "top_error_patterns": [
                {"pattern": p, "count": c} for p, c in self.top_error_patterns
            ],
            "trend": self.trend,
            "alerts": self.alerts,
            "files_scanned": self.files_scanned,
        }


class LogParser(ABC):
    """日志解析器抽象基类"""

    @abstractmethod
    def parse_line(self, line: str, source: str) -> Optional[LogEntry]:
        """解析单行日志"""
        pass


class StandardLogParser(LogParser):
    """标准日志解析器

    支持格式：YYYY-MM-DD HH:MM:SS - name - LEVEL - message
    也支持简单格式：LEVEL message
    """

    PATTERN_STANDARD = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\d]*)\s*-\s*(\S+)\s*-\s*(\w+)\s*-\s*(.*)"
    )
    PATTERN_SIMPLE = re.compile(r"^\s*(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL|FATAL)\b\s*(.*)", re.IGNORECASE)
    VALID_LEVELS = {"ERROR", "WARNING", "WARN", "INFO", "DEBUG", "CRITICAL", "FATAL"}

    def parse_line(self, line: str, source: str) -> Optional[LogEntry]:
        """解析单行日志"""
        entry = self._try_standard_format(line, source)
        if entry is not None:
            return entry
        return self._try_simple_format(line, source)

    def _try_standard_format(self, line: str, source: str) -> Optional[LogEntry]:
        """尝试标准格式解析"""
        match = self.PATTERN_STANDARD.match(line)
        if match is None:
            return None
        return LogEntry(
            timestamp=match.group(1),
            level=match.group(3).upper(),
            message=match.group(4).strip(),
            source=source,
        )

    def _try_simple_format(self, line: str, source: str) -> Optional[LogEntry]:
        """尝试简单格式解析"""
        match = self.PATTERN_SIMPLE.match(line)
        if match is None:
            return None
        return LogEntry(
            timestamp="",
            level=match.group(1).upper(),
            message=match.group(2).strip(),
            source=source,
        )


class LogAnomalyDetector:
    """日志异常检测器

    第一性原理：异常 = 偏离正常模式的显著变化
    - 错误率超阈值
    - 错误率趋势上升
    - 重复错误模式
    """

    ERROR_RATE_THRESHOLD: float = 0.10
    WARNING_RATE_THRESHOLD: float = 0.30
    TREND_WINDOW: int = 5

    def __init__(self) -> None:
        self._error_rate_history: List[float] = []

    def detect(self, result: LogAnalysisResult) -> List[str]:
        """检测异常并生成告警"""
        alerts: List[str] = []
        self._check_error_rate(result, alerts)
        self._check_warning_rate(result, alerts)
        self._check_trend(result, alerts)
        self._check_repeated_errors(result, alerts)
        result.alerts = alerts
        return alerts

    def _check_error_rate(self, result: LogAnalysisResult, alerts: List[str]) -> None:
        """检查错误率"""
        if result.error_rate > self.ERROR_RATE_THRESHOLD:
            alerts.append(
                f"HIGH_ERROR_RATE: {result.error_rate:.2%} exceeds threshold {self.ERROR_RATE_THRESHOLD:.2%}"
            )

    def _check_warning_rate(self, result: LogAnalysisResult, alerts: List[str]) -> None:
        """检查警告率"""
        if result.warning_rate > self.WARNING_RATE_THRESHOLD:
            alerts.append(
                f"HIGH_WARNING_RATE: {result.warning_rate:.2%} exceeds threshold {self.WARNING_RATE_THRESHOLD:.2%}"
            )

    def _check_trend(self, result: LogAnalysisResult, alerts: List[str]) -> None:
        """检查趋势"""
        self._error_rate_history.append(result.error_rate)
        if len(self._error_rate_history) > self.TREND_WINDOW:
            self._error_rate_history = self._error_rate_history[-self.TREND_WINDOW:]
        if len(self._error_rate_history) >= 3:
            trend = self._compute_trend()
            result.trend = trend
            if trend == "rising":
                alerts.append("ERROR_TREND_RISING: error rate is increasing")

    def _compute_trend(self) -> str:
        """计算趋势"""
        history = self._error_rate_history
        if len(history) < 3:
            return "stable"
        recent_avg = sum(history[-2:]) / 2
        older_avg = sum(history[:-2]) / max(len(history) - 2, 1)
        if recent_avg > older_avg * 1.5 and recent_avg > 0.01:
            return "rising"
        if recent_avg < older_avg * 0.5:
            return "falling"
        return "stable"

    def _check_repeated_errors(self, result: LogAnalysisResult, alerts: List[str]) -> None:
        """检查重复错误"""
        if result.top_error_patterns:
            top_pattern, count = result.top_error_patterns[0]
            if count >= 10:
                alerts.append(
                    f"REPEATED_ERROR: pattern '{top_pattern[:50]}' occurred {count} times"
                )


class LogAnalysisTaskFactory:
    """
    日志异常检测任务工厂

    第一性原理：系统必须能从自身运行日志中发现异常模式
    - 读取真实日志文件
    - 统计各级别数量
    - 检测异常模式
    - 生成告警
    """

    MAX_RECENT_ERRORS: int = 10
    MAX_PATTERN_LENGTH: int = 100

    def __init__(
        self,
        log_dir: str = "logs",
        parser: Optional[LogParser] = None,
        detector: Optional[LogAnomalyDetector] = None,
    ) -> None:
        self._log_dir = log_dir
        self._parser = parser or StandardLogParser()
        self._detector = detector or LogAnomalyDetector()
        self._last_result: Optional[LogAnalysisResult] = None

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建日志分析任务"""
        if not self._should_create_task(gaps, state):
            return []
        return [Task(
            name="log_anomaly_detection",
            description="分析日志文件，检测异常模式",
            target_drive="safe",
            priority=TaskPriority.HIGH,
            execute_fn=self._create_analyze_fn(),
        )]

    def _should_create_task(self, gaps: GapState, state: EnvironmentState) -> bool:
        """判断是否应创建任务"""
        if gaps.safety >= 0.2:
            return True
        if state.logs.error_rate >= 0.05:
            return True
        return self._last_result is not None

    def _create_analyze_fn(self) -> Callable[[], TaskResult]:
        """创建分析执行函数"""
        def analyze() -> TaskResult:
            return self._run_analysis()
        return analyze

    def _run_analysis(self) -> TaskResult:
        """执行日志分析"""
        if not os.path.isdir(self._log_dir):
            return self._build_no_dir_result()
        entries = self._collect_entries()
        result = self._build_result(entries)
        self._detector.detect(result)
        self._last_result = result
        return self._to_task_result(result)

    def _build_no_dir_result(self) -> TaskResult:
        """构建目录不存在结果"""
        return TaskResult(
            success=False,
            message=f"Log directory not found: {self._log_dir}",
            data={"log_dir": self._log_dir},
        )

    def _collect_entries(self) -> List[LogEntry]:
        """收集所有日志条目"""
        entries: List[LogEntry] = []
        files_scanned = 0
        for fname in sorted(os.listdir(self._log_dir)):
            if not fname.endswith(".log"):
                continue
            files_scanned += 1
            path = os.path.join(self._log_dir, fname)
            self._parse_file(path, fname, entries)
        return entries

    def _parse_file(
        self, path: str, source: str, entries: List[LogEntry]
    ) -> None:
        """解析单个日志文件"""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    entry = self._parser.parse_line(line.strip(), source)
                    if entry is not None:
                        entries.append(entry)
        except (OSError, IOError):
            pass

    def _build_result(self, entries: List[LogEntry]) -> LogAnalysisResult:
        """构建分析结果"""
        result = LogAnalysisResult()
        result.total_lines = len(entries)
        result.level_counts = self._count_levels(entries)
        result.error_rate = self._compute_rate(entries, "ERROR")
        result.warning_rate = self._compute_rate(entries, "WARNING")
        result.recent_errors = self._extract_recent_errors(entries)
        result.top_error_patterns = self._extract_patterns(entries)
        result.files_scanned = self._count_files()
        return result

    def _count_levels(self, entries: List[LogEntry]) -> Dict[str, int]:
        """统计各级别数量"""
        counts: Dict[str, int] = {}
        for entry in entries:
            counts[entry.level] = counts.get(entry.level, 0) + 1
        return counts

    def _compute_rate(self, entries: List[LogEntry], level: str) -> float:
        """计算指定级别比率"""
        if not entries:
            return 0.0
        count = sum(1 for e in entries if e.level == level)
        return count / len(entries)

    def _extract_recent_errors(self, entries: List[LogEntry]) -> List[LogEntry]:
        """提取最近的ERROR条目"""
        errors = [e for e in entries if e.level in ("ERROR", "CRITICAL", "FATAL")]
        return errors[-self.MAX_RECENT_ERRORS:]

    def _extract_patterns(self, entries: List[LogEntry]) -> List[Tuple[str, int]]:
        """提取错误模式"""
        error_msgs = [
            e.message[:self.MAX_PATTERN_LENGTH]
            for e in entries if e.level in ("ERROR", "CRITICAL", "FATAL")
        ]
        if not error_msgs:
            return []
        pattern_counts: Dict[str, int] = {}
        for msg in error_msgs:
            normalized = self._normalize_pattern(msg)
            pattern_counts[normalized] = pattern_counts.get(normalized, 0) + 1
        return sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    def _normalize_pattern(self, message: str) -> str:
        """归一化错误模式（替换数字和ID为占位符）"""
        result = re.sub(r"0x[0-9a-fA-F]+", "HEXADDR", message)
        result = re.sub(r"\d+", "N", result)
        return result[:self.MAX_PATTERN_LENGTH]

    def _count_files(self) -> int:
        """统计日志文件数"""
        try:
            return sum(
                1 for f in os.listdir(self._log_dir) if f.endswith(".log")
            )
        except (OSError, IOError):
            return 0

    def _to_task_result(self, result: LogAnalysisResult) -> TaskResult:
        """转换为任务结果"""
        has_alerts = len(result.alerts) > 0
        return TaskResult(
            success=not has_alerts,
            message=f"Analyzed {result.files_scanned} files, "
                    f"{result.total_lines} lines: "
                    f"{result.level_counts.get('ERROR', 0)} errors, "
                    f"{result.level_counts.get('WARNING', 0)} warnings"
                    + (f", {len(result.alerts)} alerts" if has_alerts else ""),
            data=result.to_dict(),
        )

    def get_last_result(self) -> Optional[LogAnalysisResult]:
        """获取上次分析结果"""
        return self._last_result

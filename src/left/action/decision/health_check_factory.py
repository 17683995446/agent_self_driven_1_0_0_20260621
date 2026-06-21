"""
HTTP健康监控任务工厂

第一性原理：系统必须能感知外部服务的可用性，才能做出适应性反应
- 监控：定期检查目标URL的可达性和响应时间
- 告警：连续失败时生成告警任务
- 记录：记录历史可用性数据，用于趋势分析

类比：生物的"警觉反应"——持续感知周围环境是否有威胁

核心功能：
1. 配置监控URL列表
2. 每轮循环执行HTTP GET检查
3. 记录响应时间、状态码
4. 连续失败触发告警
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState, GapState
from ....platform.support.models.base.task import Task, TaskPriority, TaskResult


logger = logging.getLogger(__name__)


@dataclass
class HealthCheckTarget:
    """健康检查目标"""
    name: str
    url: str
    expected_status: int = 200
    timeout: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "expected_status": self.expected_status,
            "timeout": self.timeout,
        }


@dataclass
class HealthCheckRecord:
    """健康检查记录"""
    target_name: str
    url: str
    timestamp: float
    success: bool
    status_code: int
    response_time: float
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_name": self.target_name,
            "url": self.url,
            "timestamp": self.timestamp,
            "success": self.success,
            "status_code": self.status_code,
            "response_time": round(self.response_time, 4),
            "error": self.error,
        }


@dataclass
class HealthCheckSummary:
    """健康检查汇总"""
    total: int = 0
    success: int = 0
    failure: int = 0
    avg_response_time: float = 0.0
    records: List[HealthCheckRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "success": self.success,
            "failure": self.failure,
            "availability": round(self.success / max(self.total, 1), 4),
            "avg_response_time": round(self.avg_response_time, 4),
            "records": [r.to_dict() for r in self.records],
        }


class HealthCheckExecutor(ABC):
    """健康检查执行器抽象基类"""

    @abstractmethod
    def check(self, target: HealthCheckTarget) -> HealthCheckRecord:
        """执行健康检查"""
        pass


class HttpHealthCheckExecutor(HealthCheckExecutor):
    """HTTP健康检查执行器"""

    def check(self, target: HealthCheckTarget) -> HealthCheckRecord:
        """执行HTTP GET健康检查"""
        start = time.time()
        status_code, error = self._do_request(target)
        elapsed = time.time() - start
        success = (status_code == target.expected_status) and not error
        return HealthCheckRecord(
            target_name=target.name,
            url=target.url,
            timestamp=start,
            success=success,
            status_code=status_code,
            response_time=elapsed,
            error=error,
        )

    def _do_request(self, target: HealthCheckTarget) -> Tuple[int, str]:
        """执行HTTP请求，返回(状态码, 错误信息)"""
        try:
            from urllib import request, error
            req = request.Request(target.url, method="GET")
            with request.urlopen(req, timeout=target.timeout) as resp:
                return resp.status, ""
        except error.HTTPError as e:
            return e.code, f"HTTPError: {e.code}"
        except error.URLError as e:
            return 0, f"URLError: {e.reason}"
        except Exception as e:
            return 0, f"Exception: {type(e).__name__}: {e}"


class HealthCheckTaskFactory:
    """
    HTTP健康监控任务工厂

    第一性原理：可用性监控是系统感知外部世界的基础能力
    - 配置监控目标列表
    - 生成健康检查任务
    - 汇总检查结果
    - 连续失败触发告警
    """

    DEFAULT_TARGETS: List[HealthCheckTarget] = [
        HealthCheckTarget(
            name="httpbin_ok",
            url="https://httpbin.org/status/200",
            expected_status=200,
        ),
    ]
    MAX_FAILURE_STREAK: int = 3

    def __init__(
        self,
        targets: Optional[List[HealthCheckTarget]] = None,
        executor: Optional[HealthCheckExecutor] = None,
    ) -> None:
        self._targets = targets if targets is not None else list(self.DEFAULT_TARGETS)
        self._executor = executor or HttpHealthCheckExecutor()
        self._history: List[HealthCheckRecord] = []
        self._failure_streaks: Dict[str, int] = {}

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建健康检查任务"""
        if gaps.safety < 0.1 and not self._has_recent_failures():
            return []
        return [Task(
            name="http_health_check",
            description="检查外部服务可用性",
            target_drive="safe",
            priority=TaskPriority.HIGH,
            execute_fn=self._create_check_fn(),
        )]

    def _has_recent_failures(self) -> bool:
        """检查最近是否有失败"""
        if len(self._history) < 1:
            return False
        return any(not r.success for r in self._history[-5:])

    def _create_check_fn(self) -> Callable[[], TaskResult]:
        """创建健康检查执行函数"""
        def check() -> TaskResult:
            return self._run_checks()
        return check

    def _run_checks(self) -> TaskResult:
        """执行所有目标的健康检查"""
        records = self._check_all_targets()
        self._update_history(records)
        summary = self._build_summary(records)
        alert = self._check_alerts(records)
        return self._build_result(summary, alert)

    def _check_all_targets(self) -> List[HealthCheckRecord]:
        """检查所有目标"""
        records: List[HealthCheckRecord] = []
        for target in self._targets:
            record = self._executor.check(target)
            records.append(record)
            self._update_streak(record)
        return records

    def _update_streak(self, record: HealthCheckRecord) -> None:
        """更新连续失败计数"""
        if record.success:
            self._failure_streaks[record.target_name] = 0
        else:
            current = self._failure_streaks.get(record.target_name, 0)
            self._failure_streaks[record.target_name] = current + 1

    def _update_history(self, records: List[HealthCheckRecord]) -> None:
        """更新历史记录"""
        self._history.extend(records)
        if len(self._history) > 100:
            self._history = self._history[-100:]

    def _build_summary(self, records: List[HealthCheckRecord]) -> HealthCheckSummary:
        """构建汇总"""
        total = len(records)
        success = sum(1 for r in records if r.success)
        times = [r.response_time for r in records if r.success]
        avg_time = sum(times) / max(len(times), 1)
        return HealthCheckSummary(
            total=total,
            success=success,
            failure=total - success,
            avg_response_time=avg_time,
            records=records,
        )

    def _check_alerts(self, records: List[HealthCheckRecord]) -> List[str]:
        """检查告警条件"""
        alerts: List[str] = []
        for record in records:
            streak = self._failure_streaks.get(record.target_name, 0)
            if streak >= self.MAX_FAILURE_STREAK:
                alerts.append(
                    f"ALERT: {record.target_name} failed {streak} times consecutively"
                )
        return alerts

    def _build_result(
        self, summary: HealthCheckSummary, alerts: List[str]
    ) -> TaskResult:
        """构建任务结果"""
        availability = summary.success / max(summary.total, 1)
        message = f"Checked {summary.total} targets: {summary.success} ok, {summary.failure} failed"
        if alerts:
            message += f"; {len(alerts)} alerts"
        return TaskResult(
            success=summary.failure == 0,
            message=message,
            data={
                "summary": summary.to_dict(),
                "alerts": alerts,
                "availability": round(availability, 4),
            },
        )

    def get_targets(self) -> List[HealthCheckTarget]:
        """获取监控目标列表"""
        return list(self._targets)

    def add_target(self, target: HealthCheckTarget) -> None:
        """添加监控目标"""
        self._targets.append(target)

    def get_history(self) -> List[HealthCheckRecord]:
        """获取历史记录"""
        return list(self._history)

    def get_failure_streaks(self) -> Dict[str, int]:
        """获取连续失败计数"""
        return dict(self._failure_streaks)

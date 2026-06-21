"""
状态回填通道

第一性原理：任务执行结果必须回填到感知层，形成数据闭环
- 任务采集的真实数据不应丢失
- 下一轮感知应能利用上一轮任务结果
- 数据流：任务执行 → 结果回填 → 感知读取 → 决策依据

类比：生物的"本体感觉"——运动后的肌肉状态反馈到大脑，影响下一步动作
"""

import logging
import threading
from typing import Any, Dict, Optional

from ....platform.support.models.base.task import TaskResult


logger = logging.getLogger(__name__)


class StateFeedbackChannel:
    """
    状态回填通道

    第一性原理：连接任务执行结果与感知层，闭合数据回路
    - 接收任务执行结果中的状态数据
    - 提供感知层查询接口
    - 线程安全，支持并发读写
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._system_feedback: Dict[str, float] = {}
        self._log_feedback: Dict[str, float] = {}
        self._file_feedback: Dict[str, Any] = {}
        self._last_task_name: str = ""
        self._last_update_time: float = 0.0

    def update_from_result(self, task_name: str, result: TaskResult) -> None:
        """从任务结果更新反馈数据（秩序化O9）"""
        if not result.success or not result.data:
            return
        try:
            self._dispatch_update(task_name, result.data)
        except Exception as e:
            logger.warning(f"State feedback update failed: {e}")

    def _dispatch_update(self, task_name: str, data: Dict[str, Any]) -> None:
        """根据任务类型分发更新"""
        with self._lock:
            self._last_task_name = task_name
            import time
            self._last_update_time = time.time()
            if "cpu_percent" in data or "memory_percent" in data:
                self._update_system_feedback(data)
            if "counts" in data or "error_rate" in data:
                self._update_log_feedback(data)
            if "total_files" in data or "file_count" in data:
                self._update_file_feedback(data)

    def _update_system_feedback(self, data: Dict[str, Any]) -> None:
        """更新系统状态反馈"""
        if "cpu_percent" in data:
            self._system_feedback["cpu_overall"] = max(0.0, min(1.0, data["cpu_percent"] / 100.0))
        if "memory_percent" in data:
            self._system_feedback["memory_usage"] = max(0.0, min(1.0, data["memory_percent"] / 100.0))
        if "disk_percent" in data:
            self._system_feedback["disk_usage"] = max(0.0, min(1.0, data["disk_percent"] / 100.0))

    def _update_log_feedback(self, data: Dict[str, Any]) -> None:
        """更新日志状态反馈"""
        if "error_rate" in data:
            self._log_feedback["error_rate"] = max(0.0, min(1.0, float(data["error_rate"])))
            if "warning_rate" in data:
                self._log_feedback["warning_rate"] = max(0.0, min(1.0, float(data["warning_rate"])))
        elif "counts" in data:
            counts = data["counts"]
            total = sum(counts.values()) if counts else 0
            if total > 0:
                self._log_feedback["error_rate"] = max(0.0, min(1.0, counts.get("ERROR", 0) / total))
                self._log_feedback["warning_rate"] = max(0.0, min(1.0, counts.get("WARNING", 0) / total))

    def _update_file_feedback(self, data: Dict[str, Any]) -> None:
        """更新文件状态反馈"""
        if "total_files" in data:
            self._file_feedback["total_files"] = data["total_files"]
        if "file_count" in data:
            self._file_feedback["total_files"] = data["file_count"]

    def get_system_feedback(self) -> Dict[str, float]:
        """获取系统状态反馈"""
        with self._lock:
            return dict(self._system_feedback)

    def get_log_feedback(self) -> Dict[str, float]:
        """获取日志状态反馈"""
        with self._lock:
            return dict(self._log_feedback)

    def get_file_feedback(self) -> Dict[str, Any]:
        """获取文件状态反馈"""
        with self._lock:
            return dict(self._file_feedback)

    def has_feedback(self) -> bool:
        """是否有反馈数据"""
        with self._lock:
            return bool(self._system_feedback or self._log_feedback or self._file_feedback)

    def get_last_task_name(self) -> str:
        """获取最后更新任务名"""
        with self._lock:
            return self._last_task_name

    def clear(self) -> None:
        """清空反馈数据"""
        with self._lock:
            self._system_feedback.clear()
            self._log_feedback.clear()
            self._file_feedback.clear()
            self._last_task_name = ""
            self._last_update_time = 0.0

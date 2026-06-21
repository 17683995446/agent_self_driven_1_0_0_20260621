"""
决策审计日志

第一性原理：所有决策过程必须可审计、可追溯、可解释
记录决策上下文、理由和备选方案，支持事后分析
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ....platform.support.models.base.task import Task
from ....platform.support.models.base.state import GapState, DriveWeights


@dataclass
class DecisionAuditEntry:
    """决策审计条目"""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    cycle: int = 0
    gaps: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    available_tasks: int = 0
    selected_task_id: str = ""
    selected_task_name: str = ""
    selected_task_score: float = 0.0
    is_exploration: bool = False
    reasoning: str = ""
    alternatives: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "cycle": self.cycle,
            "gaps": self.gaps,
            "weights": self.weights,
            "available_tasks": self.available_tasks,
            "selected_task_id": self.selected_task_id,
            "selected_task_name": self.selected_task_name,
            "selected_task_score": self.selected_task_score,
            "is_exploration": self.is_exploration,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
        }


class DecisionAuditLog:
    """
    决策审计日志

    记录所有决策过程，支持事后分析
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: List[DecisionAuditEntry] = []
        self._max_entries = max_entries
        self._cycle = 0

    def set_cycle(self, cycle: int) -> None:
        """设置当前循环周期"""
        self._cycle = cycle

    def log_decision(
        self,
        gaps: GapState,
        weights: DriveWeights,
        available_tasks: List[Task],
        selected_task: Task,
        is_exploration: bool,
        score: float,
    ) -> DecisionAuditEntry:
        """记录决策"""
        entry = self._build_entry(gaps, weights, available_tasks, selected_task, is_exploration, score)
        self._store_entry(entry)
        return entry

    def _build_entry(
        self,
        gaps: GapState,
        weights: DriveWeights,
        available_tasks: List[Task],
        selected_task: Task,
        is_exploration: bool,
        score: float,
    ) -> DecisionAuditEntry:
        """构建审计条目"""
        return DecisionAuditEntry(
            cycle=self._cycle,
            gaps=gaps.to_dict(),
            weights=weights.to_dict(),
            available_tasks=len(available_tasks),
            selected_task_id=selected_task.id,
            selected_task_name=selected_task.name,
            selected_task_score=score,
            is_exploration=is_exploration,
            reasoning=self._generate_reasoning(gaps, selected_task, score, is_exploration),
            alternatives=[t.id for t in available_tasks if t.id != selected_task.id][:5],
        )

    def _store_entry(self, entry: DecisionAuditEntry) -> None:
        """存储条目"""
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def _generate_reasoning(
        self,
        gaps: GapState,
        selected_task: Task,
        score: float,
        is_exploration: bool,
    ) -> str:
        """生成决策理由"""
        dominant = self._dominant_drive(gaps)
        mode = "探索" if is_exploration else "利用"
        return (
            f"主导缺口: {dominant}, "
            f"选择任务: {selected_task.name}, "
            f"得分: {score:.3f}, "
            f"模式: {mode}"
        )

    def _dominant_drive(self, gaps: GapState) -> str:
        """获取主导驱力"""
        drives = {"safe": gaps.safety, "gain": gaps.gain, "eff": gaps.efficiency}
        return max(drives, key=drives.get)

    def get_entries(self, limit: int = 100) -> List[DecisionAuditEntry]:
        """获取最近的审计条目"""
        return self._entries[-limit:]

    def get_entry_count(self) -> int:
        """获取条目总数"""
        return len(self._entries)

    def get_exploration_ratio(self) -> float:
        """获取探索决策比例"""
        if not self._entries:
            return 0.0
        explore_count = sum(1 for e in self._entries if e.is_exploration)
        return explore_count / len(self._entries)

    def get_drive_distribution(self) -> Dict[str, int]:
        """获取驱力选择分布"""
        dist: Dict[str, int] = {}
        for entry in self._entries:
            drive = entry.selected_task_name.split("_")[0] if "_" in entry.selected_task_name else "unknown"
            dist[drive] = dist.get(drive, 0) + 1
        return dist

    def clear(self) -> None:
        """清空日志"""
        self._entries.clear()

"""
DAG可视化与监控

第一性原理：复杂任务的执行过程必须可被观测、可追踪、可理解
- 可视化：将抽象依赖图转化为可读的图描述
- 监控：记录每个节点的状态变化
- 可追溯：事件序列提供完整的执行历史

类比：生物的"本体感觉"——知道自己的肢体在哪里、在做什么
"""

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ....platform.support.models.base.dag import DAGPlan, DAGNode, DAGNodeStatus


class DAGRenderer(ABC):
    """DAG渲染器抽象基类"""

    @abstractmethod
    def render(self, plan: DAGPlan) -> str:
        """将DAG计划渲染为字符串"""


class MermaidDAGRenderer(DAGRenderer):
    """Mermaid流程图渲染器"""

    _STYLES: Dict[DAGNodeStatus, str] = {
        DAGNodeStatus.PENDING: "pending",
        DAGNodeStatus.RUNNING: "running",
        DAGNodeStatus.COMPLETED: "completed",
        DAGNodeStatus.FAILED: "failed",
        DAGNodeStatus.SKIPPED: "skipped",
    }

    def render(self, plan: DAGPlan) -> str:
        lines = self._header()
        lines.extend(self._node_lines(plan))
        lines.extend(self._edge_lines(plan))
        return "\n".join(lines)

    def _header(self) -> List[str]:
        return [
            "flowchart TD",
            "    classDef pending fill:#f0f0f0",
            "    classDef running fill:#fff4cc",
            "    classDef completed fill:#ccffcc",
            "    classDef failed fill:#ffcccc",
            "    classDef skipped fill:#e6e6fa",
        ]

    def _node_lines(self, plan: DAGPlan) -> List[str]:
        return [self._render_node(n) for n in plan.nodes.values()]

    def _render_node(self, node: DAGNode) -> str:
        return f'    {node.id}["{node.name}"]:::{self._style(node.status)}'

    def _style(self, status: DAGNodeStatus) -> str:
        return self._STYLES.get(status, "pending")

    def _edge_lines(self, plan: DAGPlan) -> List[str]:
        lines: List[str] = []
        for node in plan.nodes.values():
            lines.extend(self._render_edges(node))
        return lines

    def _render_edges(self, node: DAGNode) -> List[str]:
        return [f"    {dep} --> {node.id}" for dep in node.dependencies]


class DotDAGRenderer(DAGRenderer):
    """Graphviz DOT渲染器"""

    _COLORS: Dict[DAGNodeStatus, str] = {
        DAGNodeStatus.PENDING: "gray",
        DAGNodeStatus.RUNNING: "orange",
        DAGNodeStatus.COMPLETED: "green",
        DAGNodeStatus.FAILED: "red",
        DAGNodeStatus.SKIPPED: "purple",
    }

    def render(self, plan: DAGPlan) -> str:
        lines = ["digraph G {"]
        lines.extend(self._node_lines(plan))
        lines.extend(self._edge_lines(plan))
        lines.append("}")
        return "\n".join(lines)

    def _node_lines(self, plan: DAGPlan) -> List[str]:
        return [self._render_node(n) for n in plan.nodes.values()]

    def _render_node(self, node: DAGNode) -> str:
        color = self._color(node.status)
        return f'    "{node.id}" [label="{node.name}", color="{color}"]'

    def _color(self, status: DAGNodeStatus) -> str:
        return self._COLORS.get(status, "gray")

    def _edge_lines(self, plan: DAGPlan) -> List[str]:
        lines: List[str] = []
        for node in plan.nodes.values():
            lines.extend(self._render_edges(node))
        return lines

    def _render_edges(self, node: DAGNode) -> List[str]:
        return [f'    "{dep}" -> "{node.id}"' for dep in node.dependencies]


class TextDAGRenderer(DAGRenderer):
    """纯文本渲染器"""

    def render(self, plan: DAGPlan) -> str:
        lines = [f"DAG: {plan.description}"]
        lines.extend(self._node_lines(plan))
        return "\n".join(lines)

    def _node_lines(self, plan: DAGPlan) -> List[str]:
        return [self._render_node(n) for n in plan.nodes.values()]

    def _render_node(self, node: DAGNode) -> str:
        deps = ", ".join(sorted(node.dependencies)) or "none"
        return f"  [{node.status.value}] {node.name} deps={deps}"


@dataclass
class DAGExecutionEvent:
    """DAG执行事件"""

    timestamp: float
    node_id: str
    node_name: str
    event_type: str
    status: Optional[str] = None
    duration: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "event_type": self.event_type,
            "status": self.status,
            "duration": self.duration,
        }


class DAGMonitor:
    """DAG执行监控器

    第一性原理：任何执行过程都必须留下可观测的痕迹
    """

    def __init__(self) -> None:
        self._events: List[DAGExecutionEvent] = []
        self._lock = threading.Lock()

    def record_start(self, node: DAGNode) -> None:
        event = self._make_event(node, "start")
        self._append(event)

    def record_complete(self, node: DAGNode) -> None:
        event = self._make_event(
            node, "complete", node.status.value, node.duration
        )
        self._append(event)

    def _make_event(
        self,
        node: DAGNode,
        event_type: str,
        status: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> DAGExecutionEvent:
        return DAGExecutionEvent(
            timestamp=time.time(),
            node_id=node.id,
            node_name=node.name,
            event_type=event_type,
            status=status,
            duration=duration,
        )

    def _append(self, event: DAGExecutionEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get_events(self) -> List[DAGExecutionEvent]:
        with self._lock:
            return list(self._events)

    def snapshot(self, plan: DAGPlan) -> Dict[str, Any]:
        return {
            "plan_id": plan.id,
            "events": [e.to_dict() for e in self.get_events()],
            "nodes": plan.to_dict()["nodes"],
        }

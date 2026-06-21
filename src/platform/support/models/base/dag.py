"""
DAG（有向无环图）任务规划模型

第一性原理：复杂任务必须可分解为有序的子任务序列
- 节点：子任务
- 边：依赖关系
- 拓扑排序：确定执行顺序
- 并行执行：无依赖的任务可并发

类比：生物的"复杂行为序列"——做饭需要先洗菜、再切菜、最后炒菜
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Callable
from enum import Enum
import uuid
import time


class DAGNodeStatus(Enum):
    """DAG节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    """DAG节点"""
    id: str
    name: str
    action: str
    plugin_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)
    status: DAGNodeStatus = DAGNodeStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        if self.start_time == 0.0:
            return 0.0
        end = self.end_time if self.end_time > 0.0 else time.time()
        return end - self.start_time


@dataclass
class DAGPlan:
    """DAG执行计划"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    nodes: Dict[str, DAGNode] = field(default_factory=dict)
    edges: Dict[str, Set[str]] = field(default_factory=dict)
    description: str = ""

    def add_node(self, node: DAGNode) -> None:
        """添加节点"""
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = set()
        for dep in node.dependencies:
            if dep in self.edges:
                self.edges[dep].add(node.id)

    def get_ready_nodes(self) -> List[DAGNode]:
        """获取可执行的节点（依赖已完成）"""
        ready = []
        for node in self.nodes.values():
            if node.status != DAGNodeStatus.PENDING:
                continue
            deps_satisfied = all(
                self.nodes[d].status == DAGNodeStatus.COMPLETED
                for d in node.dependencies
                if d in self.nodes
            )
            if deps_satisfied:
                ready.append(node)
        return ready

    def is_complete(self) -> bool:
        """检查是否全部完成"""
        return all(
            n.status in (DAGNodeStatus.COMPLETED, DAGNodeStatus.SKIPPED, DAGNodeStatus.FAILED)
            for n in self.nodes.values()
        )

    def get_execution_order(self) -> List[str]:
        """拓扑排序获取执行顺序"""
        in_degree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in self.nodes:
                    in_degree[node.id] += 1
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for next_id in self.edges.get(nid, set()):
                in_degree[next_id] -= 1
                if in_degree[next_id] == 0:
                    queue.append(next_id)
        return order

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "description": self.description,
            "nodes": {
                nid: {
                    "name": n.name,
                    "status": n.status.value,
                    "dependencies": list(n.dependencies),
                    "duration": n.duration,
                }
                for nid, n in self.nodes.items()
            },
        }

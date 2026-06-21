"""
多Agent协作协调器

第一性原理：复杂问题需要分工协作，每个Agent专注特定驱力维度
类比：生物的"细胞分化"——不同细胞承担不同功能，协同维持生命体
"""

import uuid
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from ...support.models.base.state import EnvironmentState, GapState, DriveWeights
from ...support.models.base.task import Task, TaskPool, TaskResult


logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent角色"""
    SAFETY = "safety"      # 安全守护Agent
    GAIN = "gain"          # 收益优化Agent
    EFFICIENCY = "efficiency"  # 能效优化Agent
    EXPLORATION = "exploration"  # 探索Agent
    COORDINATOR = "coordinator"  # 协调Agent


@dataclass
class AgentIdentity:
    """Agent身份标识"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    role: AgentRole = AgentRole.COORDINATOR
    capabilities: List[str] = field(default_factory=list)
    registered_at: float = field(default_factory=time.time)


@dataclass
class TaskAssignment:
    """任务分配记录"""
    task_id: str = ""
    agent_id: str = ""
    assigned_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[TaskResult] = None


class AgentCoordinatorBase(ABC):
    """Agent协调器抽象基类"""

    @abstractmethod
    def register_agent(self, identity: AgentIdentity) -> bool:
        """注册Agent"""
        pass

    @abstractmethod
    def distribute_task(self, task: Task, gaps: GapState) -> Optional[str]:
        """分发任务给合适的Agent"""
        pass


class AgentCoordinator(AgentCoordinatorBase):
    """
    多Agent协作协调器

    职责：
    1. Agent注册与发现
    2. 任务分发（基于缺口匹配）
    3. 结果聚合
    4. 负载均衡

    第一性原理：
    - 每个Agent专注一个驱力维度
    - 任务必须分配给最匹配的Agent
    - 协调器本身不执行任务，只负责调度
    """

    ROLE_PRIORITY = {
        AgentRole.SAFETY: 0,
        AgentRole.GAIN: 1,
        AgentRole.EFFICIENCY: 2,
        AgentRole.EXPLORATION: 3,
        AgentRole.COORDINATOR: 4,
    }

    def __init__(self) -> None:
        self.agents: Dict[str, AgentIdentity] = {}
        self.agent_pools: Dict[str, TaskPool] = {}
        self.assignments: List[TaskAssignment] = []
        self.task_callbacks: Dict[str, Callable] = {}
        self.stats = {
            "tasks_distributed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
        }
        logger.info("AgentCoordinator initialized")

    def register_agent(self, identity: AgentIdentity) -> bool:
        """注册Agent到协调器"""
        if identity.id in self.agents:
            logger.warning(f"Agent {identity.id} already registered")
            return False
        self.agents[identity.id] = identity
        self.agent_pools[identity.id] = TaskPool(max_size=100)
        logger.info(f"Agent registered: {identity.name} ({identity.role.value})")
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        if agent_id not in self.agents:
            return False
        del self.agents[agent_id]
        del self.agent_pools[agent_id]
        logger.info(f"Agent unregistered: {agent_id}")
        return True

    def _find_best_agent(self, task: Task, gaps: GapState) -> Optional[str]:
        """找到最适合执行任务的Agent"""
        candidates = self._collect_candidates(task, gaps)
        if not candidates:
            return None
        return self._select_top_candidate(candidates)

    def _is_eligible(self, identity: AgentIdentity) -> bool:
        """判断Agent是否可参与任务分配"""
        return identity.role != AgentRole.COORDINATOR

    def _collect_candidates(self, task: Task, gaps: GapState) -> List[Tuple[str, float]]:
        candidates: List[Tuple[str, float]] = []
        for agent_id, identity in self.agents.items():
            if not self._is_eligible(identity):
                continue
            score = self._compute_match_score(task, identity, gaps)
            if score > 0:
                candidates.append((agent_id, score))
        return candidates

    def _select_top_candidate(self, candidates: List[Tuple[str, float]]) -> Optional[str]:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _compute_match_score(self, task: Task, identity: AgentIdentity, gaps: GapState) -> float:
        """计算任务与Agent的匹配分数"""
        role_match = self._role_match_score(task, identity.role)
        gap_match = self._gap_match_score(identity.role, gaps)
        load_penalty = self._load_penalty(identity.id)
        return role_match * 0.4 + gap_match * 0.4 - load_penalty * 0.2

    def _role_match_score(self, task: Task, role: AgentRole) -> float:
        """角色匹配分数"""
        role_map = {
            "safe": AgentRole.SAFETY,
            "gain": AgentRole.GAIN,
            "eff": AgentRole.EFFICIENCY,
        }
        expected_role = role_map.get(task.target_drive, AgentRole.EXPLORATION)
        return 1.0 if role == expected_role else 0.3

    def _gap_match_score(self, role: AgentRole, gaps: GapState) -> float:
        """缺口匹配分数"""
        if role == AgentRole.SAFETY:
            return gaps.safety
        elif role == AgentRole.GAIN:
            return gaps.gain
        elif role == AgentRole.EFFICIENCY:
            return gaps.efficiency
        return 0.5

    def _load_penalty(self, agent_id: str) -> float:
        """负载惩罚"""
        pool = self.agent_pools.get(agent_id)
        if not pool:
            return 0.0
        return min(1.0, pool.size / 100.0)

    def _resolve_agent(self, task: Task, gaps: GapState) -> Optional[str]:
        """解析目标Agent"""
        agent_id = self._find_best_agent(task, gaps)
        if agent_id is None:
            return self._handle_no_agent(task)
        return agent_id

    def distribute_task(self, task: Task, gaps: GapState) -> Optional[str]:
        """
        分发任务给最合适的Agent

        策略：
        1. 根据任务目标驱力匹配Agent角色
        2. 考虑当前缺口大小
        3. 考虑Agent当前负载
        """
        agent_id = self._resolve_agent(task, gaps)
        if agent_id is None:
            return None
        self._assign_task(task, agent_id)
        return agent_id

    def _handle_no_agent(self, task: Task) -> None:
        logger.warning(f"No suitable agent for task: {task.name}")
        return None

    def _assign_task(self, task: Task, agent_id: str) -> None:
        pool = self.agent_pools[agent_id]
        pool.add_task(task)
        self.assignments.append(TaskAssignment(
            task_id=task.id,
            agent_id=agent_id,
        ))
        self.stats["tasks_distributed"] += 1
        logger.info(f"Task {task.name} distributed to agent {agent_id}")

    def _update_assignment(self, assignment: TaskAssignment, result: TaskResult) -> None:
        """更新任务分配记录"""
        assignment.result = result
        assignment.completed_at = time.time()
        if result.success:
            self.stats["tasks_completed"] += 1
        else:
            self.stats["tasks_failed"] += 1

    def report_result(self, task_id: str, result: TaskResult) -> None:
        """报告任务执行结果"""
        for assignment in self.assignments:
            if assignment.task_id == task_id:
                self._update_assignment(assignment, result)
                break

    def _gather_agent_assignments(self, agent_id: str) -> Tuple[List[TaskAssignment], List[TaskAssignment]]:
        """收集Agent的任务分配记录"""
        agent_assignments = [a for a in self.assignments if a.agent_id == agent_id]
        completed = [a for a in agent_assignments if a.completed_at is not None]
        return agent_assignments, completed

    def get_agent_stats(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取Agent统计"""
        if agent_id not in self.agents:
            return None
        identity = self.agents[agent_id]
        pool = self.agent_pools[agent_id]
        agent_assignments, completed = self._gather_agent_assignments(agent_id)
        return {
            "agent_id": agent_id,
            "name": identity.name,
            "role": identity.role.value,
            "pending_tasks": pool.size,
            "total_assigned": len(agent_assignments),
            "total_completed": len(completed),
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        return {
            "coordinator_stats": self.stats.copy(),
            "agent_count": len(self.agents),
            "agents": {
                agent_id: self.get_agent_stats(agent_id)
                for agent_id in self.agents
            },
        }

    def get_pending_tasks(self, agent_id: str) -> List[Task]:
        """获取Agent的待处理任务"""
        pool = self.agent_pools.get(agent_id)
        if pool:
            return pool.get_pending_tasks()
        return []

    def broadcast_task(self, task: Task) -> List[str]:
        """广播任务给所有Agent"""
        assigned = []
        for agent_id in self.agents:
            if self.agents[agent_id].role == AgentRole.COORDINATOR:
                continue
            pool = self.agent_pools[agent_id]
            pool.add_task(task)
            assigned.append(agent_id)
        return assigned


@dataclass
class AgentHeartbeat:
    """Agent心跳记录"""
    agent_id: str
    timestamp: float
    status: str = "alive"


class AgentHealthMonitor:
    """
    Agent健康监控器

    第一性原理：协作系统必须感知成员存活状态
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.heartbeats: Dict[str, AgentHeartbeat] = {}

    def record_heartbeat(self, agent_id: str) -> None:
        """记录心跳"""
        self.heartbeats[agent_id] = AgentHeartbeat(
            agent_id=agent_id, timestamp=time.time()
        )

    def is_alive(self, agent_id: str) -> bool:
        """检查Agent是否存活"""
        if agent_id not in self.heartbeats:
            return False
        elapsed = time.time() - self.heartbeats[agent_id].timestamp
        return elapsed < self.timeout_seconds

    def get_dead_agents(self) -> List[str]:
        """获取失效Agent列表"""
        return [aid for aid in self.heartbeats if not self.is_alive(aid)]

    def get_stats(self) -> Dict[str, Any]:
        """获取健康统计"""
        total = len(self.heartbeats)
        alive = sum(1 for aid in self.heartbeats if self.is_alive(aid))
        return {"total": total, "alive": alive, "dead": total - alive}


class ConsensusVoter:
    """
    协作共识投票器

    第一性原理：重大决策需要多Agent共识，避免单点错误
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.votes: Dict[str, List[str]] = {}

    def cast_vote(self, proposal_id: str, agent_id: str, approve: bool) -> None:
        """投票"""
        if proposal_id not in self.votes:
            self.votes[proposal_id] = {"yes": [], "no": []}
        key = "yes" if approve else "no"
        if agent_id not in self.votes[proposal_id][key]:
            self.votes[proposal_id][key].append(agent_id)

    def is_approved(self, proposal_id: str, total_agents: int) -> bool:
        """检查提案是否通过"""
        if proposal_id not in self.votes:
            return False
        yes_count = len(self.votes[proposal_id]["yes"])
        return (yes_count / total_agents) >= self.threshold

    def get_result(self, proposal_id: str) -> Dict[str, Any]:
        """获取投票结果"""
        if proposal_id not in self.votes:
            return {"yes": 0, "no": 0}
        return {
            "yes": len(self.votes[proposal_id]["yes"]),
            "no": len(self.votes[proposal_id]["no"]),
        }

    def reset(self, proposal_id: str) -> None:
        """重置投票"""
        if proposal_id in self.votes:
            del self.votes[proposal_id]

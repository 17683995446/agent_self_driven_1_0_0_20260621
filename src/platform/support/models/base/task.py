"""
任务模型定义

第一性原理：任务是系统行为的原子单元，必须有明确的生命周期
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import time
import uuid


class TaskStatus(Enum):
    """任务状态"""
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0   # 安全相关，必须立即执行
    HIGH = 1       # 重要任务
    NORMAL = 2     # 普通任务
    LOW = 3        # 低优先级
    EXPLORATION = 4  # 探索任务


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool = False
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    resource_usage: Dict[str, float] = field(default_factory=dict)


@dataclass
class Task:
    """
    任务 —— 系统行为的原子单元
    
    第一性原理：任务 = (目标状态, 当前状态, 行为策略, 预期效果)
    任务必须有明确的：
    1. 目标：缩小哪个缺口
    2. 约束：资源限制、时间限制
    3. 评估：成功/失败标准
    
    类比：生物的"行为意图"——如捕食、逃跑、休息等
    """
    
    # 基本标识
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "unnamed_task"
    description: str = ""
    
    # 目标定义
    target_drive: str = "safe"  # "safe" | "gain" | "eff"
    target_gap_reduction: float = 0.1  # 预期缩小的缺口量 [0, 1]
    
    # 优先级
    priority: TaskPriority = TaskPriority.NORMAL
    
    # 约束定义
    max_cpu_usage: float = 0.05  # 任务执行时最大CPU使用
    max_memory_usage: float = 0.05  # 任务执行时最大内存使用
    max_duration: float = 60.0  # 最大执行时间（秒）
    deadline: float = 0.0  # 绝对截止时间（时间戳），0表示无限制
    
    # 执行函数
    execute_fn: Optional[Callable[[], TaskResult]] = None
    
    # 状态管理
    status: TaskStatus = TaskStatus.CREATED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 历史记录
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_reward: float = 0.0
    
    # 探索标记
    is_exploration: bool = False  # 是否是探索任务
    novelty_score: float = 0.0  # 新颖性分数
    
    def __post_init__(self) -> None:
        if self.deadline == 0:
            self.deadline = time.time() + 3600  # 默认1小时过期

    @property
    def success_rate(self) -> float:
        """历史成功率"""
        if self.execution_count == 0:
            return 0.5  # 默认值
        return self.success_count / self.execution_count
    
    @property
    def average_reward(self) -> float:
        """平均奖励"""
        if self.execution_count == 0:
            return 0.0
        return self.total_reward / self.execution_count
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return time.time() > self.deadline
    
    @property
    def duration(self) -> float:
        """执行时长"""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at
    
    def start(self) -> None:
        """开始执行"""
        self.status = TaskStatus.RUNNING
        self.started_at = time.time()
        self.execution_count += 1

    def complete(self, result: TaskResult) -> None:
        """完成执行"""
        self.completed_at = time.time()
        if result.success:
            self.status = TaskStatus.COMPLETED
            self.success_count += 1
        else:
            self.status = TaskStatus.FAILED
            self.failure_count += 1

    def cancel(self) -> None:
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "target_drive": self.target_drive,
            "priority": self.priority.name,
            "status": self.status.value,
            "success_rate": self.success_rate,
            "execution_count": self.execution_count,
            "is_exploration": self.is_exploration,
        }


@dataclass
class TaskPool:
    """
    任务池 —— 动态生成和管理任务
    
    第一性原理：任务池是系统的"行为 repertoire"，
    必须动态刷新、动态淘汰、动态新增
    """
    max_size: int = 100
    tasks: Dict[str, Task] = field(default_factory=dict)
    execution_history: List[Task] = field(default_factory=list)
    
    def add_task(self, task: Task) -> bool:
        """添加任务"""
        if len(self.tasks) >= self.max_size:
            # 淘汰最低价值的任务
            self._evict_lowest_value()
        
        self.tasks[task.id] = task
        return True
    
    def remove_task(self, task_id: str) -> None:
        """移除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[Task]:
        """获取待执行的任务"""
        return [t for t in self.tasks.values() 
                if t.status in [TaskStatus.CREATED, TaskStatus.PENDING]]
    
    def get_tasks_by_drive(self, drive: str) -> List[Task]:
        """按驱力类型获取任务"""
        return [t for t in self.tasks.values() if t.target_drive == drive]
    
    def record_execution(self, task: Task) -> None:
        """记录执行历史"""
        self.execution_history.append(task)
        # 只保留最近1000条
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

    def _find_lowest_value_task(self) -> Task:
        """查找最低价值任务"""
        # 计算每个任务的价值分数
        def value_score(task: Task) -> float:
            return (task.average_reward * 0.4 + 
                    task.success_rate * 0.3 + 
                    (1.0 if task.is_exploration else 0.0) * 0.3)
        
        return min(self.tasks.values(), key=value_score)

    def _evict_lowest_value(self):
        """淘汰最低价值的任务"""
        if not self.tasks:
            return
        
        lowest_task = self._find_lowest_value_task()
        del self.tasks[lowest_task.id]
    
    @property
    def size(self) -> int:
        """当前任务数"""
        return len(self.tasks)
    
    def clear_completed(self) -> None:
        """清理已完成的任务"""
        completed_ids = [tid for tid, t in self.tasks.items()
                        if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED,
                                       TaskStatus.CANCELLED, TaskStatus.EXPIRED]]
        for tid in completed_ids:
            del self.tasks[tid]

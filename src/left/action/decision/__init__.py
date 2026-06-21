"""
决策引擎

系统的"前额叶皮层"，负责自主决策。

核心功能：
1. 评估候选任务
2. 选择最优任务
3. 平衡探索与利用
4. 处理任务中断

第一性原理：
- 决策必须完全自主
- 评分机制必须透明
- 探索利用必须平衡
- 高优先级可中断低优先级

算法保证：
- UCB算法保证渐进最优
- 任务评分满足传递性
- 中断机制保证响应性

性能保证：
- 单次决策 < 10ms
- 支持1000+任务实时排序
"""

from .task_lifecycle import TaskLifecycle, InvalidTransitionError
from .task_scorer import StandardTaskScorer
from .exploration_policy import UCBExplorationPolicy, EpsilonGreedyPolicy
from .task_interrupt import TaskInterruptHandler
from .decision_audit import DecisionAuditLog
from .task_dependency import StandardTaskDependencyManager
from .task_resource_budget import TaskResourceBudget

__all__ = [
    "TaskLifecycle",
    "InvalidTransitionError",
    "StandardTaskScorer",
    "UCBExplorationPolicy",
    "EpsilonGreedyPolicy",
    "TaskInterruptHandler",
    "DecisionAuditLog",
    "StandardTaskDependencyManager",
    "TaskResourceBudget",
]

"""
任务DAG动态分解器

第一性原理：复杂任务必须可分解为可管理、可追踪、可并行的子任务
- 识别：判断任务是否需要分解
- 分解：将复杂任务拆分为DAG节点
- 验证：确保分解结果无循环依赖、可执行

类比：生物的"目标分解"——"捕食"分解为"靠近、伏击、追逐、捕获"
"""

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any

from ....platform.support.models.base.task import Task
from ....platform.support.models.base.dag import DAGNode, DAGPlan


class TaskDecomposer(ABC):
    """任务分解器抽象基类"""

    @abstractmethod
    def can_decompose(self, task: Task) -> bool:
        """判断是否能分解该任务"""
        pass

    @abstractmethod
    def decompose(self, task: Task) -> DAGPlan:
        """将任务分解为DAG计划"""
        pass


@dataclass
class DecompositionRule:
    """分解规则"""
    name: str
    pattern: str
    builder: Callable[[Task], DAGPlan]


@dataclass
class SubTaskSpec:
    """子任务规格"""
    name: str
    plugin_name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


class RuleBasedTaskDecomposer(TaskDecomposer):
    """
    基于规则的动态分解器

    通过正则模式匹配任务描述，选择预定义的分解模板
    """

    def __init__(self) -> None:
        self._rules: List[DecompositionRule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """注册默认分解规则"""
        self._rules.extend([
            self._build_fetch_analyze_rule(),
            self._build_file_process_rule(),
        ])

    def _build_fetch_analyze_rule(self) -> DecompositionRule:
        """构建获取-分析规则"""
        return DecompositionRule(
            name="fetch_and_analyze",
            pattern=r"fetch.*then.*analyze|获取.*分析|query.*summarize",
            builder=self._build_fetch_analyze_plan,
        )

    def _build_file_process_rule(self) -> DecompositionRule:
        """构建文件处理规则"""
        return DecompositionRule(
            name="file_process",
            pattern=r"read.*file.*write|文件.*处理|parse.*save",
            builder=self._build_file_process_plan,
        )

    def can_decompose(self, task: Task) -> bool:
        """判断是否能分解"""
        return self._match_rule(task) is not None

    def _match_rule(self, task: Task) -> Optional[DecompositionRule]:
        """匹配分解规则"""
        text = self._task_text(task)
        for rule in self._rules:
            if re.search(rule.pattern, text, re.IGNORECASE):
                return rule
        return None

    def _task_text(self, task: Task) -> str:
        """获取任务文本"""
        return f"{task.name} {task.description}".lower()

    def decompose(self, task: Task) -> DAGPlan:
        """分解任务"""
        rule = self._match_rule(task)
        if rule is None:
            return self._build_single_node_plan(task)
        return rule.builder(task)

    def _build_single_node_plan(self, task: Task) -> DAGPlan:
        """构建单节点计划"""
        node = self._build_node_from_task(task)
        plan = DAGPlan(description=task.description)
        plan.add_node(node)
        return plan

    def _build_node_from_task(self, task: Task) -> DAGNode:
        """从任务构建DAG节点"""
        params = dict(task.params) if hasattr(task, "params") else {}
        return DAGNode(
            id=self._generate_node_id(),
            name=task.name,
            action="execute",
            plugin_name="tool_plugin",
            params=params,
        )

    def _generate_node_id(self) -> str:
        """生成节点ID"""
        return f"node_{uuid.uuid4().hex[:8]}"

    def _build_fetch_analyze_plan(self, task: Task) -> DAGPlan:
        """构建获取-分析计划"""
        params = self._extract_params(task)
        fetch_node = self._build_spec_node(
            "fetch_data", "http_plugin", "get", params.get("fetch", {})
        )
        analyze_node = self._build_spec_node(
            "analyze_data", "llm_plugin", "summarize",
            {"text": params.get("analyze_text", "")},
            dependencies=[fetch_node.id],
        )
        return self._build_plan_from_specs(task.description, [fetch_node, analyze_node])

    def _build_file_process_plan(self, task: Task) -> DAGPlan:
        """构建文件处理计划"""
        params = self._extract_params(task)
        read_node = self._build_spec_node(
            "read_file", "file_plugin", "read", params.get("read", {})
        )
        process_node = self._build_spec_node(
            "process_content", "llm_plugin", "extract",
            {"text": params.get("content", ""), "schema": params.get("schema", {})},
            dependencies=[read_node.id],
        )
        write_node = self._build_spec_node(
            "write_result", "file_plugin", "write",
            params.get("write", {}),
            dependencies=[process_node.id],
        )
        return self._build_plan_from_specs(task.description, [read_node, process_node, write_node])

    def _build_spec_node(
        self,
        name: str,
        plugin_name: str,
        action: str,
        params: Dict[str, Any],
        dependencies: Optional[List[str]] = None,
    ) -> DAGNode:
        """从规格构建节点"""
        return DAGNode(
            id=self._generate_node_id(),
            name=name,
            action=action,
            plugin_name=plugin_name,
            params=params,
            dependencies=set(dependencies or []),
        )

    def _build_plan_from_specs(self, description: str, nodes: List[DAGNode]) -> DAGPlan:
        """从节点列表构建计划"""
        plan = DAGPlan(description=description)
        for node in nodes:
            plan.add_node(node)
        return plan

    def _extract_params(self, task: Task) -> Dict[str, Any]:
        """提取任务参数"""
        if hasattr(task, "params"):
            return dict(task.params)
        return {}


class DecompositionValidator:
    """
    分解结果验证器

    第一性原理：分解必须保持正确性，不能引入循环依赖或孤立节点
    """

    def __init__(self) -> None:
        self._errors: List[str] = []

    def validate(self, plan: DAGPlan) -> bool:
        """验证计划是否合法"""
        self._errors = []
        self._check_empty(plan)
        self._check_dangling_deps(plan)
        if self._errors:
            return False
        self._check_cycle(plan)
        return len(self._errors) == 0

    def get_errors(self) -> List[str]:
        """获取验证错误"""
        return self._errors

    def _check_empty(self, plan: DAGPlan) -> None:
        if not plan.nodes:
            self._errors.append("plan has no nodes")

    def _check_dangling_deps(self, plan: DAGPlan) -> None:
        node_ids = set(plan.nodes.keys())
        for node in plan.nodes.values():
            for dep in node.dependencies:
                if dep not in node_ids:
                    self._errors.append(f"node {node.id} depends on missing node {dep}")

    def _check_cycle(self, plan: DAGPlan) -> None:
        if self._has_cycle(plan):
            self._errors.append("cycle detected in DAG")

    def _has_cycle(self, plan: DAGPlan) -> bool:
        """检测循环依赖"""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        for nid in plan.nodes:
            if self._cycle_dfs(plan, nid, visited, rec_stack):
                return True
        return False

    def _cycle_dfs(
        self,
        plan: DAGPlan,
        nid: str,
        visited: Set[str],
        rec_stack: Set[str],
    ) -> bool:
        """DFS循环检测"""
        visited.add(nid)
        rec_stack.add(nid)
        for dep in plan.nodes[nid].dependencies:
            if dep not in visited:
                if self._cycle_dfs(plan, dep, visited, rec_stack):
                    return True
            elif dep in rec_stack:
                return True
        rec_stack.discard(nid)
        return False


class CompositeTaskDecomposer(TaskDecomposer):
    """
    组合分解器

    第一性原理：不同复杂任务需要不同分解策略
    按优先级尝试多个分解器，直到找到能处理的任务
    """

    def __init__(self, decomposers: List[TaskDecomposer]) -> None:
        self.decomposers = decomposers
        self.validator = DecompositionValidator()

    def can_decompose(self, task: Task) -> bool:
        """是否有分解器能处理"""
        return any(d.can_decompose(task) for d in self.decomposers)

    def decompose(self, task: Task) -> DAGPlan:
        """使用第一个匹配的分解器"""
        for decomposer in self.decomposers:
            if decomposer.can_decompose(task):
                plan = decomposer.decompose(task)
                return self._validate_or_single(plan, task)
        return self._build_single_node_plan(task)

    def _validate_or_single(self, plan: DAGPlan, task: Task) -> DAGPlan:
        """验证计划，失败则返回单节点"""
        if self.validator.validate(plan):
            return plan
        return self._build_single_node_plan(task)

    def _build_single_node_plan(self, task: Task) -> DAGPlan:
        """构建单节点计划"""
        node = DAGNode(
            id=f"node_{uuid.uuid4().hex[:8]}",
            name=task.name,
            action="execute",
            plugin_name="tool_plugin",
        )
        plan = DAGPlan(description=task.description)
        plan.add_node(node)
        return plan

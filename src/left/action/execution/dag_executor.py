"""
DAG执行器

第一性原理：复杂任务必须按依赖顺序执行，支持并行
- 拓扑排序：确定执行顺序
- 并行执行：无依赖任务并发
- 结果传递：上游结果传递给下游
- 失败处理：支持失败重试和跳过
- 可观测：集成监控，记录执行事件

类比：生物的"行为编排"——跳舞需要手脚协调，按节拍执行
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional, Any

from ....platform.support.models.base.dag import DAGPlan, DAGNode, DAGNodeStatus
from ....platform.support.models.base.plugin import PluginResult
from ....platform.lifecycle.memory.plugin_manager import PluginManager
from .dag_visualizer import DAGMonitor


logger = logging.getLogger(__name__)


class DAGExecutor:
    """
    DAG执行器

    执行DAG计划，支持并行、结果传递和执行监控
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        max_workers: int = 4,
        monitor: Optional[DAGMonitor] = None,
    ) -> None:
        self.plugin_manager = plugin_manager
        self.max_workers = max_workers
        self.monitor = monitor
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running_futures: Dict[str, Future] = {}

    def execute(self, plan: DAGPlan) -> Dict[str, Any]:
        """执行DAG计划"""
        logger.info(f"Executing DAG plan: {plan.id}")
        start_time = time.time()
        self._run_until_complete(plan)
        self._cleanup_futures()
        return self._build_result(plan, time.time() - start_time)

    def _run_until_complete(self, plan: DAGPlan) -> None:
        while not plan.is_complete():
            if not self._run_cycle(plan):
                break

    def _run_cycle(self, plan: DAGPlan) -> bool:
        ready = plan.get_ready_nodes()
        if not ready:
            return self._wait_or_stop(plan)
        self._launch_ready(ready, plan)
        self._wait_any()
        return True

    def _wait_or_stop(self, plan: DAGPlan) -> bool:
        if not self._running_futures:
            return False
        self._wait_any()
        return True

    def _launch_ready(self, ready: List[DAGNode], plan: DAGPlan) -> None:
        """启动就绪节点"""
        for node in ready:
            self._launch_node(node, plan)

    def _launch_node(self, node: DAGNode, plan: DAGPlan) -> None:
        """启动单个节点"""
        node.status = DAGNodeStatus.RUNNING
        node.start_time = time.time()
        self._notify_start(node)
        future = self._executor.submit(self._run_node, node, plan)
        self._running_futures[node.id] = future
        logger.info(f"Launched node: {node.name}")

    def _run_node(self, node: DAGNode, plan: DAGPlan) -> None:
        """运行节点"""
        try:
            self._execute_node(node, plan)
        except Exception as e:
            self._mark_failed(node, str(e))
            logger.error(f"Node {node.name} failed: {e}")
        finally:
            self._finish_node(node)

    def _execute_node(self, node: DAGNode, plan: DAGPlan) -> None:
        params = self._resolve_refs(node.params, plan)
        result = self.plugin_manager.execute(
            node.plugin_name, node.action, params
        )
        node.result = result
        node.status = self._node_status(result)
        node.error = None if result.success else result.message

    def _node_status(self, result: PluginResult) -> DAGNodeStatus:
        if result.success:
            return DAGNodeStatus.COMPLETED
        return DAGNodeStatus.FAILED

    def _mark_failed(self, node: DAGNode, message: str) -> None:
        node.status = DAGNodeStatus.FAILED
        node.error = message

    def _finish_node(self, node: DAGNode) -> None:
        node.end_time = time.time()
        self._notify_complete(node)

    def _notify_start(self, node: DAGNode) -> None:
        if self.monitor is not None:
            self.monitor.record_start(node)

    def _notify_complete(self, node: DAGNode) -> None:
        if self.monitor is not None:
            self.monitor.record_complete(node)

    def _resolve_refs(self, params: Dict[str, Any], plan: DAGPlan) -> Dict[str, Any]:
        """解析参数中的结果引用"""
        resolved: Dict[str, Any] = {}
        for key, value in params.items():
            resolved[key] = self._resolve_value(value, plan)
        return resolved

    def _resolve_value(self, value: Any, plan: DAGPlan) -> Any:
        """解析单个值"""
        if isinstance(value, dict) and "$ref" in value:
            return self._fetch_ref(value["$ref"], plan)
        return value

    def _fetch_ref(self, ref: str, plan: DAGPlan) -> Any:
        """获取引用值"""
        parts = ref.split(".")
        node_id = parts[0]
        node = plan.nodes.get(node_id)
        if node is None or node.result is None:
            return None
        return self._traverse_ref(node.result.data, parts[1:])

    def _traverse_ref(self, data: Dict[str, Any], path: List[str]) -> Any:
        """遍历引用路径"""
        current: Any = data
        for part in path:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _wait_any(self) -> None:
        """等待任意一个任务完成"""
        if not self._running_futures:
            return
        done = [fid for fid, f in self._running_futures.items() if f.done()]
        for fid in done:
            del self._running_futures[fid]
        if not done:
            time.sleep(0.01)

    def _cleanup_futures(self) -> None:
        """清理所有future"""
        for future in self._running_futures.values():
            if not future.done():
                future.cancel()
        self._running_futures.clear()

    def _count_success(self, plan: DAGPlan) -> int:
        """统计成功节点数"""
        return sum(1 for n in plan.nodes.values() if n.status == DAGNodeStatus.COMPLETED)

    def _count_failed(self, plan: DAGPlan) -> int:
        """统计失败节点数"""
        return sum(1 for n in plan.nodes.values() if n.status == DAGNodeStatus.FAILED)

    def _build_result(self, plan: DAGPlan, duration: float) -> Dict[str, Any]:
        """构建执行结果"""
        success = self._count_success(plan)
        failed = self._count_failed(plan)
        return {
            "plan_id": plan.id,
            "duration": duration,
            "total_nodes": len(plan.nodes),
            "success": success,
            "failed": failed,
            "nodes": plan.to_dict()["nodes"],
        }

    def shutdown(self) -> None:
        """关闭执行器"""
        self._executor.shutdown(wait=True)
        logger.info("DAGExecutor shut down")

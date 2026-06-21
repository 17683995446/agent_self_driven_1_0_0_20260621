"""
任务执行器与并发控制

第一性原理：任务执行必须有边界控制，防止资源耗尽和级联故障
- 并发限制：同时执行的任务数有上限
- 超时控制：任务必须在限定时间内完成
- 资源隔离：任务执行不互相干扰
- 优雅取消：支持安全中断正在执行的任务

类比：生物的"运动皮层"——控制肌肉收缩的强度和时机，防止过度疲劳
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

from ....platform.support.models.base.task import Task, TaskResult, TaskStatus


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRecord:
    """执行记录"""
    task_id: str
    task_name: str
    status: ExecutionStatus
    start_time: float
    end_time: float = 0.0
    result: Optional[TaskResult] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time


class TaskExecutorBase(ABC):
    """任务执行器抽象基类"""

    @abstractmethod
    def submit(self, task: Task, timeout: Optional[float] = None) -> ExecutionRecord:
        """提交任务执行"""
        pass

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """取消正在执行的任务"""
        pass


class TaskExecutor(TaskExecutorBase):
    """
    任务执行器

    第一性原理：执行是决策的闭环，必须有边界控制
    - 线程池管理并发
    - 超时机制防止挂起
    - 资源使用追踪
    - 执行历史记录
    """

    def _init_pools(self, max_workers: int) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task_worker")
        self._running_tasks: Dict[str, Future] = {}
        self._running_lock = threading.Lock()

    def _init_history(self) -> None:
        self._history: List[ExecutionRecord] = []
        self._history_lock = threading.Lock()
        self._max_history = 1000

    def __init__(
        self,
        max_workers: int = 4,
        default_timeout: float = 60.0,
        max_queue_size: int = 100,
    ) -> None:
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.max_queue_size = max_queue_size
        self._init_pools(max_workers)
        self._init_history()
        self._init_counters()
        logger.info(f"TaskExecutor initialized: max_workers={max_workers}, timeout={default_timeout}s")

    def _init_counters(self) -> None:
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_timeout = 0
        self.total_cancelled = 0

    def _create_failed_record(self, task: Task, error: str) -> ExecutionRecord:
        """创建失败记录"""
        now = time.time()
        return ExecutionRecord(
            task_id=task.id,
            task_name=task.name,
            status=ExecutionStatus.FAILED,
            start_time=now,
            end_time=now,
            error=error,
        )

    def _wrap_execute(self, task: Task) -> Callable[[], TaskResult]:
        """包装执行函数以捕获异常"""
        def wrapped_execute() -> TaskResult:
            try:
                return task.execute_fn()
            except Exception as e:
                logger.error(f"Task {task.name} execution error: {e}")
                return TaskResult(success=False, message=str(e))
        return wrapped_execute

    def _set_status_and_count(self, result: TaskResult) -> ExecutionStatus:
        if result.success:
            self.total_completed += 1
            return ExecutionStatus.COMPLETED
        self.total_failed += 1
        return ExecutionStatus.FAILED

    def _build_success_record(
        self, task: Task, start_time: float, end_time: float, result: TaskResult
    ) -> ExecutionRecord:
        """构建成功/失败的执行记录"""
        status = self._set_status_and_count(result)
        error = result.message or "Task failed" if not result.success else None
        return ExecutionRecord(
            task_id=task.id,
            task_name=task.name,
            status=status,
            start_time=start_time,
            end_time=end_time,
            result=result,
            error=error,
        )

    def _mark_timeout(self, task: Task, future: Future, timeout: float) -> None:
        future.cancel()
        self.total_timeout += 1
        task.status = TaskStatus.FAILED
        logger.warning(f"Task {task.name} timed out after {timeout}s")

    def _build_timeout_record(
        self, task: Task, future: Future, start_time: float, end_time: float, timeout: float
    ) -> ExecutionRecord:
        """构建超时执行记录"""
        self._mark_timeout(task, future, timeout)
        return ExecutionRecord(
            task_id=task.id,
            task_name=task.name,
            status=ExecutionStatus.TIMEOUT,
            start_time=start_time,
            end_time=end_time,
            error=f"Timeout after {timeout}s",
        )

    def _mark_exception(self, task: Task, exc: Exception) -> None:
        self.total_failed += 1
        task.status = TaskStatus.FAILED
        logger.error(f"Task {task.name} failed: {exc}")

    def _build_exception_record(
        self, task: Task, start_time: float, end_time: float, exc: Exception
    ) -> ExecutionRecord:
        """构建异常执行记录"""
        self._mark_exception(task, exc)
        return ExecutionRecord(
            task_id=task.id,
            task_name=task.name,
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=end_time,
            error=str(exc),
        )

    def _wait_success(self, task: Task, future: Future, start_time: float, end_time: float) -> ExecutionRecord:
        result = future.result(timeout=self.default_timeout)
        task.complete(result)
        return self._build_success_record(task, start_time, end_time, result)

    def _wait_timeout(self, task: Task, future: Future, start_time: float, end_time: float, timeout: float) -> ExecutionRecord:
        return self._build_timeout_record(task, future, start_time, end_time, timeout)

    def _wait_exception(self, task: Task, start_time: float, end_time: float, exc: Exception) -> ExecutionRecord:
        return self._build_exception_record(task, start_time, end_time, exc)

    def _wait_for_result(self, task: Task, future: Future, timeout: float) -> ExecutionRecord:
        """等待任务结果"""
        start_time = time.time()
        try:
            end_time = time.time()
            return self._wait_success(task, future, start_time, end_time)
        except FutureTimeoutError:
            end_time = time.time()
            return self._wait_timeout(task, future, start_time, end_time, timeout)
        except Exception as e:
            end_time = time.time()
            return self._wait_exception(task, start_time, end_time, e)

    def _check_concurrency(self, task: Task) -> None:
        """检查并发限制并记录警告"""
        with self._running_lock:
            if len(self._running_tasks) >= self.max_workers:
                logger.warning(f"Concurrency limit reached, queueing task {task.name}")

    def _submit_future(self, task: Task) -> Future:
        """提交任务到线程池并记录"""
        self.total_submitted += 1
        future = self._executor.submit(self._wrap_execute(task))
        with self._running_lock:
            self._running_tasks[task.id] = future
        return future

    def _cleanup_task(self, task: Task) -> None:
        """从运行任务中清理"""
        with self._running_lock:
            self._running_tasks.pop(task.id, None)

    def _reject_no_fn(self, task: Task) -> ExecutionRecord:
        record = self._create_failed_record(task, "No execute function defined")
        self._add_history(record)
        return record

    def _submit_and_wait(self, task: Task, timeout: float) -> ExecutionRecord:
        task.start()
        future = self._submit_future(task)
        record = self._wait_for_result(task, future, timeout)
        self._cleanup_task(task)
        return record

    def submit(self, task: Task, timeout: Optional[float] = None) -> ExecutionRecord:
        """
        提交任务执行

        Args:
            task: 要执行的任务
            timeout: 超时时间（秒），None使用默认值

        Returns:
            ExecutionRecord: 执行记录
        """
        if task.execute_fn is None:
            return self._reject_no_fn(task)
        self._check_concurrency(task)
        task_timeout = timeout or self.default_timeout
        record = self._submit_and_wait(task, task_timeout)
        self._add_history(record)
        return record

    def _do_cancel(self, future: Future, task_id: str) -> bool:
        cancelled = future.cancel()
        if cancelled:
            self.total_cancelled += 1
            logger.info(f"Task {task_id} cancelled")
        return cancelled

    def cancel_task(self, task_id: str) -> bool:
        """
        取消正在执行的任务

        Returns:
            bool: 是否成功取消
        """
        with self._running_lock:
            future = self._running_tasks.get(task_id)
            if future is None:
                return False
            return self._do_cancel(future, task_id)

    def get_running_count(self) -> int:
        """获取当前运行中的任务数"""
        with self._running_lock:
            return len(self._running_tasks)

    def _build_stats(self) -> Dict[str, Any]:
        return {
            "max_workers": self.max_workers,
            "running": self.get_running_count(),
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_timeout": self.total_timeout,
            "total_cancelled": self.total_cancelled,
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return self._build_stats()

    def get_recent_history(self, n: int = 100) -> List[ExecutionRecord]:
        """获取最近执行历史"""
        with self._history_lock:
            return self._history[-n:]

    def _trim_history(self) -> None:
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _add_history(self, record: ExecutionRecord) -> None:
        """添加执行记录"""
        with self._history_lock:
            self._history.append(record)
            self._trim_history()

    def shutdown(self, wait: bool = True) -> None:
        """关闭执行器"""
        logger.info("Shutting down TaskExecutor...")
        self._executor.shutdown(wait=wait)
        logger.info("TaskExecutor shut down")


class ConcurrentTaskManager:
    """
    并发任务管理器

    第一性原理：系统资源有限，必须有序调度任务执行
    - 优先级队列：高优先级任务优先执行
    - 并发限制：防止资源耗尽
    - 依赖管理：支持任务间依赖关系
    """

    def __init__(
        self,
        max_concurrent: int = 4,
        default_timeout: float = 60.0,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.executor = TaskExecutor(
            max_workers=max_concurrent,
            default_timeout=default_timeout,
        )
        self._pending_queue: List[Task] = []
        self._queue_lock = threading.Lock()
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动任务调度器"""
        self._is_running = True
        self._worker_thread = threading.Thread(target=self._schedule_loop, name="task_scheduler")
        self._worker_thread.daemon = True
        self._worker_thread.start()
        logger.info("ConcurrentTaskManager started")

    def stop(self) -> None:
        """停止任务调度器"""
        self._is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        self.executor.shutdown(wait=True)
        logger.info("ConcurrentTaskManager stopped")

    def enqueue(self, task: Task) -> bool:
        """
        将任务加入等待队列

        Returns:
            bool: 是否成功加入
        """
        with self._queue_lock:
            self._pending_queue.append(task)
            self._pending_queue.sort(key=lambda t: t.priority.value)
        logger.debug(f"Task {task.name} enqueued, queue size: {len(self._pending_queue)}")
        return True

    def _has_capacity(self) -> bool:
        """检查是否有空闲槽位"""
        return self.executor.get_running_count() < self.max_concurrent

    def _dequeue(self) -> Optional[Task]:
        """从队列取出一个任务"""
        with self._queue_lock:
            if not self._pending_queue:
                return None
            return self._pending_queue.pop(0)

    def _run_task_async(self, task: Task) -> None:
        """异步运行任务并清理"""
        record = self.executor.submit(task, timeout=self.default_timeout)
        logger.debug(f"Task {task.name} finished with status {record.status.value}")

    def _submit_async(self, task: Task) -> None:
        """异步提交任务"""
        thread = threading.Thread(
            target=self._run_task_async,
            args=(task,),
            name=f"async_{task.id}"
        )
        thread.daemon = True
        thread.start()

    def _wait_no_capacity(self) -> bool:
        time.sleep(0.1)
        return False

    def _wait_no_task(self) -> bool:
        time.sleep(0.1)
        return False

    def _try_schedule_one(self) -> bool:
        """尝试调度一个任务，返回是否成功"""
        if not self._has_capacity():
            return self._wait_no_capacity()
        task = self._dequeue()
        if task is None:
            return self._wait_no_task()
        self._submit_async(task)
        return True

    def _tick(self) -> None:
        self._try_schedule_one()

    def _schedule_loop(self) -> None:
        """调度循环"""
        while self._is_running:
            self._tick()

    def get_queue_size(self) -> int:
        """获取等待队列大小"""
        with self._queue_lock:
            return len(self._pending_queue)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.executor.get_stats()
        stats["queue_size"] = self.get_queue_size()
        return stats

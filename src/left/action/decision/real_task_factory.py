"""
真实任务工厂

第一性原理：任务必须产生可度量的真实价值
- 替换占位任务（生成随机数、获取时间戳）为真实可执行任务
- 每个任务采集真实环境数据，输出结构化结果

类比：生物的"觅食行为"——不是模拟觅食动作，而是真正寻找和获取食物

核心任务：
1. system_health_check：采集真实CPU/内存/磁盘指标
2. log_scan：扫描日志目录，统计错误和警告
3. file_inventory：扫描工作目录，统计文件类型分布
4. disk_usage_report：计算磁盘使用率，识别大文件
5. process_audit：列出高资源占用进程
"""

import os
import time
import logging
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState, GapState
from ....platform.support.models.base.task import Task, TaskPriority, TaskResult


logger = logging.getLogger(__name__)


def _safe_import_psutil() -> Optional[Any]:
    """安全导入psutil"""
    try:
        import psutil
        return psutil
    except ImportError:
        return None


class RealTaskFactoryBase(ABC):
    """真实任务工厂抽象基类"""

    @abstractmethod
    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建真实任务"""
        pass

    @abstractmethod
    def task_type_name(self) -> str:
        """任务类型名称"""
        pass


class SystemHealthCheckFactory(RealTaskFactoryBase):
    """系统健康检查任务工厂"""

    def task_type_name(self) -> str:
        return "system_health_check"

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建系统健康检查任务"""
        return [Task(
            name="system_health_check",
            description="采集真实CPU/内存/磁盘指标，输出健康报告",
            target_drive="safe",
            priority=TaskPriority.HIGH,
            execute_fn=self._create_health_check_fn(),
        )]

    def _create_health_check_fn(self) -> Callable[[], TaskResult]:
        """创建健康检查执行函数"""
        def check() -> TaskResult:
            return self._perform_health_check()
        return check

    def _perform_health_check(self) -> TaskResult:
        """执行健康检查"""
        psutil = _safe_import_psutil()
        if psutil is None:
            return self._fallback_check()
        return self._psutil_check(psutil)

    def _psutil_check(self, psutil: Any) -> TaskResult:
        """使用psutil采集指标"""
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        data = {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_available_mb": round(mem.available / 1048576, 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / 1073741824, 1),
            "load_avg_1m": load[0],
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        }
        return TaskResult(
            success=True,
            message=f"CPU={cpu}% MEM={mem.percent}% DISK={disk.percent}%",
            data=data,
        )

    def _fallback_check(self) -> TaskResult:
        """无psutil时的降级检查"""
        data = {
            "cpu_percent": -1.0,
            "memory_percent": -1.0,
            "disk_percent": self._fallback_disk_usage(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "note": "psutil not available, limited metrics",
        }
        return TaskResult(
            success=True,
            message="Health check (limited, no psutil)",
            data=data,
        )

    def _fallback_disk_usage(self) -> float:
        """降级磁盘使用率计算"""
        try:
            usage = os.statvfs("/")
            total = usage.f_blocks * usage.f_frsize
            free = usage.f_bavail * usage.f_frsize
            if total <= 0:
                return 0.0
            return round((1.0 - free / total) * 100, 1)
        except (OSError, AttributeError):
            return 0.0


class LogScanFactory(RealTaskFactoryBase):
    """日志扫描任务工厂"""

    def task_type_name(self) -> str:
        return "log_scan"

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建日志扫描任务"""
        if gaps.safety < 0.2 and state.logs.error_rate < 0.05:
            return []
        return [Task(
            name="log_scan",
            description="扫描日志目录，统计ERROR/WARNING数量",
            target_drive="safe",
            priority=TaskPriority.NORMAL,
            execute_fn=self._create_log_scan_fn(),
        )]

    def _create_log_scan_fn(self) -> Callable[[], TaskResult]:
        """创建日志扫描执行函数"""
        def scan() -> TaskResult:
            return self._scan_logs()
        return scan

    def _scan_logs(self) -> TaskResult:
        """扫描日志目录"""
        log_dir = self._find_log_dir()
        if not os.path.isdir(log_dir):
            return TaskResult(
                success=False,
                message=f"Log directory not found: {log_dir}",
                data={"log_dir": log_dir},
            )
        stats = self._collect_log_stats(log_dir)
        return self._build_log_result(log_dir, stats)

    def _find_log_dir(self) -> str:
        """查找日志目录"""
        candidates = ["logs", "../logs", "../../logs", "/workspace/self_driven_agent/logs"]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return "logs"

    def _collect_log_stats(self, log_dir: str) -> Dict[str, Any]:
        """收集日志统计"""
        counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0}
        recent_errors: List[str] = []
        files_scanned = 0
        for fname in os.listdir(log_dir):
            if not fname.endswith(".log"):
                continue
            files_scanned += 1
            self._scan_one_log(os.path.join(log_dir, fname), counts, recent_errors)
        return {
            "counts": counts,
            "recent_errors": recent_errors[-10:],
            "files_scanned": files_scanned,
        }

    def _scan_one_log(
        self, path: str, counts: Dict[str, int], recent_errors: List[str]
    ) -> None:
        """扫描单个日志文件"""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    self._classify_line(line, counts, recent_errors)
        except (OSError, IOError):
            pass

    def _classify_line(
        self, line: str, counts: Dict[str, int], recent_errors: List[str]
    ) -> None:
        """分类日志行"""
        upper = line.upper()
        if "ERROR" in upper:
            counts["ERROR"] += 1
            recent_errors.append(line.strip()[:200])
        elif "WARNING" in upper:
            counts["WARNING"] += 1
        elif "INFO" in upper:
            counts["INFO"] += 1
        elif "DEBUG" in upper:
            counts["DEBUG"] += 1

    def _build_log_result(self, log_dir: str, stats: Dict[str, Any]) -> TaskResult:
        """构建日志扫描结果"""
        counts = stats["counts"]
        total = sum(counts.values())
        error_rate = counts["ERROR"] / max(total, 1)
        return TaskResult(
            success=True,
            message=f"Scanned {stats['files_scanned']} logs: "
                    f"{counts['ERROR']} errors, {counts['WARNING']} warnings",
            data={
                "log_dir": log_dir,
                "counts": counts,
                "error_rate": round(error_rate, 4),
                "recent_errors": stats["recent_errors"],
                "files_scanned": stats["files_scanned"],
            },
        )


class FileInventoryFactory(RealTaskFactoryBase):
    """文件清单任务工厂"""

    def task_type_name(self) -> str:
        return "file_inventory"

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建文件清单任务"""
        return [Task(
            name="file_inventory",
            description="扫描工作目录，统计文件类型分布",
            target_drive="gain",
            priority=TaskPriority.LOW,
            execute_fn=self._create_inventory_fn(),
        )]

    def _create_inventory_fn(self) -> Callable[[], TaskResult]:
        """创建文件清单执行函数"""
        def inventory() -> TaskResult:
            return self._scan_files()
        return inventory

    def _scan_files(self) -> TaskResult:
        """扫描文件"""
        target_dir = self._find_target_dir()
        if not os.path.isdir(target_dir):
            return TaskResult(
                success=False,
                message=f"Target directory not found: {target_dir}",
                data={"target_dir": target_dir},
            )
        stats = self._collect_file_stats(target_dir)
        return self._build_inventory_result(target_dir, stats)

    def _find_target_dir(self) -> str:
        """查找目标目录"""
        candidates = ["src", "../src", "/workspace/self_driven_agent/src"]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return "src"

    def _collect_file_stats(self, target_dir: str) -> Dict[str, Any]:
        """收集文件统计"""
        type_counts: Dict[str, int] = {}
        type_sizes: Dict[str, int] = {}
        total_files = 0
        total_size = 0
        large_files: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(target_dir):
            for fname in files:
                path = os.path.join(root, fname)
                total_files += 1
                ext = os.path.splitext(fname)[1].lower() or "(no ext)"
                size = self._safe_file_size(path)
                total_size += size
                self._update_type_stats(type_counts, type_sizes, ext, size)
                self._check_large_file(path, fname, size, large_files)
        return {
            "type_counts": type_counts,
            "type_sizes": type_sizes,
            "total_files": total_files,
            "total_size_mb": round(total_size / 1048576, 2),
            "large_files": large_files[:10],
        }

    def _safe_file_size(self, path: str) -> int:
        """安全获取文件大小"""
        try:
            return os.path.getsize(path)
        except (OSError, IOError):
            return 0

    def _update_type_stats(
        self,
        type_counts: Dict[str, int],
        type_sizes: Dict[str, int],
        ext: str,
        size: int,
    ) -> None:
        """更新类型统计"""
        type_counts[ext] = type_counts.get(ext, 0) + 1
        type_sizes[ext] = type_sizes.get(ext, 0) + size

    def _check_large_file(
        self, path: str, fname: str, size: int, large_files: List[Dict[str, Any]]
    ) -> None:
        """检查大文件"""
        if size > 102400:
            large_files.append({
                "name": fname,
                "path": path,
                "size_kb": round(size / 1024, 1),
            })

    def _build_inventory_result(
        self, target_dir: str, stats: Dict[str, Any]
    ) -> TaskResult:
        """构建文件清单结果"""
        top_types = sorted(
            stats["type_counts"].items(), key=lambda x: x[1], reverse=True
        )[:5]
        return TaskResult(
            success=True,
            message=f"Found {stats['total_files']} files, "
                    f"{stats['total_size_mb']}MB total",
            data={
                "target_dir": target_dir,
                "total_files": stats["total_files"],
                "total_size_mb": stats["total_size_mb"],
                "type_distribution": dict(top_types),
                "large_files": stats["large_files"],
            },
        )


class DiskUsageReportFactory(RealTaskFactoryBase):
    """磁盘使用报告任务工厂"""

    def task_type_name(self) -> str:
        return "disk_usage_report"

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建磁盘使用报告任务"""
        if gaps.efficiency < 0.2:
            return []
        return [Task(
            name="disk_usage_report",
            description="计算磁盘使用率，识别大文件",
            target_drive="eff",
            priority=TaskPriority.NORMAL,
            execute_fn=self._create_disk_report_fn(),
        )]

    def _create_disk_report_fn(self) -> Callable[[], TaskResult]:
        """创建磁盘报告执行函数"""
        def report() -> TaskResult:
            return self._generate_disk_report()
        return report

    def _generate_disk_report(self) -> TaskResult:
        """生成磁盘报告"""
        psutil = _safe_import_psutil()
        if psutil is not None:
            return self._psutil_disk_report(psutil)
        return self._fallback_disk_report()

    def _psutil_disk_report(self, psutil: Any) -> TaskResult:
        """使用psutil生成磁盘报告"""
        disk = psutil.disk_usage("/")
        data = {
            "total_gb": round(disk.total / 1073741824, 1),
            "used_gb": round(disk.used / 1073741824, 1),
            "free_gb": round(disk.free / 1073741824, 1),
            "percent": disk.percent,
        }
        return TaskResult(
            success=True,
            message=f"Disk: {disk.percent}% used ({data['used_gb']}GB / {data['total_gb']}GB)",
            data=data,
        )

    def _fallback_disk_report(self) -> TaskResult:
        """降级磁盘报告"""
        try:
            usage = os.statvfs("/")
            total = usage.f_blocks * usage.f_frsize
            free = usage.f_bavail * usage.f_frsize
            used = total - free
            percent = round(used / max(total, 1) * 100, 1)
            return TaskResult(
                success=True,
                message=f"Disk: {percent}% used (fallback)",
                data={
                    "total_gb": round(total / 1073741824, 1),
                    "used_gb": round(used / 1073741824, 1),
                    "free_gb": round(free / 1073741824, 1),
                    "percent": percent,
                    "method": "statvfs",
                },
            )
        except (OSError, AttributeError):
            return TaskResult(
                success=False,
                message="Unable to get disk usage",
                data={},
            )


class ProcessAuditFactory(RealTaskFactoryBase):
    """进程审计任务工厂"""

    def task_type_name(self) -> str:
        return "process_audit"

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建进程审计任务"""
        return [Task(
            name="process_audit",
            description="列出高资源占用进程",
            target_drive="safe",
            priority=TaskPriority.LOW,
            execute_fn=self._create_audit_fn(),
        )]

    def _create_audit_fn(self) -> Callable[[], TaskResult]:
        """创建进程审计执行函数"""
        def audit() -> TaskResult:
            return self._audit_processes()
        return audit

    def _audit_processes(self) -> TaskResult:
        """审计进程"""
        psutil = _safe_import_psutil()
        if psutil is None:
            return self._fallback_audit()
        return self._psutil_audit(psutil)

    def _psutil_audit(self, psutil: Any) -> TaskResult:
        """使用psutil审计进程"""
        procs: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu": round(info["cpu_percent"] or 0.0, 1),
                    "mem": round(info["memory_percent"] or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        top_cpu = sorted(procs, key=lambda p: p["cpu"], reverse=True)[:5]
        top_mem = sorted(procs, key=lambda p: p["mem"], reverse=True)[:5]
        return TaskResult(
            success=True,
            message=f"Audited {len(procs)} processes",
            data={
                "total_processes": len(procs),
                "top_cpu": top_cpu,
                "top_mem": top_mem,
            },
        )

    def _fallback_audit(self) -> TaskResult:
        """降级进程审计"""
        pid = os.getpid()
        return TaskResult(
            success=True,
            message="Process audit (limited, no psutil)",
            data={
                "total_processes": 1,
                "top_cpu": [{"pid": pid, "name": "self_driven_agent", "cpu": 0.0, "mem": 0.0}],
                "top_mem": [{"pid": pid, "name": "self_driven_agent", "cpu": 0.0, "mem": 0.0}],
                "note": "psutil not available",
            },
        )


class RealTaskFactory:
    """
    真实任务工厂聚合器

    第一性原理：任务来源多样化，避免单一空转
    聚合多个工厂，根据缺口和环境状态生成多样化真实任务
    """

    def __init__(self) -> None:
        self._factories: List[RealTaskFactoryBase] = []
        self._register_default_factories()

    def _register_default_factories(self) -> None:
        """注册默认工厂"""
        self._factories = [
            SystemHealthCheckFactory(),
            LogScanFactory(),
            FileInventoryFactory(),
            DiskUsageReportFactory(),
            ProcessAuditFactory(),
        ]

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建真实任务"""
        tasks: List[Task] = []
        for factory in self._factories:
            tasks.extend(factory.create_tasks(gaps, state))
        return tasks

    def get_factory_names(self) -> List[str]:
        """获取所有工厂名称"""
        return [f.task_type_name() for f in self._factories]

    def add_factory(self, factory: RealTaskFactoryBase) -> None:
        """添加自定义工厂"""
        self._factories.append(factory)

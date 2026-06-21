"""
文件处理管道任务工厂

第一性原理：系统必须能处理真实文件，产生结构化输出
- 扫描：遍历目录，收集文件元数据
- 分类：按扩展名分组统计
- 分析：识别异常文件（空文件、超大文件、损坏文件）
- 报告：生成可读的结构化汇总报告

类比：生物的"消化系统"——摄入原材料，分解分类，输出营养报告

核心功能：
1. 批量扫描目录文件
2. 按类型分类统计
3. 识别异常文件
4. 生成文件清单报告
5. 支持文件内容摘要提取
"""

import os
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....platform.support.models.base.state import EnvironmentState, GapState
from ....platform.support.models.base.task import Task, TaskPriority, TaskResult


logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """文件信息"""
    name: str
    path: str
    extension: str
    size_bytes: int
    is_empty: bool = False
    is_large: bool = False
    is_readable: bool = True
    md5_prefix: str = ""
    line_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "size_kb": round(self.size_bytes / 1024, 2),
            "is_empty": self.is_empty,
            "is_large": self.is_large,
            "is_readable": self.is_readable,
            "md5_prefix": self.md5_prefix,
            "line_count": self.line_count,
        }


@dataclass
class FileProcessingReport:
    """文件处理报告"""
    target_dir: str = ""
    total_files: int = 0
    total_size_bytes: int = 0
    type_distribution: Dict[str, int] = field(default_factory=dict)
    type_sizes: Dict[str, int] = field(default_factory=dict)
    empty_files: List[FileInfo] = field(default_factory=list)
    large_files: List[FileInfo] = field(default_factory=list)
    unreadable_files: List[FileInfo] = field(default_factory=list)
    all_files: List[FileInfo] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_dir": self.target_dir,
            "total_files": self.total_files,
            "total_size_mb": round(self.total_size_bytes / 1048576, 2),
            "type_distribution": self.type_distribution,
            "type_sizes_mb": {
                k: round(v / 1048576, 2) for k, v in self.type_sizes.items()
            },
            "empty_files": [f.to_dict() for f in self.empty_files],
            "large_files": [f.to_dict() for f in self.large_files],
            "unreadable_files": [f.to_dict() for f in self.unreadable_files],
            "anomalies": self.anomalies,
        }


class FileAnalyzer(ABC):
    """文件分析器抽象基类"""

    @abstractmethod
    def analyze(self, path: str) -> FileInfo:
        """分析单个文件"""
        pass


class StandardFileAnalyzer(FileAnalyzer):
    """标准文件分析器"""

    LARGE_FILE_THRESHOLD: int = 102400  # 100KB
    MD5_PREFIX_LENGTH: int = 8
    MAX_LINES_TO_COUNT: int = 10000

    def analyze(self, path: str) -> FileInfo:
        """分析文件"""
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        size = self._safe_size(path)
        info = FileInfo(
            name=name,
            path=path,
            extension=ext,
            size_bytes=size,
            is_empty=(size == 0),
            is_large=(size > self.LARGE_FILE_THRESHOLD),
        )
        self._enrich_info(info, path)
        return info

    def _safe_size(self, path: str) -> int:
        """安全获取文件大小"""
        try:
            return os.path.getsize(path)
        except (OSError, IOError):
            return 0

    def _enrich_info(self, info: FileInfo, path: str) -> None:
        """补充文件信息"""
        if info.is_empty:
            return
        content = self._read_file(path)
        if content is None:
            info.is_readable = False
            return
        info.md5_prefix = self._compute_md5_prefix(content)
        info.line_count = self._count_lines(content)

    def _read_file(self, path: str) -> Optional[bytes]:
        """读取文件内容"""
        try:
            with open(path, "rb") as f:
                return f.read()
        except (OSError, IOError):
            return None

    def _compute_md5_prefix(self, content: bytes) -> str:
        """计算MD5前缀"""
        return hashlib.md5(content).hexdigest()[:self.MD5_PREFIX_LENGTH]

    def _count_lines(self, content: bytes) -> int:
        """计算行数"""
        try:
            text = content.decode("utf-8", errors="ignore")
            lines = text.splitlines()
            return min(len(lines), self.MAX_LINES_TO_COUNT)
        except (UnicodeDecodeError, AttributeError):
            return 0


class FileProcessingTaskFactory:
    """
    文件处理管道任务工厂

    第一性原理：系统必须能处理真实文件，产生结构化输出
    - 批量扫描目录
    - 分类统计
    - 异常检测
    - 报告生成
    """

    SKIP_DIRS: Tuple[str, ...] = (
        "__pycache__", ".git", ".pytest_cache", "node_modules", ".venv",
    )

    def __init__(
        self,
        target_dir: str = "src",
        analyzer: Optional[FileAnalyzer] = None,
    ) -> None:
        self._target_dir = target_dir
        self._analyzer = analyzer or StandardFileAnalyzer()
        self._last_report: Optional[FileProcessingReport] = None

    def create_tasks(self, gaps: GapState, state: EnvironmentState) -> List[Task]:
        """创建文件处理任务"""
        if gaps.gain < 0.1 and self._last_report is not None:
            return []
        return [Task(
            name="file_processing_pipeline",
            description="批量处理文件，生成分类报告",
            target_drive="gain",
            priority=TaskPriority.NORMAL,
            execute_fn=self._create_process_fn(),
        )]

    def _create_process_fn(self) -> Callable[[], TaskResult]:
        """创建处理执行函数"""
        def process() -> TaskResult:
            return self._run_pipeline()
        return process

    def _run_pipeline(self) -> TaskResult:
        """执行文件处理管道"""
        if not os.path.isdir(self._target_dir):
            return self._build_no_dir_result()
        report = self._scan_directory()
        self._detect_anomalies(report)
        self._last_report = report
        return self._to_task_result(report)

    def _build_no_dir_result(self) -> TaskResult:
        """构建目录不存在结果"""
        return TaskResult(
            success=False,
            message=f"Target directory not found: {self._target_dir}",
            data={"target_dir": self._target_dir},
        )

    def _scan_directory(self) -> FileProcessingReport:
        """扫描目录"""
        report = FileProcessingReport(target_dir=self._target_dir)
        for root, dirs, files in os.walk(self._target_dir):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            self._process_dir_files(root, files, report)
        return report

    def _process_dir_files(
        self, root: str, files: List[str], report: FileProcessingReport
    ) -> None:
        """处理目录中的文件"""
        for fname in files:
            path = os.path.join(root, fname)
            info = self._analyzer.analyze(path)
            self._add_to_report(info, report)

    def _add_to_report(self, info: FileInfo, report: FileProcessingReport) -> None:
        """将文件信息添加到报告"""
        report.all_files.append(info)
        report.total_files += 1
        report.total_size_bytes += info.size_bytes
        self._update_type_stats(info, report)
        self._classify_file(info, report)

    def _update_type_stats(self, info: FileInfo, report: FileProcessingReport) -> None:
        """更新类型统计"""
        ext = info.extension or "(no ext)"
        report.type_distribution[ext] = report.type_distribution.get(ext, 0) + 1
        report.type_sizes[ext] = report.type_sizes.get(ext, 0) + info.size_bytes

    def _classify_file(self, info: FileInfo, report: FileProcessingReport) -> None:
        """分类文件"""
        if info.is_empty:
            report.empty_files.append(info)
        if info.is_large:
            report.large_files.append(info)
        if not info.is_readable and not info.is_empty:
            report.unreadable_files.append(info)

    def _detect_anomalies(self, report: FileProcessingReport) -> None:
        """检测异常"""
        self._check_empty_files(report)
        self._check_large_files(report)
        self._check_unreadable(report)

    def _check_empty_files(self, report: FileProcessingReport) -> None:
        """检查空文件"""
        if len(report.empty_files) > 0:
            report.anomalies.append(
                f"EMPTY_FILES: {len(report.empty_files)} empty files found"
            )

    def _check_large_files(self, report: FileProcessingReport) -> None:
        """检查大文件"""
        if len(report.large_files) > 0:
            report.anomalies.append(
                f"LARGE_FILES: {len(report.large_files)} files exceed "
                f"{StandardFileAnalyzer.LARGE_FILE_THRESHOLD} bytes"
            )

    def _check_unreadable(self, report: FileProcessingReport) -> None:
        """检查不可读文件"""
        if len(report.unreadable_files) > 0:
            report.anomalies.append(
                f"UNREADABLE_FILES: {len(report.unreadable_files)} files unreadable"
            )

    def _to_task_result(self, report: FileProcessingReport) -> TaskResult:
        """转换为任务结果"""
        has_anomalies = len(report.anomalies) > 0
        return TaskResult(
            success=True,
            message=f"Processed {report.total_files} files, "
                    f"{round(report.total_size_bytes / 1048576, 2)}MB total"
                    + (f", {len(report.anomalies)} anomalies" if has_anomalies else ""),
            data=report.to_dict(),
        )

    def get_last_report(self) -> Optional[FileProcessingReport]:
        """获取上次报告"""
        return self._last_report

    def set_target_dir(self, dir_path: str) -> None:
        """设置目标目录"""
        self._target_dir = dir_path

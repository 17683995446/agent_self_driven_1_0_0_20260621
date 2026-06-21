"""
快照与回滚系统

第一性原理：进化必须可逆，防止退化导致系统崩溃
类比：生物的"DNA备份"——保留稳定版本，突变失败时恢复
"""

import os
import time
import json
import shutil
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass, field, asdict


logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """
    快照 —— 系统某一时刻的完整状态

    第一性原理：快照是系统的"时间胶囊"，保存进化历史
    """
    id: str
    timestamp: float
    version: str = "1.0"
    model_state: Dict[str, Any] = field(default_factory=dict)
    config_state: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age(self) -> float:
        """快照年龄（秒）"""
        return time.time() - self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return self._make_dict(
            self.id, self.timestamp, self.version,
            self.model_state, self.config_state, self.metrics, self.metadata,
        )

    @staticmethod
    def _make_dict(
        id: str,
        timestamp: float,
        version: str,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        d = {"id": id, "timestamp": timestamp, "version": version}
        d["model_state"] = model_state
        d["config_state"] = config_state
        d["metrics"] = metrics
        d["metadata"] = metadata
        return d

    @classmethod
    def from_dict(cls: Type["Snapshot"], data: Dict[str, Any]) -> "Snapshot":
        return cls(**cls._extract_kwargs(data))

    @staticmethod
    def _extract_kwargs(data: Dict[str, Any]) -> Dict[str, Any]:
        kwargs = {"id": data["id"], "timestamp": data["timestamp"]}
        kwargs["version"] = data.get("version", "1.0")
        kwargs["model_state"] = data.get("model_state", {})
        kwargs["config_state"] = data.get("config_state", {})
        kwargs["metrics"] = data.get("metrics", {})
        kwargs["metadata"] = data.get("metadata", {})
        return kwargs



@dataclass
class RollbackResult:
    """回滚结果"""
    success: bool = False
    snapshot_id: str = ""
    message: str = ""
    restored_state: Dict[str, Any] = field(default_factory=dict)


class SnapshotManagerBase(ABC):
    """快照管理器抽象基类"""

    @abstractmethod
    def create_snapshot(
        self,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any] = None
    ) -> Snapshot:
        """创建快照"""
        pass

    @abstractmethod
    def rollback(self, snapshot_id: str = None) -> RollbackResult:
        """回滚到指定快照"""
        pass


class SnapshotManager(SnapshotManagerBase):
    """
    快照管理器

    负责：
    1. 创建系统快照
    2. 管理快照生命周期
    3. 执行回滚操作
    4. 验证快照完整性

    第一性原理：
    - 快照操作必须原子化
    - 回滚必须可验证
    - 保留历史用于分析
    """

    def __init__(
        self,
        snapshot_dir: str = "./snapshots",
        max_snapshots: int = 10,
        auto_snapshot_interval: int = 3600
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.max_snapshots = max_snapshots
        self.auto_snapshot_interval = auto_snapshot_interval
        self._init_snapshot_state()
        logger.info(f"SnapshotManager initialized: dir={snapshot_dir}, max={max_snapshots}")

    def _init_snapshot_state(self) -> None:
        os.makedirs(self.snapshot_dir, exist_ok=True)
        self.snapshots: List[Snapshot] = []
        self.last_snapshot_time = 0.0
        self._load_existing_snapshots()

    def _generate_id(self) -> str:
        """生成快照ID"""
        return f"snapshot_{int(time.time() * 1000000)}"

    def _build_snapshot(
        self,
        snapshot_id: str,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any]
    ) -> Snapshot:
        """构建快照对象"""
        return self._create_snapshot_obj(snapshot_id, time.time(), model_state, config_state, metrics, metadata)

    def _snapshot_kwargs(
        self,
        snapshot_id: str,
        timestamp: float,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        d = {"id": snapshot_id, "timestamp": timestamp}
        d["model_state"] = model_state
        d["config_state"] = config_state
        d["metrics"] = metrics
        d["metadata"] = metadata
        return d

    def _create_snapshot_obj(
        self,
        snapshot_id: str,
        timestamp: float,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any],
    ) -> Snapshot:
        return Snapshot(**self._snapshot_kwargs(
            snapshot_id, timestamp, model_state, config_state, metrics, metadata
        ))

    def _log_snapshot_created(self, snapshot: Snapshot) -> None:
        """记录快照创建日志"""
        logger.info(f"Snapshot created: {snapshot.id}")

    def create_snapshot(
        self,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any] = None
    ) -> Snapshot:
        """
        创建快照

        第一性原理：快照必须包含系统的完整状态
        """
        snapshot = self._build_and_save_snapshot(model_state, config_state, metrics, metadata)
        self._register_snapshot(snapshot)
        self._log_snapshot_created(snapshot)
        return snapshot

    def _build_and_save_snapshot(
        self,
        model_state: Dict[str, Any],
        config_state: Dict[str, Any],
        metrics: Dict[str, float],
        metadata: Dict[str, Any] = None
    ) -> Snapshot:
        snapshot_id = self._generate_id()
        snapshot = self._build_snapshot(
            snapshot_id, model_state, config_state, metrics, metadata or {}
        )
        self._save_snapshot(snapshot)
        return snapshot

    def _find_snapshot_in_memory(self, snapshot_id: str) -> Optional[Snapshot]:
        """在内存中查找快照"""
        for snapshot in self.snapshots:
            if snapshot.id == snapshot_id:
                return snapshot
        return None

    def _register_snapshot(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)
        self.last_snapshot_time = time.time()
        self._cleanup_old_snapshots()

    def _find_snapshot(self, snapshot_id: Optional[str]) -> Optional[Snapshot]:
        """查找快照"""
        if snapshot_id is None:
            return self._find_last_stable_snapshot()
        return self._find_snapshot_in_memory(snapshot_id)

    def _build_restored_state(self, snapshot: Snapshot) -> Dict[str, Any]:
        """构建恢复后的状态"""
        return {
            "model_state": snapshot.model_state,
            "config_state": snapshot.config_state,
            "metrics": snapshot.metrics,
        }

    def _resolve_rollback_target(self, snapshot_id: Optional[str]) -> Optional[Snapshot]:
        """解析回滚目标快照"""
        return self._find_snapshot(snapshot_id)

    def rollback(self, snapshot_id: str = None) -> RollbackResult:
        """
        回滚到指定快照

        第一性原理：回滚是进化的保险，防止退化
        """
        snapshot = self._resolve_rollback_target(snapshot_id)
        if snapshot is None:
            return self._rollback_not_found()
        return self._perform_rollback(snapshot)

    def _rollback_not_found(self) -> RollbackResult:
        return RollbackResult(
            success=False,
            message="No suitable snapshot found for rollback"
        )

    def _perform_rollback(self, snapshot: Snapshot) -> RollbackResult:
        logger.info(f"Rolling back to snapshot: {snapshot.id}")
        try:
            return self._execute_rollback(snapshot)
        except Exception as e:
            return self._rollback_failed(e)

    def _rollback_failed(self, error: Exception) -> RollbackResult:
        logger.error(f"Rollback failed: {error}")
        return RollbackResult(
            success=False,
            message=f"Rollback failed: {str(error)}",
        )

    def _build_success_result(self, snapshot: Snapshot) -> RollbackResult:
        """构建成功回滚结果"""
        return self._make_success_result(snapshot, self._build_restored_state(snapshot))

    def _make_success_result(self, snapshot: Snapshot, restored_state: Dict[str, Any]) -> RollbackResult:
        logger.info(f"Rollback successful: {snapshot.id}")
        return RollbackResult(
            success=True,
            snapshot_id=snapshot.id,
            message="Rollback completed successfully",
            restored_state=restored_state,
        )

    def _execute_rollback(self, snapshot: Snapshot) -> RollbackResult:
        if not self._verify_snapshot(snapshot):
            return RollbackResult(
                success=False,
                message=f"Snapshot {snapshot.id} verification failed"
            )
        return self._build_success_result(snapshot)

    def should_auto_snapshot(self) -> bool:
        """是否应该自动创建快照"""
        elapsed = time.time() - self.last_snapshot_time
        return elapsed > self.auto_snapshot_interval

    def get_snapshot_history(self) -> List[Dict[str, Any]]:
        """获取快照历史"""
        return [self._snapshot_info(s) for s in self.snapshots]

    @staticmethod
    def _snapshot_info(s: Snapshot) -> Dict[str, Any]:
        return {
            "id": s.id,
            "timestamp": s.timestamp,
            "age": s.age,
            "metrics": s.metrics,
        }

    def _get_metric_diff(self, v1: float, v2: float) -> Dict[str, Any]:
        """计算单个指标差异"""
        return {
            "before": v1,
            "after": v2,
            "change": v2 - v1,
            "change_percent": ((v2 - v1) / v1 * 100) if v1 != 0 else 0
        }

    def _resolve_snapshots_for_compare(
        self, snapshot_id1: str, snapshot_id2: str
    ) -> Tuple[Optional[Snapshot], Optional[Snapshot]]:
        """解析用于比较的两个快照"""
        return self._find_snapshot(snapshot_id1), self._find_snapshot(snapshot_id2)

    def compare_snapshots(
        self,
        snapshot_id1: str,
        snapshot_id2: str
    ) -> Dict[str, Any]:
        """
        比较两个快照

        用于分析进化过程
        """
        s1, s2 = self._resolve_snapshots_for_compare(snapshot_id1, snapshot_id2)
        if not s1 or not s2:
            return {"error": "Snapshot not found"}
        return self._build_comparison(s1, s2)

    def _compare_single_metric(self, s1: Snapshot, s2: Snapshot, key: str) -> Dict[str, Any]:
        """比较单个指标"""
        v1 = s1.metrics.get(key, 0)
        v2 = s2.metrics.get(key, 0)
        return self._get_metric_diff(v1, v2)

    def _build_comparison(self, s1: Snapshot, s2: Snapshot) -> Dict[str, Any]:
        comparison = {
            "time_diff": s2.timestamp - s1.timestamp,
            "metrics_diff": {}
        }
        for key in set(s1.metrics.keys()) | set(s2.metrics.keys()):
            comparison["metrics_diff"][key] = self._compare_single_metric(s1, s2, key)
        comparison["model_state_diff"] = self._diff_dicts(s1.model_state, s2.model_state)
        comparison["config_state_diff"] = self._diff_dicts(s1.config_state, s2.config_state)
        return comparison

    @staticmethod
    def _diff_dicts(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """计算两个字典的差异"""
        diff: Dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            if key not in old:
                diff["added"][key] = new[key]
            elif key not in new:
                diff["removed"][key] = old[key]
            elif old[key] != new[key]:
                diff["changed"][key] = {"from": old[key], "to": new[key]}
        return diff

    def _write_snapshot_file(self, filepath: str, snapshot: Snapshot) -> None:
        """写入快照文件"""
        with open(filepath, 'w') as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def _save_snapshot(self, snapshot: Snapshot) -> None:
        """保存快照到磁盘"""
        filepath = os.path.join(self.snapshot_dir, f"{snapshot.id}.json")
        try:
            self._write_snapshot_file(filepath, snapshot)
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            raise

    def _load_snapshot_file(self, filepath: str) -> Optional[Snapshot]:
        """加载单个快照文件"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Snapshot.from_dict(data)

    def _try_load_snapshot_file(self, filename: str) -> None:
        filepath = os.path.join(self.snapshot_dir, filename)
        try:
            snapshot = self._load_snapshot_file(filepath)
            self.snapshots.append(snapshot)
        except Exception as e:
            logger.warning(f"Failed to load snapshot {filename}: {e}")

    def _finalize_snapshot_load(self) -> None:
        self.snapshots.sort(key=lambda s: s.timestamp)
        if self.snapshots:
            self.last_snapshot_time = self.snapshots[-1].timestamp
        logger.info(f"Loaded {len(self.snapshots)} existing snapshots")

    def _load_snapshot_files(self) -> None:
        for filename in sorted(os.listdir(self.snapshot_dir)):
            if filename.endswith('.json'):
                self._try_load_snapshot_file(filename)

    def _load_existing_snapshots(self) -> None:
        """加载已有快照"""
        if not os.path.exists(self.snapshot_dir):
            return
        self._load_snapshot_files()
        self._finalize_snapshot_load()

    def _find_last_stable_snapshot(self) -> Optional[Snapshot]:
        """查找最后一个稳定快照"""
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def _verify_snapshot(self, snapshot: Snapshot) -> bool:
        """验证快照完整性"""
        if not snapshot.id or snapshot.timestamp <= 0:
            return False
        filepath = os.path.join(self.snapshot_dir, f"{snapshot.id}.json")
        return os.path.exists(filepath)

    def _cleanup_old_snapshots(self) -> None:
        """清理旧快照"""
        while len(self.snapshots) > self.max_snapshots:
            self._remove_oldest_snapshot()
        logger.debug(f"Cleaned up snapshots, remaining: {len(self.snapshots)}")

    def _remove_oldest_snapshot(self) -> None:
        oldest = self.snapshots.pop(0)
        filepath = os.path.join(self.snapshot_dir, f"{oldest.id}.json")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.warning(f"Failed to delete old snapshot: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_snapshots": len(self.snapshots),
            "max_snapshots": self.max_snapshots,
            "last_snapshot_time": self.last_snapshot_time,
            "snapshot_dir": self.snapshot_dir,
        }


class RollbackTrigger:
    """
    回滚触发器

    自动检测是否需要回滚

    第一性原理：退化必须自动恢复
    """

    def __init__(self) -> None:
        self.error_history: List[float] = []
        self.trigger_count = 0

    def _trim_history(self) -> None:
        """裁剪历史记录"""
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]

    def _check_spike(self, current_error: float, threshold: float) -> bool:
        """检查误差突增"""
        if len(self.error_history) < 2:
            return False
        prev_error = self.error_history[-2]
        if self._is_spike(prev_error, current_error, threshold):
            self._trigger_spike(prev_error, current_error)
            return True
        return False

    def _is_spike(self, prev_error: float, current_error: float, threshold: float) -> bool:
        return prev_error > 0 and (current_error - prev_error) / prev_error > threshold

    def _trigger_spike(self, prev_error: float, current_error: float) -> None:
        self.trigger_count += 1
        logger.warning(f"Rollback triggered: error spiked {prev_error:.3f} -> {current_error:.3f}")

    def _check_persistent_degradation(self) -> bool:
        """检查持续下降"""
        if len(self.error_history) < 10:
            return False
        recent = self.error_history[-10:]
        if self._is_degrading(recent):
            self._trigger_degradation()
            return True
        return False

    def _is_degrading(self, recent: List[float]) -> bool:
        monotonic = all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1))
        return monotonic and recent[-1] > recent[0] * 2

    def _trigger_degradation(self) -> None:
        self.trigger_count += 1
        logger.warning("Rollback triggered: persistent degradation")

    def _record_error(self, current_error: float) -> None:
        """记录误差并裁剪历史"""
        self.error_history.append(current_error)
        self._trim_history()

    def check(self, current_error: float, threshold: float = 0.5) -> bool:
        """
        检查是否触发回滚

        条件：
        1. 误差突增超过阈值
        2. 性能持续下降
        """
        self._record_error(current_error)
        if self._check_spike(current_error, threshold):
            return True
        return self._check_persistent_degradation()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "trigger_count": self.trigger_count,
            "error_history_length": len(self.error_history),
        }

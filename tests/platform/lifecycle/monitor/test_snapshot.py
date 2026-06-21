"""
快照与回滚模块测试

验证快照创建、回滚、比较的正确性
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest

from src.platform.lifecycle.monitor.snapshot import SnapshotManager, SnapshotManagerBase, Snapshot, RollbackResult


class TestSnapshotManagerBase:
    """测试快照管理器基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            SnapshotManagerBase()


class TestSnapshotManagerInit:
    """测试快照管理器初始化"""

    def test_normal_init(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        assert manager is not None


class TestCreateSnapshot:
    """测试快照创建"""

    def test_normal_snapshot(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        model_state = {"weights": [0.1, 0.2]}
        config_state = {"interval": 1.0}
        metrics = {"error": 0.05}
        snapshot = manager.create_snapshot(model_state, config_state, metrics)
        assert isinstance(snapshot, Snapshot)

    def test_snapshot_with_metadata(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snapshot = manager.create_snapshot({}, {}, {}, metadata={"tag": "test"})
        assert snapshot.metadata.get("tag") == "test"


class TestRollback:
    """测试回滚"""

    def test_rollback_to_snapshot(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snapshot = manager.create_snapshot({"key": "value"}, {}, {})
        result = manager.rollback(snapshot.id)
        assert isinstance(result, RollbackResult)
        assert result.success is True

    def test_rollback_invalid_id(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        result = manager.rollback("invalid_id")
        assert isinstance(result, RollbackResult)
        assert result.success is False


class TestCompareSnapshots:
    """测试快照比较"""

    def test_compare_same(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({"a": 1}, {}, {})
        snap2 = manager.create_snapshot({"a": 1}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff is not None

    def test_compare_different(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({"a": 1}, {}, {})
        snap2 = manager.create_snapshot({"a": 2}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff is not None


class TestSnapshotDiffAnalysis:
    """测试快照差异分析"""

    def test_model_state_added(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({"a": 1}, {}, {})
        snap2 = manager.create_snapshot({"a": 1, "b": 2}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff["model_state_diff"]["added"] == {"b": 2}

    def test_model_state_removed(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({"a": 1, "b": 2}, {}, {})
        snap2 = manager.create_snapshot({"a": 1}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff["model_state_diff"]["removed"] == {"b": 2}

    def test_model_state_changed(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({"a": 1}, {}, {})
        snap2 = manager.create_snapshot({"a": 3}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff["model_state_diff"]["changed"]["a"] == {"from": 1, "to": 3}

    def test_config_state_diff(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({}, {"lr": 0.01}, {})
        snap2 = manager.create_snapshot({}, {"lr": 0.001}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff["config_state_diff"]["changed"]["lr"]["to"] == 0.001

    def test_empty_state_diff(self, tmp_path):
        manager = SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))
        snap1 = manager.create_snapshot({}, {}, {})
        snap2 = manager.create_snapshot({}, {}, {})
        diff = manager.compare_snapshots(snap1.id, snap2.id)
        assert diff["model_state_diff"]["added"] == {}
        assert diff["model_state_diff"]["removed"] == {}
        assert diff["model_state_diff"]["changed"] == {}

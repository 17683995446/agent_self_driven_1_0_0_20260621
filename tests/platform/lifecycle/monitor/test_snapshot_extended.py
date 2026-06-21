"""
快照与回滚扩展测试

补充覆盖 Snapshot、RollbackTrigger、自动快照、统计等路径
"""

import os
import tempfile

import pytest

from src.platform.lifecycle.monitor.snapshot import (
    SnapshotManager, Snapshot, RollbackResult, RollbackTrigger,
)


class TestSnapshotExtended:
    """测试快照数据类"""

    def test_snapshot_age(self):
        snapshot = Snapshot(id="test", timestamp=0.0)
        assert snapshot.age > 0

    def test_snapshot_to_dict(self):
        snapshot = Snapshot(id="test", timestamp=1.0, model_state={"a": 1})
        d = snapshot.to_dict()
        assert d["id"] == "test"
        assert d["model_state"]["a"] == 1

    def test_snapshot_from_dict(self):
        data = {"id": "test", "timestamp": 1.0, "model_state": {"a": 1}}
        snapshot = Snapshot.from_dict(data)
        assert snapshot.id == "test"


class TestSnapshotManagerExtended:
    """测试快照管理器扩展路径"""

    def test_should_auto_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir, auto_snapshot_interval=0)
            assert manager.should_auto_snapshot() is True

    def test_get_snapshot_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            manager.create_snapshot({"a": 1}, {}, {})
            history = manager.get_snapshot_history()
            assert len(history) == 1

    def test_rollback_none_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            manager.create_snapshot({"a": 1}, {}, {})
            result = manager.rollback()
            assert isinstance(result, RollbackResult)
            assert result.success is True

    def test_compare_snapshots_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            diff = manager.compare_snapshots("a", "b")
            assert "error" in diff

    def test_cleanup_old_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir, max_snapshots=2)
            manager.create_snapshot({"a": 1}, {}, {})
            manager.create_snapshot({"a": 2}, {}, {})
            manager.create_snapshot({"a": 3}, {}, {})
            assert len(manager.snapshots) <= 2

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            stats = manager.get_stats()
            assert "total_snapshots" in stats

    def test_rollback_invalid_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            # 创建一个快照但删除其文件，使验证失败
            snapshot = manager.create_snapshot({"a": 1}, {}, {})
            filepath = os.path.join(tmpdir, f"{snapshot.id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            result = manager.rollback(snapshot.id)
            assert isinstance(result, RollbackResult)
            assert result.success is False

    def test_rollback_no_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            result = manager.rollback()
            assert isinstance(result, RollbackResult)
            assert result.success is False

    def test_load_existing_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            manager.create_snapshot({"a": 1}, {}, {})
            # 创建第二个管理器加载已有快照
            manager2 = SnapshotManager(snapshot_dir=tmpdir)
            assert len(manager2.snapshots) >= 1

    def test_load_existing_corrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = os.path.join(tmpdir, "bad.json")
            with open(bad_file, "w") as f:
                f.write("not json")
            manager = SnapshotManager(snapshot_dir=tmpdir)
            assert len(manager.snapshots) == 0

    def test_cleanup_old_snapshots_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir, max_snapshots=1)
            snap1 = manager.create_snapshot({"a": 1}, {}, {})
            snap2 = manager.create_snapshot({"a": 2}, {}, {})
            # 删除第一个快照的文件，让cleanup时删除失败
            fp1 = os.path.join(tmpdir, f"{snap1.id}.json")
            if os.path.exists(fp1):
                os.remove(fp1)
            # 再创建第三个触发cleanup
            manager.create_snapshot({"a": 3}, {}, {})
            assert len(manager.snapshots) <= 1

    def test_compare_snapshots_with_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            snap1 = manager.create_snapshot({}, {}, {"error": 0.1})
            snap2 = manager.create_snapshot({}, {}, {"error": 0.2})
            diff = manager.compare_snapshots(snap1.id, snap2.id)
            assert "metrics_diff" in diff
            assert "error" in diff["metrics_diff"]

    def test_get_metric_diff_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            diff = manager._get_metric_diff(0.0, 0.5)
            assert diff["change_percent"] == 0

    def test_save_snapshot_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            # 模拟保存异常：通过patch open来触发
            from unittest.mock import patch
            with patch("builtins.open", side_effect=OSError("disk full")):
                with pytest.raises(Exception):
                    manager._save_snapshot(Snapshot(id="test", timestamp=1.0))

    def test_verify_snapshot_bad_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            bad = Snapshot(id="test", timestamp=-1.0)
            assert manager._verify_snapshot(bad) is False

    def test_verify_snapshot_no_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            bad = Snapshot(id="", timestamp=1.0)
            assert manager._verify_snapshot(bad) is False

    def test_find_last_stable_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(snapshot_dir=tmpdir)
            assert manager._find_last_stable_snapshot() is None

    def test_load_existing_non_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_file = os.path.join(tmpdir, "readme.txt")
            with open(txt_file, "w") as f:
                f.write("hello")
            manager = SnapshotManager(snapshot_dir=tmpdir)
            assert len(manager.snapshots) == 0


class TestRollbackTrigger:
    """测试回滚触发器"""

    def test_no_trigger_initially(self):
        trigger = RollbackTrigger()
        assert trigger.check(0.1) is False

    def test_spike_trigger(self):
        trigger = RollbackTrigger()
        trigger.check(0.1)
        trigger.check(0.2)
        result = trigger.check(0.5)
        assert result is True

    def test_persistent_degradation_trigger(self):
        trigger = RollbackTrigger()
        for i in range(10):
            trigger.check(float(i) * 0.01)
        result = trigger.check(0.5)
        assert result is True

    def test_get_stats(self):
        trigger = RollbackTrigger()
        stats = trigger.get_stats()
        assert "trigger_count" in stats

    def test_trim_history(self):
        trigger = RollbackTrigger()
        for i in range(110):
            trigger.check(float(i) * 0.001)
        assert len(trigger.error_history) <= 100

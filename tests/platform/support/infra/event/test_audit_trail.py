"""
审计追踪系统测试

验证审计记录、哈希链、查询、完整性校验
包含四类用例：正常值、空入参、边界极值、非法格式
"""

import json
import os
import tempfile
import time

import pytest

from src.platform.support.infra.event.audit_trail import (
    AuditTrail, AuditTrailBase, AuditRecord,
    AuditEventType, AuditLevel,
)


class TestAuditTrailBase:
    """测试抽象基类"""

    def test_base_class_is_abstract(self):
        with pytest.raises(TypeError):
            AuditTrailBase()


class TestAuditRecord:
    """测试审计记录"""

    def test_compute_hash(self):
        record = AuditRecord(
            record_id="r1",
            trace_id="t1",
            event_type="TEST",
            details={"key": "value"},
            prev_hash="0" * 16,
        )
        h = record.compute_hash()
        assert len(h) == 16
        assert h != "0" * 16

    def test_to_dict(self):
        record = AuditRecord(record_id="r1", event_type="TEST")
        d = record.to_dict()
        assert d["record_id"] == "r1"
        assert d["event_type"] == "TEST"
        assert "datetime" in d

    def test_from_dict(self):
        data = {
            "record_id": "r1",
            "trace_id": "t1",
            "timestamp": 1234567890.0,
            "event_type": "TEST",
            "cycle": 5,
            "severity": "info",
            "details": {"k": "v"},
            "prev_hash": "0" * 16,
            "record_hash": "abc",
        }
        record = AuditRecord.from_dict(data)
        assert record.record_id == "r1"
        assert record.cycle == 5


class TestAuditTrailInit:
    """测试初始化"""

    def test_normal_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            assert trail.audit_dir.exists()

    def test_load_last_hash_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            assert trail._last_hash == "0" * 16


class TestAuditTrailRecord:
    """测试记录审计事件"""

    def test_record_normal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            rid = trail.record(
                AuditEventType.TASK_EXECUTE,
                {"task_name": "test"},
            )
            assert len(rid) > 0

    def test_record_with_trace_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            rid = trail.record(
                AuditEventType.TASK_EXECUTE,
                {"task_name": "test"},
                trace_id="mytrace",
            )
            records = trail.query_by_trace_id("mytrace")
            assert len(records) == 1
            assert records[0].trace_id == "mytrace"

    def test_record_auto_generates_trace_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            rid = trail.record(
                AuditEventType.TASK_EXECUTE,
                {"task_name": "test"},
            )
            records = trail.query(limit=1)
            assert records[0].trace_id != ""

    def test_record_with_severity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(
                AuditEventType.SAFETY_VIOLATION,
                {"reason": "cpu"},
                severity=AuditLevel.WARNING,
            )
            records = trail.query(severity=AuditLevel.WARNING)
            assert len(records) == 1

    def test_record_invalid_event_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with pytest.raises(ValueError):
                trail.record("invalid", {})

    def test_record_invalid_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with pytest.raises(ValueError):
                trail.record(AuditEventType.TASK_EXECUTE, "not_dict")

    def test_record_listener_called(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            called = []
            trail.add_listener(lambda r: called.append(r.record_id))
            rid = trail.record(AuditEventType.TASK_EXECUTE, {})
            assert rid in called

    def test_record_listener_exception_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.add_listener(lambda r: 1 / 0)
            rid = trail.record(AuditEventType.TASK_EXECUTE, {})
            assert len(rid) > 0


class TestAuditTrailQuery:
    """测试查询功能"""

    def test_query_by_event_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            trail.record(AuditEventType.TASK_COMPLETE, {})
            results = trail.query(event_type=AuditEventType.TASK_EXECUTE)
            assert len(results) == 1
            assert results[0].event_type == "TASK_EXECUTE"

    def test_query_by_severity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {}, severity=AuditLevel.INFO)
            trail.record(AuditEventType.SAFETY_VIOLATION, {}, severity=AuditLevel.WARNING)
            results = trail.query(severity=AuditLevel.WARNING)
            assert len(results) == 1

    def test_query_by_time_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            before = time.time()
            trail.record(AuditEventType.TASK_EXECUTE, {})
            after = time.time()
            results = trail.query(start_time=before, end_time=after)
            assert len(results) == 1

    def test_query_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            for i in range(5):
                trail.record(AuditEventType.TASK_EXECUTE, {"i": i})
            results = trail.query(limit=2)
            assert len(results) == 2

    def test_query_limit_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with pytest.raises(ValueError):
                trail.query(limit=0)

    def test_query_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            results = trail.query()
            assert results == []

    def test_query_by_trace_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {}, trace_id="abc")
            trail.record(AuditEventType.TASK_COMPLETE, {}, trace_id="abc")
            trail.record(AuditEventType.TASK_EXECUTE, {}, trace_id="xyz")
            results = trail.query_by_trace_id("abc")
            assert len(results) == 2

    def test_query_by_trace_id_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            results = trail.query_by_trace_id("none")
            assert results == []


class TestAuditTrailIntegrity:
    """测试完整性校验"""

    def test_verify_integrity_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            assert trail.verify_integrity() is True

    def test_verify_integrity_after_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            trail.record(AuditEventType.TASK_COMPLETE, {})
            assert trail.verify_integrity() is True

    def test_verify_integrity_tampered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            # 篡改文件
            with open(trail._audit_file, "r+") as f:
                content = f.read()
                content = content.replace("TASK_EXECUTE", "TAMPERED")
                f.seek(0)
                f.write(content)
                f.truncate()
            assert trail.verify_integrity() is False


class TestAuditTrailStats:
    """测试统计功能"""

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {}, severity=AuditLevel.INFO)
            trail.record(AuditEventType.SAFETY_VIOLATION, {}, severity=AuditLevel.WARNING)
            stats = trail.get_stats()
            assert stats["total_records"] == 2
            assert stats["by_type"]["TASK_EXECUTE"] == 1
            assert stats["by_severity"]["warning"] == 1
            assert stats["integrity_ok"] is True


class TestAuditTrailExport:
    """测试导出功能"""

    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            output = os.path.join(tmpdir, "export.jsonl")
            count = trail.export_to_file(output)
            assert count == 1
            assert os.path.exists(output)

    def test_export_with_time_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            before = time.time()
            trail.record(AuditEventType.TASK_EXECUTE, {})
            after = time.time()
            output = os.path.join(tmpdir, "export.jsonl")
            count = trail.export_to_file(output, start_time=before, end_time=after)
            assert count == 1


class TestAuditTrailTraceContext:
    """测试Trace上下文"""

    def test_generate_trace_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            tid = trail.generate_trace_id()
            assert len(tid) == 8
            assert trail.get_trace_id() == tid

    def test_set_trace_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.set_trace_id("custom")
            assert trail.get_trace_id() == "custom"

    def test_set_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.set_cycle(42)
            trail.record(AuditEventType.CYCLE_START, {})
            records = trail.query()
            assert records[0].cycle == 42


class TestAuditTrailListeners:
    """测试监听器管理"""

    def test_add_remove_listener(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            listener = lambda r: None
            trail.add_listener(listener)
            trail.remove_listener(listener)
            assert listener not in trail._listeners

    def test_remove_nonexistent_listener(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            listener = lambda r: None
            trail.remove_listener(listener)


class TestAuditTrailRotation:
    """测试日志轮转"""

    def test_no_rotation_when_small(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            result = trail.rotate_if_needed(max_size_mb=10.0)
            assert result is None

    def test_rotation_when_large(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            large_data = "x" * 1024 * 1024
            trail.record(AuditEventType.TASK_EXECUTE, {"data": large_data})
            result = trail.rotate_if_needed(max_size_mb=0.5)
            assert result is not None
            assert result.exists()

    def test_rotation_creates_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            large_data = "x" * 1024 * 1024
            trail.record(AuditEventType.TASK_EXECUTE, {"data": large_data})
            trail.rotate_if_needed(max_size_mb=0.5)
            assert trail._audit_file.exists()
            assert trail._audit_file.stat().st_size < 100


class TestAuditTrailBatchQuery:
    """测试批量查询"""

    def test_batch_query_by_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            trail.record(AuditEventType.TASK_COMPLETE, {})
            trail.record(AuditEventType.SAFETY_VIOLATION, {})
            results = trail.query_batch(
                event_types=[AuditEventType.TASK_EXECUTE, AuditEventType.TASK_COMPLETE],
                limit=10,
            )
            assert len(results) == 2

    def test_batch_query_by_severities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {}, severity=AuditLevel.INFO)
            trail.record(AuditEventType.SAFETY_VIOLATION, {}, severity=AuditLevel.WARNING)
            trail.record(AuditEventType.TASK_FAIL, {}, severity=AuditLevel.ERROR)
            results = trail.query_batch(
                severities=[AuditLevel.WARNING, AuditLevel.ERROR],
                limit=10,
            )
            assert len(results) == 2

    def test_batch_query_empty_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            results = trail.query_batch(event_types=[], limit=10)
            assert len(results) == 1

    def test_batch_query_limit_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with pytest.raises(ValueError):
                trail.query_batch(limit=0)

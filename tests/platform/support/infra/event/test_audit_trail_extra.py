"""
审计追踪系统边界补充测试

覆盖缺失分支：_load_last_hash异常路径、查询JSONDecodeError、统计异常路径
"""

import json
import os
import tempfile

import pytest

from src.platform.support.infra.event.audit_trail import (
    AuditTrail, AuditRecord, AuditEventType, AuditLevel,
)


class TestLoadLastHashEdgeCases:
    """测试加载最后哈希边界"""

    def test_load_last_hash_empty_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            # 创建空文件
            open(trail._audit_file, "w").close()
            assert trail._load_last_hash() == "0" * 16

    def test_load_last_hash_corrupted_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with open(trail._audit_file, "w") as f:
                f.write("not json\n")
            assert trail._load_last_hash() == "0" * 16

    def test_load_last_hash_missing_record_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            with open(trail._audit_file, "w") as f:
                f.write(json.dumps({"event_type": "TEST"}) + "\n")
            assert trail._load_last_hash() == "0" * 16


class TestQueryCorruptedLines:
    """测试查询时遇到损坏行"""

    def test_query_skips_corrupted_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            with open(trail._audit_file, "a") as f:
                f.write("corrupted line\n")
            results = trail.query()
            assert len(results) == 1

    def test_query_by_trace_id_skips_corrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {}, trace_id="abc")
            with open(trail._audit_file, "a") as f:
                f.write("bad json\n")
            results = trail.query_by_trace_id("abc")
            assert len(results) == 1


class TestVerifyIntegrityCorrupted:
    """测试完整性校验遇到损坏行"""

    def test_verify_skips_corrupted_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            with open(trail._audit_file, "a") as f:
                f.write("not json\n")
            assert trail.verify_integrity() is True


class TestStatsCorruptedLines:
    """测试统计时遇到损坏行"""

    def test_get_stats_skips_corrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            trail.record(AuditEventType.TASK_EXECUTE, {})
            with open(trail._audit_file, "a") as f:
                f.write("corrupted\n")
            stats = trail.get_stats()
            assert stats["total_records"] == 1


class TestExportEmpty:
    """测试导出空结果"""

    def test_export_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            output = os.path.join(tmpdir, "export.jsonl")
            count = trail.export_to_file(output)
            assert count == 0
            assert os.path.exists(output)


class TestRecordHashChain:
    """测试哈希链连续性"""

    def test_hash_chain_continuity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(audit_dir=tmpdir)
            rid1 = trail.record(AuditEventType.TASK_EXECUTE, {})
            rid2 = trail.record(AuditEventType.TASK_COMPLETE, {})
            records = trail.query(limit=2)
            # 第二条记录的prev_hash应等于第一条的record_hash
            assert records[0].prev_hash == records[1].record_hash

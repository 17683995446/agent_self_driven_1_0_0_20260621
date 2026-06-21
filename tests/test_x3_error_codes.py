"""
X3：错误码体系接入测试

验证错误码体系接入实际错误路径：
1. ConfigLoader 错误路径使用 ErrorCode + ValidationError（H1）
2. main.py _handle_cycle_error 按错误码分类处理
3. 不同错误类别有不同退避策略
4. 错误日志和事件携带错误码

第一性原理：错误必须可识别、可检索、可分类处理
"""

import pytest
import os
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.platform.lifecycle.memory.config_loader import ConfigLoader
from src.platform.support.models.base.error_code import ErrorCode, ValidationError


class TestX3ErrorCodeEnum:
    """测试错误码枚举完整性"""

    def test_error_code_has_code_and_message_key(self):
        """每个错误码有 code 和 message_key"""
        for ec in ErrorCode:
            assert isinstance(ec.code, int)
            assert isinstance(ec.message_key, str)
            assert ec.code > 0 or ec == ErrorCode.SUCCESS

    def test_config_not_found_code(self):
        """CONFIG_NOT_FOUND 错误码"""
        assert ErrorCode.CONFIG_NOT_FOUND.code == 200003
        assert ErrorCode.CONFIG_NOT_FOUND.message_key == "config_not_found"

    def test_parameter_range_error_code(self):
        """PARAMETER_RANGE_ERROR 错误码"""
        assert ErrorCode.PARAMETER_RANGE_ERROR.code == 100004
        assert ErrorCode.PARAMETER_RANGE_ERROR.message_key == "parameter_range_error"

    def test_error_codes_are_unique(self):
        """所有错误码唯一"""
        codes = [ec.code for ec in ErrorCode]
        assert len(codes) == len(set(codes)), "错误码存在重复"


class TestX3ValidationError:
    """测试 ValidationError 异常类"""

    def test_validation_error_stores_error_code(self):
        """ValidationError 存储 error_code"""
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="missing")
        assert err.error_code == ErrorCode.CONFIG_NOT_FOUND

    def test_validation_error_stores_field(self):
        """ValidationError 存储 field"""
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="config_path", detail="missing")
        assert err.field == "config_path"

    def test_validation_error_stores_detail(self):
        """ValidationError 存储 detail"""
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="file missing")
        assert err.detail == "file missing"

    def test_validation_error_message_contains_code(self):
        """异常消息包含错误码"""
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="missing")
        assert str(ErrorCode.CONFIG_NOT_FOUND.code) in str(err)

    def test_validation_error_message_contains_field(self):
        """异常消息包含字段名"""
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="my_field", detail="missing")
        assert "my_field" in str(err)

    def test_validation_error_is_exception(self):
        """ValidationError 是 Exception 子类"""
        assert issubclass(ValidationError, Exception)


class TestX3ConfigLoaderErrorCodes:
    """测试 ConfigLoader 错误路径接入错误码"""

    def test_missing_config_uses_config_not_found(self, tmp_path):
        """配置不存在使用 CONFIG_NOT_FOUND 错误码"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.CONFIG_NOT_FOUND

    def test_invalid_cpu_uses_parameter_range_error(self, tmp_path):
        """无效CPU值使用 PARAMETER_RANGE_ERROR 错误码"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_invalid_memory_uses_parameter_range_error(self, tmp_path):
        """无效内存值使用 PARAMETER_RANGE_ERROR 错误码"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_memory_usage: -1.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_invalid_exploration_uses_parameter_range_error(self, tmp_path):
        """无效探索比例使用 PARAMETER_RANGE_ERROR 错误码"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("decision:\n  base_exploration_ratio: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_config_not_found_field_is_config_path(self, tmp_path):
        """CONFIG_NOT_FOUND 的 field 为 config_path"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.field == "config_path"

    def test_invalid_cpu_field_is_max_cpu_usage(self, tmp_path):
        """无效CPU的 field 为 guardrail.max_cpu_usage"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.field == "guardrail.max_cpu_usage"


class TestX3HandleCycleErrorClassification:
    """测试 main.py _handle_cycle_error 按错误码分类处理"""

    def _make_system(self):
        """创建最小化 AgentSystem 实例（绕过完整初始化）"""
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 0
        system.event_bus = MagicMock()
        return system

    def test_extract_error_info_from_validation_error(self):
        """从 ValidationError 提取错误码信息"""
        system = self._make_system()
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="missing")
        info = system._extract_error_info(err)
        assert info["has_code"] is True
        assert info["code"] == 200003
        assert info["message_key"] == "config_not_found"
        assert info["field"] == "path"
        assert info["category"] == 2

    def test_extract_error_info_from_generic_exception(self):
        """从普通异常提取信息（无错误码）"""
        system = self._make_system()
        err = ValueError("something wrong")
        info = system._extract_error_info(err)
        assert info["has_code"] is False
        assert info["category"] == 0

    def test_extract_error_info_category_for_resource_error(self):
        """资源类错误 category 为 3"""
        system = self._make_system()
        err = ValidationError(ErrorCode.RESOURCE_CPU_EXCEEDED, field="cpu", detail="over")
        info = system._extract_error_info(err)
        assert info["category"] == 3

    def test_extract_error_info_category_for_task_error(self):
        """任务类错误 category 为 5"""
        system = self._make_system()
        err = ValidationError(ErrorCode.TASK_EXECUTE_FAILED, field="task", detail="fail")
        info = system._extract_error_info(err)
        assert info["category"] == 5

    def test_compute_backoff_for_config_error(self):
        """配置类错误退避 5 秒"""
        system = self._make_system()
        info = {"has_code": True, "category": 2}
        assert system._compute_error_backoff(info) == 5.0

    def test_compute_backoff_for_resource_error(self):
        """资源类错误退避 3 秒"""
        system = self._make_system()
        info = {"has_code": True, "category": 3}
        assert system._compute_error_backoff(info) == 3.0

    def test_compute_backoff_for_task_error(self):
        """任务类错误退避 0.5 秒"""
        system = self._make_system()
        info = {"has_code": True, "category": 5}
        assert system._compute_error_backoff(info) == 0.5

    def test_compute_backoff_for_unknown_error(self):
        """未知错误退避 1 秒"""
        system = self._make_system()
        info = {"has_code": False, "category": 0}
        assert system._compute_error_backoff(info) == 1.0


class TestX3HandleCycleErrorLogging:
    """测试 _handle_cycle_error 的日志和事件发布"""

    def _make_system(self):
        from src.main import AgentSystem
        system = object.__new__(AgentSystem)
        system.cycle_count = 42
        system.event_bus = MagicMock()
        return system

    def test_log_cycle_error_includes_code_for_validation_error(self, caplog):
        """ValidationError 的日志包含错误码"""
        system = self._make_system()
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="missing")
        info = system._extract_error_info(err)
        with caplog.at_level(logging.ERROR):
            system._log_cycle_error(err, info)
        assert "200003" in caplog.text
        assert "config_not_found" in caplog.text

    def test_log_cycle_error_for_generic_exception(self, caplog):
        """普通异常的日志不包含错误码"""
        system = self._make_system()
        err = ValueError("boom")
        info = system._extract_error_info(err)
        with caplog.at_level(logging.ERROR):
            system._log_cycle_error(err, info)
        assert "Cycle error" in caplog.text
        assert "boom" in caplog.text

    def test_publish_cycle_error_includes_code_for_validation_error(self):
        """ValidationError 的事件 payload 包含错误码"""
        system = self._make_system()
        err = ValidationError(ErrorCode.RESOURCE_CPU_EXCEEDED, field="cpu", detail="over")
        info = system._extract_error_info(err)
        system._publish_cycle_error(err, info)
        system.event_bus.publish_simple.assert_called_once()
        call_kwargs = system.event_bus.publish_simple.call_args
        payload = call_kwargs.kwargs.get("payload") or call_kwargs[1].get("payload")
        assert payload["error_code"] == 300001
        assert payload["error_key"] == "resource_cpu_exceeded"
        assert payload["error_field"] == "cpu"

    def test_publish_cycle_error_for_generic_exception(self):
        """普通异常的事件 payload 不包含错误码字段"""
        system = self._make_system()
        err = ValueError("boom")
        info = system._extract_error_info(err)
        system._publish_cycle_error(err, info)
        call_kwargs = system.event_bus.publish_simple.call_args
        payload = call_kwargs.kwargs.get("payload") or call_kwargs[1].get("payload")
        assert "error" in payload
        assert "error_code" not in payload

    def test_handle_cycle_error_calls_sleep_with_backoff(self):
        """_handle_cycle_error 按错误类别 sleep"""
        system = self._make_system()
        err = ValidationError(ErrorCode.CONFIG_NOT_FOUND, field="path", detail="missing")
        with patch("src.main.time.sleep") as mock_sleep:
            system._handle_cycle_error(err)
        mock_sleep.assert_called_once_with(5.0)

    def test_handle_cycle_error_generic_sleeps_1s(self):
        """_handle_cycle_error 普通异常 sleep 1 秒"""
        system = self._make_system()
        err = ValueError("boom")
        with patch("src.main.time.sleep") as mock_sleep:
            system._handle_cycle_error(err)
        mock_sleep.assert_called_once_with(1.0)


class TestX3ErrorCodesAreImportedInMain:
    """测试 main.py 正确导入错误码体系"""

    def test_main_imports_validation_error(self):
        """main.py 导入 ValidationError"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "ValidationError" in content
        assert "from src.platform.support.models.base.error_code" in content

    def test_main_imports_error_code(self):
        """main.py 导入 ErrorCode"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "ErrorCode" in content

    def test_handle_cycle_error_uses_extract_error_info(self):
        """_handle_cycle_error 调用 _extract_error_info"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _handle_cycle_error\(self.*?error.*?\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_handle_cycle_error method not found"
        body = match.group()
        assert "_extract_error_info" in body
        assert "_compute_error_backoff" in body

    def test_extract_error_info_checks_validation_error(self):
        """_extract_error_info 检查 isinstance ValidationError"""
        content = (PROJECT_ROOT / "src" / "main.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _extract_error_info\(self.*?\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_extract_error_info method not found"
        body = match.group()
        assert "isinstance" in body
        assert "ValidationError" in body

"""
错误码枚举测试

验证错误码定义的正确性
"""

import pytest

from src.platform.support.models.base.error_code import ErrorCode


class TestErrorCode:
    """测试错误码枚举"""

    def test_success_code(self):
        assert ErrorCode.SUCCESS.code == 0
        assert ErrorCode.SUCCESS.message_key == "success"

    def test_invalid_parameter_code(self):
        assert ErrorCode.INVALID_PARAMETER.code == 100001
        assert ErrorCode.INVALID_PARAMETER.message_key == "invalid_parameter"

    def test_tuple_property(self):
        code_tuple = ErrorCode.MISSING_PARAMETER.tuple
        assert code_tuple == (100002, "missing_parameter")

    def test_all_codes_unique(self):
        codes = [e.code for e in ErrorCode]
        assert len(codes) == len(set(codes))

    def test_all_messages_unique(self):
        messages = [e.message_key for e in ErrorCode]
        assert len(messages) == len(set(messages))

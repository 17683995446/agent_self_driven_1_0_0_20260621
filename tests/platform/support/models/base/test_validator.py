"""
参数校验模块测试

验证参数校验器的正确性，包含四类用例：
- 正常值入参
- 空入参
- 边界极值入参
- 非法格式入参
"""

import pytest

from src.platform.support.models.base.error_code import ParameterValidator, ValidationError
from src.platform.support.models.base.error_code import ErrorCode


class TestValidateNotNull:
    """测试非空校验"""

    def test_normal_value(self):
        ParameterValidator.validate_not_null("test", "field")

    def test_empty_string(self):
        ParameterValidator.validate_not_null("", "field")

    def test_null_value(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_not_null(None, "field")
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER


class TestValidateStringLength:
    """测试字符串长度校验"""

    def test_normal_string(self):
        ParameterValidator.validate_string_length("hello", "field", 1, 10)

    def test_boundary_min(self):
        ParameterValidator.validate_string_length("a", "field", 1, 10)

    def test_boundary_max(self):
        ParameterValidator.validate_string_length("a" * 10, "field", 1, 10)

    def test_null_string(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_string_length(None, "field", 1, 10)
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER

    def test_invalid_type(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_string_length(123, "field", 1, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_TYPE_ERROR

    def test_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_string_length("", "field", 1, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_string_length("a" * 11, "field", 1, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR


class TestValidateNumberRange:
    """测试数值范围校验"""

    def test_normal_number(self):
        ParameterValidator.validate_number_range(5, "field", 0, 10)

    def test_boundary_min(self):
        ParameterValidator.validate_number_range(0, "field", 0, 10)

    def test_boundary_max(self):
        ParameterValidator.validate_number_range(10, "field", 0, 10)

    def test_null_number(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_number_range(None, "field", 0, 10)
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER

    def test_invalid_type(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_number_range("five", "field", 0, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_TYPE_ERROR

    def test_below_min(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_number_range(-1, "field", 0, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_above_max(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_number_range(11, "field", 0, 10)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR


class TestValidateInEnum:
    """测试枚举值校验"""

    def test_valid_value(self):
        ParameterValidator.validate_in_enum("a", "field", ["a", "b", "c"])

    def test_null_value(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_in_enum(None, "field", ["a", "b"])
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER

    def test_invalid_value(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_in_enum("d", "field", ["a", "b", "c"])
        assert exc_info.value.error_code == ErrorCode.PARAMETER_FORMAT_ERROR


class TestValidateDictKeys:
    """测试字典键校验"""

    def test_valid_dict(self):
        ParameterValidator.validate_dict_keys({"a": 1, "b": 2}, "field", ["a"])

    def test_null_dict(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_dict_keys(None, "field", ["a"])
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER

    def test_invalid_type(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_dict_keys("not_dict", "field", ["a"])
        assert exc_info.value.error_code == ErrorCode.PARAMETER_TYPE_ERROR

    def test_missing_key(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_dict_keys({"a": 1}, "field", ["a", "b"])
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER


class TestValidateListLength:
    """测试列表长度校验"""

    def test_valid_list(self):
        ParameterValidator.validate_list_length([1, 2, 3], "field", 1, 5)

    def test_boundary_min(self):
        ParameterValidator.validate_list_length([1], "field", 1, 5)

    def test_boundary_max(self):
        ParameterValidator.validate_list_length([1, 2, 3, 4, 5], "field", 1, 5)

    def test_null_list(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_list_length(None, "field", 1, 5)
        assert exc_info.value.error_code == ErrorCode.MISSING_PARAMETER

    def test_invalid_type(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_list_length("not_list", "field", 1, 5)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_TYPE_ERROR

    def test_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_list_length([], "field", 1, 5)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            ParameterValidator.validate_list_length([1, 2, 3, 4, 5, 6], "field", 1, 5)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

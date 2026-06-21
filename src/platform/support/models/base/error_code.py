"""
全局错误码枚举与参数校验

第一性原理：错误码必须统一、固定、可追踪；所有接口入参必须强制完成参数强校验
- 禁止自定义返回码
- 禁止自定义提示文案
- 所有提示文本统一从配置文件读取
- 校验范围包含非空、字段长度、数值范围、数据格式
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ErrorCode(Enum):
    """全局错误码枚举"""
    SUCCESS = (0, "success")
    INVALID_PARAMETER = (100001, "invalid_parameter")
    MISSING_PARAMETER = (100002, "missing_parameter")
    PARAMETER_TYPE_ERROR = (100003, "parameter_type_error")
    PARAMETER_RANGE_ERROR = (100004, "parameter_range_error")
    PARAMETER_FORMAT_ERROR = (100005, "parameter_format_error")

    SYSTEM_INTERNAL_ERROR = (200001, "system_internal_error")
    CONFIG_LOAD_ERROR = (200002, "config_load_error")
    CONFIG_NOT_FOUND = (200003, "config_not_found")
    CONFIG_VALIDATE_ERROR = (200004, "config_validate_error")

    RESOURCE_CPU_EXCEEDED = (300001, "resource_cpu_exceeded")
    RESOURCE_MEMORY_EXCEEDED = (300002, "resource_memory_exceeded")
    RESOURCE_DISK_EXCEEDED = (300003, "resource_disk_exceeded")
    RESOURCE_LIMIT_VIOLATION = (300004, "resource_limit_violation")

    SAFETY_VIOLATION = (400001, "safety_violation")
    FORBIDDEN_OPERATION = (400002, "forbidden_operation")
    EXPLORATION_STOPPED = (400003, "exploration_stopped")

    TASK_EXECUTE_FAILED = (500001, "task_execute_failed")
    TASK_TIMEOUT = (500002, "task_timeout")
    TASK_CANCELLED = (500003, "task_cancelled")
    TASK_NO_FUNCTION = (500004, "task_no_function")

    SNAPSHOT_CREATE_FAILED = (600001, "snapshot_create_failed")
    SNAPSHOT_ROLLBACK_FAILED = (600002, "snapshot_rollback_failed")
    SNAPSHOT_NOT_FOUND = (600003, "snapshot_not_found")

    PREDICTION_ERROR = (700001, "prediction_error")
    MODEL_UPDATE_FAILED = (700002, "model_update_failed")

    MEMORY_STORE_FAILED = (800001, "memory_store_failed")
    MEMORY_RETRIEVE_FAILED = (800002, "memory_retrieve_failed")

    HEALTH_CHECK_FAILED = (900001, "health_check_failed")
    HEALING_FAILED = (900002, "healing_failed")

    def __init__(self, code: int, message_key: str) -> None:
        self.code = code
        self.message_key = message_key

    @property
    def tuple(self) -> tuple:
        return (self.code, self.message_key)


class ValidationError(Exception):
    """参数校验异常"""

    def __init__(self, error_code: ErrorCode, field: str = "", detail: str = "") -> None:
        self.error_code = error_code
        self.field = field
        self.detail = detail
        super().__init__(f"[{error_code.code}] {field}: {detail}")


class ParameterValidator:
    """参数校验器"""

    @staticmethod
    def validate_not_null(value: Any, field_name: str) -> None:
        """校验非空"""
        if value is None:
            raise ValidationError(
                ErrorCode.MISSING_PARAMETER,
                field_name,
                "parameter cannot be null",
            )

    @staticmethod
    def _validate_string_type(value: Any, field_name: str) -> None:
        """验证是否为字符串类型"""
        if not isinstance(value, str):
            raise ValidationError(
                ErrorCode.PARAMETER_TYPE_ERROR,
                field_name,
                f"expected str, got {type(value).__name__}",
            )

    @staticmethod
    def _validate_min_length(value: str, min_length: int, field_name: str) -> None:
        """验证最小长度"""
        if len(value) < min_length:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"length {len(value)} < min {min_length}",
            )

    @staticmethod
    def _validate_max_length(value: str, max_length: int, field_name: str) -> None:
        """验证最大长度"""
        if len(value) > max_length:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"length {len(value)} > max {max_length}",
            )

    @staticmethod
    def validate_string_length(
        value: str,
        field_name: str,
        min_length: int = 1,
        max_length: int = 255,
    ) -> None:
        """校验字符串长度"""
        ParameterValidator.validate_not_null(value, field_name)
        ParameterValidator._validate_string_type(value, field_name)
        if min_length is not None:
            ParameterValidator._validate_min_length(value, min_length, field_name)
        if max_length is not None:
            ParameterValidator._validate_max_length(value, max_length, field_name)

    @staticmethod
    def _validate_number_type(value: Any, field_name: str) -> None:
        """验证是否为数值类型"""
        if not isinstance(value, (int, float)):
            raise ValidationError(
                ErrorCode.PARAMETER_TYPE_ERROR,
                field_name,
                f"expected number, got {type(value).__name__}",
            )

    @staticmethod
    def _validate_min_value(value: Union[int, float], min_value: float, field_name: str) -> None:
        """验证最小值"""
        if value < min_value:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"value {value} < min {min_value}",
            )

    @staticmethod
    def _validate_max_value(value: Union[int, float], max_value: float, field_name: str) -> None:
        """验证最大值"""
        if value > max_value:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"value {value} > max {max_value}",
            )

    @staticmethod
    def validate_number_range(
        value: Union[int, float],
        field_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> None:
        """校验数值范围"""
        ParameterValidator.validate_not_null(value, field_name)
        ParameterValidator._validate_number_type(value, field_name)
        if min_value is not None:
            ParameterValidator._validate_min_value(value, min_value, field_name)
        if max_value is not None:
            ParameterValidator._validate_max_value(value, max_value, field_name)

    @staticmethod
    def validate_in_enum(
        value: Any,
        field_name: str,
        allowed_values: List[Any],
    ) -> None:
        """校验枚举值"""
        ParameterValidator.validate_not_null(value, field_name)
        if value not in allowed_values:
            raise ValidationError(
                ErrorCode.PARAMETER_FORMAT_ERROR,
                field_name,
                f"value {value} not in {allowed_values}",
            )

    @staticmethod
    def _validate_dict_type(value: Any, field_name: str) -> None:
        """验证是否为字典类型"""
        if not isinstance(value, dict):
            raise ValidationError(
                ErrorCode.PARAMETER_TYPE_ERROR,
                field_name,
                f"expected dict, got {type(value).__name__}",
            )

    @staticmethod
    def _validate_required_keys(value: Dict, field_name: str, required_keys: List[str]) -> None:
        """验证必填键是否存在"""
        for key in required_keys:
            if key not in value:
                raise ValidationError(
                    ErrorCode.MISSING_PARAMETER,
                    f"{field_name}.{key}",
                    "required key missing",
                )

    @staticmethod
    def validate_dict_keys(
        value: Dict,
        field_name: str,
        required_keys: List[str],
    ) -> None:
        """校验字典必填键"""
        ParameterValidator.validate_not_null(value, field_name)
        ParameterValidator._validate_dict_type(value, field_name)
        ParameterValidator._validate_required_keys(value, field_name, required_keys)

    @staticmethod
    def _validate_list_type(value: Any, field_name: str) -> None:
        """验证是否为列表类型"""
        if not isinstance(value, list):
            raise ValidationError(
                ErrorCode.PARAMETER_TYPE_ERROR,
                field_name,
                f"expected list, got {type(value).__name__}",
            )

    @staticmethod
    def _validate_list_min_length(value: List, min_length: int, field_name: str) -> None:
        """验证列表最小长度"""
        if len(value) < min_length:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"length {len(value)} < min {min_length}",
            )

    @staticmethod
    def _validate_list_max_length(value: List, max_length: int, field_name: str) -> None:
        """验证列表最大长度"""
        if len(value) > max_length:
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field_name,
                f"length {len(value)} > max {max_length}",
            )

    @staticmethod
    def validate_list_length(
        value: List,
        field_name: str,
        min_length: int = 0,
        max_length: Optional[int] = None,
    ) -> None:
        """校验列表长度"""
        ParameterValidator.validate_not_null(value, field_name)
        ParameterValidator._validate_list_type(value, field_name)
        ParameterValidator._validate_list_min_length(value, min_length, field_name)
        if max_length is not None:
            ParameterValidator._validate_list_max_length(value, max_length, field_name)

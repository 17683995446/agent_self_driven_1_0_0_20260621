"""
X2：静默回退消除测试

验证配置问题显式失败而非静默继续：
1. 配置文件不存在时抛出 ValidationError(CONFIG_NOT_FOUND)（H8）
2. 配置校验失败时抛出带详细信息的 ValidationError(PARAMETER_RANGE_ERROR)（H2）
3. 错误信息包含合法取值范围和修复建议
4. 不再静默回退到默认配置

第一性原理：系统行为必须确定，不能静默回退
X3：异常类型由 FileNotFoundError/ValueError 统一为 ValidationError
"""

import pytest
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspace/self_driven_agent")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.platform.lifecycle.memory.config_loader import ConfigLoader
from src.platform.support.models.base.error_code import ErrorCode, ValidationError


class TestX2ConfigNotFound:
    """测试配置文件不存在的显式失败（H8）"""

    def test_missing_config_raises_validation_error(self, tmp_path):
        """配置文件不存在时抛出 ValidationError（X3：错误码体系）"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError):
            ConfigLoader(config_path=path)

    def test_missing_config_has_config_not_found_code(self, tmp_path):
        """X3：错误码为 CONFIG_NOT_FOUND"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.CONFIG_NOT_FOUND

    def test_error_message_contains_path(self, tmp_path):
        """错误信息包含文件路径"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert path in str(exc_info.value)

    def test_error_message_contains_available_configs(self, tmp_path):
        """错误信息提示可用配置"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "dev.yaml" in msg
        assert "prod.yaml" in msg
        assert "test.yaml" in msg

    def test_error_message_contains_env_var_hint(self, tmp_path):
        """错误信息提示环境变量"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert "AGENT_CONFIG_PATH" in str(exc_info.value)

    def test_error_message_contains_env_option_hint(self, tmp_path):
        """错误信息提示 --env 选项"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert "--env" in str(exc_info.value)

    def test_no_silent_fallback_to_default(self, tmp_path):
        """不静默回退到默认配置"""
        path = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(ValidationError):
            loader = ConfigLoader(config_path=path)
        # 不应返回包含默认配置的对象


class TestX2ConfigValidationFailure:
    """测试配置校验失败的显式错误（H2）"""

    def test_invalid_cpu_raises_with_range(self, tmp_path):
        """无效CPU值抛出异常包含取值范围"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "max_cpu_usage" in msg
        assert "0.01" in msg
        assert "1.0" in msg

    def test_invalid_cpu_has_parameter_range_code(self, tmp_path):
        """X3：无效CPU的错误码为 PARAMETER_RANGE_ERROR"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        assert exc_info.value.error_code == ErrorCode.PARAMETER_RANGE_ERROR

    def test_invalid_memory_raises_with_range(self, tmp_path):
        """无效内存值抛出异常包含取值范围"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_memory_usage: -1.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "max_memory_usage" in msg
        assert "0.01" in msg
        assert "1.0" in msg

    def test_invalid_exploration_raises_with_range(self, tmp_path):
        """无效探索比例抛出异常包含取值范围"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("decision:\n  base_exploration_ratio: 2.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "base_exploration_ratio" in msg
        assert "0.0" in msg
        assert "1.0" in msg

    def test_validation_error_contains_fix_suggestion(self, tmp_path):
        """校验错误包含修复建议"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 5.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "修复建议" in msg or "改为" in msg

    def test_validation_error_contains_example(self, tmp_path):
        """校验错误包含示例"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write("guardrail:\n  max_cpu_usage: 5.0\n")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_path=path)
        msg = str(exc_info.value)
        assert "示例" in msg or "max_cpu_usage:" in msg


class TestX2NoSilentFallback:
    """测试不静默回退"""

    def test_load_with_fallback_not_catching_exceptions(self):
        """_load_with_fallback 不捕获异常"""
        content = (PROJECT_ROOT / "src" / "platform" / "lifecycle" / "memory" / "config_loader.py").read_text(encoding="utf-8")
        # _load_with_fallback 应直接调用 _try_load，不 try/except
        import re
        match = re.search(r'def _load_with_fallback\(self\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_load_with_fallback method not found"
        method_body = match.group()
        assert "try:" not in method_body, "_load_with_fallback 不应 try/except"
        assert "return self._try_load()" in method_body

    def test_handle_load_failure_re_raises(self):
        """_handle_load_failure 重新抛出异常"""
        content = (PROJECT_ROOT / "src" / "platform" / "lifecycle" / "memory" / "config_loader.py").read_text(encoding="utf-8")
        import re
        match = re.search(r'def _handle_load_failure\(self.*?e.*?\).*?(?=\n    def )', content, re.DOTALL)
        assert match, "_handle_load_failure method not found"
        method_body = match.group()
        assert "raise" in method_body, "_handle_load_failure 应重新抛出异常"
        assert "_get_default_config" not in method_body, "不应回退到默认配置"

    def test_load_not_setting_default_on_missing(self):
        """load 方法在文件不存在时抛出 ValidationError 而非回退默认配置（X3）"""
        content = (PROJECT_ROOT / "src" / "platform" / "lifecycle" / "memory" / "config_loader.py").read_text(encoding="utf-8")
        # 查找 ConfigLoader 类（非基类）的 load 方法
        import re
        # 匹配 class ConfigLoader( 之后的内容
        class_match = re.search(r'class ConfigLoader\(ConfigLoaderBase\):(.*?)(?=\nclass |\Z)', content, re.DOTALL)
        assert class_match, "ConfigLoader class not found"
        class_body = class_match.group(1)
        load_match = re.search(r'def load\(self\).*?(?=\n    def )', class_body, re.DOTALL)
        assert load_match, "load method not found in ConfigLoader"
        load_body = load_match.group()
        assert "ValidationError" in load_body, "应抛出 ValidationError"
        assert "CONFIG_NOT_FOUND" in load_body, "应使用 CONFIG_NOT_FOUND 错误码"
        assert "_get_default_config" not in load_body, "不应回退到默认配置"


class TestX2ValidConfigStillWorks:
    """测试有效配置仍正常工作"""

    def test_valid_config_loads_successfully(self, tmp_path):
        """有效配置正常加载"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write(
                "environment: test\n"
                "guardrail:\n"
                "  max_cpu_usage: 0.5\n"
                "  max_memory_usage: 0.5\n"
                "decision:\n"
                "  base_exploration_ratio: 0.3\n"
            )
        loader = ConfigLoader(config_path=path)
        assert loader.get("environment") == "test"
        assert loader.get("guardrail.max_cpu_usage") == 0.5

    def test_boundary_values_accepted(self, tmp_path):
        """边界值被接受"""
        path = str(tmp_path / "config.yaml")
        with open(path, "w") as f:
            f.write(
                "guardrail:\n"
                "  max_cpu_usage: 0.01\n"
                "  max_memory_usage: 1.0\n"
                "decision:\n"
                "  base_exploration_ratio: 0.0\n"
            )
        loader = ConfigLoader(config_path=path)
        assert loader.get("guardrail.max_cpu_usage") == 0.01
        assert loader.get("guardrail.max_memory_usage") == 1.0
        assert loader.get("decision.base_exploration_ratio") == 0.0

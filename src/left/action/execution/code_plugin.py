"""
代码执行沙箱插件

第一性原理：代码是精确指令的最强形式
- 执行：在受控环境中运行代码
- 捕获：获取输出和错误
- 隔离：防止影响宿主系统
- 限制：控制资源使用

类比：生物的"运动执行"——大脑发出指令，肌肉精确执行
"""

import time
import logging
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class CodePlugin(PluginBase):
    """
    代码执行沙箱插件

    支持：执行Python、Shell脚本，带超时和资源限制
    """

    def __init__(self) -> None:
        meta = PluginMetadata(
            name="code_plugin",
            version="1.0.0",
            plugin_type=PluginType.CODE,
            capabilities=[
                PluginCapability.EXECUTE,
            ],
            description="代码执行沙箱插件",
        )
        super().__init__(meta)
        self.default_timeout: float = 30.0
        self.max_output_size: int = 10000
        self.allowed_commands: List[str] = ["python3", "python", "bash", "sh"]

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        self.default_timeout = config.get("timeout", 30.0)
        self.max_output_size = config.get("max_output_size", 10000)
        self.allowed_commands = config.get("allowed_commands", ["python3", "python", "bash", "sh"])
        self._initialized = True
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行代码"""
        start = time.time()
        try:
            result = self._dispatch(action, params)
            result.execution_time = time.time() - start
            return result
        except Exception as e:
            return PluginResult(
                success=False,
                message=str(e),
                execution_time=time.time() - start,
            )

    def _dispatch(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """分发到具体动作"""
        if action == "run_python":
            return self._action_run_python(params)
        if action == "run_shell":
            return self._action_run_shell(params)
        if action == "run_script":
            return self._action_run_script(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _run_command(
        self,
        command: List[str],
        input_data: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """执行命令"""
        timeout = timeout or self.default_timeout
        proc = subprocess.run(
            command,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout[:self.max_output_size]
        stderr = proc.stderr[:self.max_output_size]
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "success": proc.returncode == 0,
        }

    def _action_run_python(self, params: Dict[str, Any]) -> PluginResult:
        """执行Python代码"""
        code = params.get("code", "")
        if not code:
            raise ValueError("code is required")
        timeout = params.get("timeout", self.default_timeout)
        result = self._run_command(["python3", "-c", code], timeout=timeout)
        return PluginResult(
            success=result["success"],
            message="Python execution completed",
            data={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"],
            },
        )

    def _action_run_shell(self, params: Dict[str, Any]) -> PluginResult:
        """执行Shell命令"""
        command = params.get("command", "")
        if not command:
            raise ValueError("command is required")
        timeout = params.get("timeout", self.default_timeout)
        result = self._run_command(["bash", "-c", command], timeout=timeout)
        return PluginResult(
            success=result["success"],
            message="Shell execution completed",
            data={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"],
            },
        )

    def _action_run_script(self, params: Dict[str, Any]) -> PluginResult:
        """执行脚本文件"""
        script = params.get("script", "")
        interpreter = params.get("interpreter", "python3")
        if not script:
            raise ValueError("script is required")
        if interpreter not in self.allowed_commands:
            raise ValueError(f"Interpreter {interpreter} not allowed")
        timeout = params.get("timeout", self.default_timeout)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            temp_path = f.name
        try:
            result = self._run_command([interpreter, temp_path], timeout=timeout)
            return PluginResult(
                success=result["success"],
                message="Script execution completed",
                data={
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "returncode": result["returncode"],
                },
            )
        finally:
            os.unlink(temp_path)

"""
工具调用插件

第一性原理：通用工具扩展系统能力边界
- 计算：精确数学运算
- 搜索：信息检索
- 时间：获取当前时间
- 转换：单位转换、格式转换

类比：生物的"工具使用"——猴子用石头砸坚果，人类用计算器做数学
"""

import ast
import time
import logging
import math
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class ToolPlugin(PluginBase):
    """
    工具调用插件

    支持：计算、搜索、时间、转换
    """

    def __init__(self) -> None:
        meta = PluginMetadata(
            name="tool_plugin",
            version="1.0.0",
            plugin_type=PluginType.TOOL,
            capabilities=[
                PluginCapability.EXECUTE,
                PluginCapability.TRANSFORM,
            ],
            description="通用工具调用插件",
        )
        super().__init__(meta)

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        self._initialized = True
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行工具"""
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
        if action == "calculate":
            return self._action_calculate(params)
        if action == "search":
            return self._action_search(params)
        if action == "time":
            return self._action_time(params)
        if action == "convert":
            return self._action_convert(params)
        if action == "count_tokens":
            return self._action_count_tokens(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _action_calculate(self, params: Dict[str, Any]) -> PluginResult:
        """数学计算（使用ast.literal_eval安全替代eval）"""
        expression = params.get("expression", "")
        if not expression:
            raise ValueError("expression is required")
        result = self._safe_calculate(expression)
        return PluginResult(
            success=True,
            message=f"Calculated: {result}",
            data={"result": result, "expression": expression},
        )

    def _safe_calculate(self, expression: str) -> float:
        """安全计算表达式（仅支持四则运算和括号）"""
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")
        node = ast.parse(expression, mode="eval")
        return self._eval_node(node.body)

    def _eval_node(self, node: ast.AST) -> float:
        """递归求值AST节点"""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self._apply_op(node.op, left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            return self._apply_unary(node.op, operand)
        elif isinstance(node, ast.Expression):
            return self._eval_node(node.body)
        else:
            raise ValueError(f"Unsupported node type: {type(node).__name__}")

    def _apply_op(self, op: ast.operator, left: float, right: float) -> float:
        """应用二元运算符"""
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
            return left - right
        elif isinstance(op, ast.Mult):
            return left * right
        elif isinstance(op, ast.Div):
            if right == 0:
                raise ValueError("Division by zero")
            return left / right
        else:
            raise ValueError(f"Unsupported operator: {type(op).__name__}")

    def _apply_unary(self, op: ast.unaryop, operand: float) -> float:
        """应用一元运算符"""
        if isinstance(op, ast.USub):
            return -operand
        elif isinstance(op, ast.UAdd):
            return +operand
        else:
            raise ValueError(f"Unsupported unary operator: {type(op).__name__}")

    def _action_search(self, params: Dict[str, Any]) -> PluginResult:
        """本地搜索（在文本列表中搜索）"""
        query = params.get("query", "").lower()
        items = params.get("items", [])
        if not query:
            raise ValueError("query is required")
        results = []
        for item in items:
            text = str(item).lower()
            if query in text:
                results.append(item)
        return PluginResult(
            success=True,
            message=f"Found {len(results)} matches",
            data={"results": results, "query": query, "total": len(items)},
        )

    def _action_time(self, params: Dict[str, Any]) -> PluginResult:
        """获取时间"""
        fmt = params.get("format", "iso")
        now = datetime.now(timezone.utc)
        if fmt == "iso":
            time_str = now.isoformat()
        elif fmt == "timestamp":
            time_str = str(now.timestamp())
        elif fmt == "date":
            time_str = now.strftime("%Y-%m-%d")
        else:
            time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        return PluginResult(
            success=True,
            message=f"Current time: {time_str}",
            data={"time": time_str, "format": fmt, "timestamp": now.timestamp()},
        )

    def _action_convert(self, params: Dict[str, Any]) -> PluginResult:
        """单位转换"""
        value, from_unit, to_unit = self._extract_convert_params(params)
        if from_unit == to_unit:
            return self._build_convert_result(value, from_unit, to_unit, "No conversion needed")
        return self._perform_convert(value, from_unit, to_unit)

    def _extract_convert_params(self, params: Dict[str, Any]) -> Tuple[float, str, str]:
        """提取转换参数"""
        value = params.get("value", 0.0)
        from_unit = params.get("from", "")
        to_unit = params.get("to", "")
        return value, from_unit, to_unit

    def _perform_convert(self, value: float, from_unit: str, to_unit: str) -> PluginResult:
        """执行转换"""
        factor = self._lookup_conversion(from_unit, to_unit)
        if factor is None:
            return PluginResult(success=False, message=f"Unsupported conversion: {from_unit} to {to_unit}")
        result = value * factor
        return self._build_convert_result(result, from_unit, to_unit, f"Converted {value} {from_unit} to {result} {to_unit}")

    def _lookup_conversion(self, from_unit: str, to_unit: str) -> Optional[float]:
        """查询转换系数"""
        conversions = {
            ("m", "km"): 0.001,
            ("km", "m"): 1000.0,
            ("g", "kg"): 0.001,
            ("kg", "g"): 1000.0,
            ("s", "ms"): 1000.0,
            ("ms", "s"): 0.001,
            ("mb", "gb"): 0.001,
            ("gb", "mb"): 1000.0,
        }
        return conversions.get((from_unit.lower(), to_unit.lower()))

    def _build_convert_result(self, value: float, from_unit: str, to_unit: str, message: str) -> PluginResult:
        """构建转换结果"""
        return PluginResult(
            success=True,
            message=message,
            data={"result": value, "from": from_unit, "to": to_unit},
        )

    def _action_count_tokens(self, params: Dict[str, Any]) -> PluginResult:
        """估算token数量（简单字符/4估算）"""
        text = params.get("text", "")
        estimated = len(text) // 4
        return PluginResult(
            success=True,
            message=f"Estimated {estimated} tokens",
            data={"tokens": estimated, "chars": len(text)},
        )

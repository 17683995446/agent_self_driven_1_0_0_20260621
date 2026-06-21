"""
文件操作插件

第一性原理：文件是信息持久化的最基本形式
- 读：从文件系统获取信息
- 写：将信息持久化到文件系统
- 解析：将文件内容转换为结构化数据

类比：生物的"记忆存储"——将经验写入大脑，需要时读取
"""

import json
import csv
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class FilePlugin(PluginBase):
    """
    文件操作插件

    支持：读文件、写文件、解析JSON、解析CSV、列出目录
    """

    def __init__(self) -> None:
        meta = PluginMetadata(
            name="file_plugin",
            version="1.0.0",
            plugin_type=PluginType.FILE,
            capabilities=[
                PluginCapability.READ,
                PluginCapability.WRITE,
                PluginCapability.TRANSFORM,
            ],
            description="文件读写与解析插件",
        )
        super().__init__(meta)
        self.base_path: Path = Path(".")

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        base = config.get("base_path", ".")
        self.base_path = Path(base)
        self._initialized = True
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self._initialized and self.base_path.exists()

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行文件操作"""
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
        if action == "read":
            return self._action_read(params)
        if action == "write":
            return self._action_write(params)
        if action == "read_json":
            return self._action_read_json(params)
        if action == "write_json":
            return self._action_write_json(params)
        if action == "read_csv":
            return self._action_read_csv(params)
        if action == "list_dir":
            return self._action_list_dir(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _resolve_path(self, params: Dict[str, Any]) -> Path:
        """解析文件路径"""
        path_str = params.get("path", "")
        if not path_str:
            raise ValueError("path is required")
        path = self.base_path / path_str
        return path.resolve()

    def _action_read(self, params: Dict[str, Any]) -> PluginResult:
        """读取文本文件"""
        path = self._resolve_path(params)
        encoding = params.get("encoding", "utf-8")
        content = path.read_text(encoding=encoding)
        return PluginResult(
            success=True,
            message=f"Read {len(content)} chars from {path}",
            data={"content": content, "path": str(path)},
        )

    def _action_write(self, params: Dict[str, Any]) -> PluginResult:
        """写入文本文件"""
        path = self._resolve_path(params)
        content = params.get("content", "")
        encoding = params.get("encoding", "utf-8")
        path.write_text(content, encoding=encoding)
        return PluginResult(
            success=True,
            message=f"Wrote {len(content)} chars to {path}",
            data={"path": str(path), "size": len(content)},
        )

    def _action_read_json(self, params: Dict[str, Any]) -> PluginResult:
        """读取并解析JSON文件"""
        path = self._resolve_path(params)
        encoding = params.get("encoding", "utf-8")
        text = path.read_text(encoding=encoding)
        data = json.loads(text)
        return PluginResult(
            success=True,
            message=f"Parsed JSON from {path}",
            data={"data": data, "path": str(path)},
        )

    def _action_write_json(self, params: Dict[str, Any]) -> PluginResult:
        """写入JSON文件"""
        path = self._resolve_path(params)
        data = params.get("data", {})
        indent = params.get("indent", 2)
        text = json.dumps(data, ensure_ascii=False, indent=indent)
        path.write_text(text, encoding="utf-8")
        return PluginResult(
            success=True,
            message=f"Wrote JSON to {path}",
            data={"path": str(path)},
        )

    def _action_read_csv(self, params: Dict[str, Any]) -> PluginResult:
        """读取并解析CSV文件"""
        path = self._resolve_path(params)
        encoding = params.get("encoding", "utf-8")
        delimiter = params.get("delimiter", ",")
        with path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
        return PluginResult(
            success=True,
            message=f"Parsed {len(rows)} rows from {path}",
            data={"rows": rows, "columns": list(rows[0].keys()) if rows else []},
        )

    def _action_list_dir(self, params: Dict[str, Any]) -> PluginResult:
        """列出目录内容"""
        path = self._resolve_path(params)
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return PluginResult(
            success=True,
            message=f"Listed {len(items)} items in {path}",
            data={"items": items, "path": str(path)},
        )

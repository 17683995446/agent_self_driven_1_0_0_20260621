"""
插件系统模型定义

第一性原理：复杂能力必须模块化、可插拔、可扩展
类比：生物的"器官系统"——心脏只管泵血，肺只管呼吸，各司其职
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time
import uuid


class PluginType(Enum):
    """插件类型"""
    FILE = "file"
    HTTP = "http"
    DATABASE = "database"
    LLM = "llm"
    CODE = "code"
    TOOL = "tool"
    CUSTOM = "custom"


class PluginCapability(Enum):
    """插件能力标签"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    QUERY = "query"
    TRANSFORM = "transform"
    CONNECT = "connect"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    plugin_type: PluginType
    capabilities: List[PluginCapability]
    description: str = ""
    author: str = ""
    config_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResult:
    """插件执行结果"""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class PluginBase(ABC):
    """
    插件抽象基类

    第一性原理：所有复杂能力必须通过统一接口暴露
    """

    def __init__(self, metadata: PluginMetadata) -> None:
        self.metadata = metadata
        self._initialized = False

    @property
    def name(self) -> str:
        return self.metadata.name

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行插件动作"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass

    def shutdown(self) -> None:
        """关闭插件"""
        self._initialized = False


class TaskPluginAdapter:
    """
    任务插件适配器

    将插件适配为任务可执行的函数
    """

    def __init__(self, plugin: PluginBase) -> None:
        self.plugin = plugin

    def create_task_fn(self, action: str, params: Dict[str, Any]) -> Callable[[], PluginResult]:
        """创建任务执行函数"""
        def execute() -> PluginResult:
            return self.plugin.execute(action, params)
        return execute

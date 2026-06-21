"""
插件管理器

第一性原理：复杂能力必须统一管理、动态加载、健康监控
- 注册：插件登记入库
- 加载：按需初始化
- 执行：统一调度
- 监控：健康检查

类比：生物的"器官管理系统"——确保每个器官正常工作
"""

import time
import logging
from typing import Dict, List, Optional, Any, Type
from abc import ABC

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType
)


logger = logging.getLogger(__name__)


class PluginManager:
    """
    插件管理器

    统一管理所有插件的生命周期
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, PluginBase] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._initialized: bool = False

    def initialize(self) -> None:
        """初始化管理器"""
        self._initialized = True
        logger.info("PluginManager initialized")

    def register(self, name: str, plugin: PluginBase, config: Dict[str, Any]) -> bool:
        """注册插件"""
        if name in self._plugins:
            logger.warning(f"Plugin {name} already registered, overwriting")
        self._plugins[name] = plugin
        self._configs[name] = config
        logger.info(f"Plugin {name} registered")
        return True

    def load(self, name: str) -> bool:
        """加载并初始化插件"""
        plugin = self._plugins.get(name)
        if plugin is None:
            logger.error(f"Plugin {name} not found")
            return False
        config = self._configs.get(name, {})
        success = plugin.initialize(config)
        if success:
            logger.info(f"Plugin {name} loaded successfully")
        else:
            logger.error(f"Plugin {name} failed to load")
        return success

    def load_all(self) -> Dict[str, bool]:
        """加载所有插件"""
        results = {}
        for name in self._plugins:
            results[name] = self.load(name)
        return results

    def execute(self, plugin_name: str, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行插件动作"""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return PluginResult(success=False, message=f"Plugin {plugin_name} not found")
        if not plugin._initialized:
            return PluginResult(success=False, message=f"Plugin {plugin_name} not initialized")
        return plugin.execute(action, params)

    def health_check(self, name: str) -> bool:
        """检查插件健康"""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        return plugin.health_check()

    def health_check_all(self) -> Dict[str, bool]:
        """检查所有插件健康"""
        return {name: self.health_check(name) for name in self._plugins}

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """获取插件"""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self._plugins.keys())

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginBase]:
        """按类型获取插件"""
        return [
            p for p in self._plugins.values()
            if p.metadata.plugin_type == plugin_type
        ]

    def shutdown(self, name: str) -> None:
        """关闭插件"""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.shutdown()
            logger.info(f"Plugin {name} shut down")

    def shutdown_all(self) -> None:
        """关闭所有插件"""
        for name in list(self._plugins.keys()):
            self.shutdown(name)

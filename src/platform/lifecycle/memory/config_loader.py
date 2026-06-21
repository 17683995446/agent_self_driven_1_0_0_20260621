"""
配置加载器

第一性原理：配置是系统的"基因"，决定行为边界
类比：生物的"基因表达"——环境触发基因表达，配置决定系统行为
X3：接入错误码体系，错误可识别、可检索
"""

import os
import time
import logging
import threading
import copy
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable

from src.platform.support.models.base.error_code import ErrorCode, ValidationError

try:
    import yaml
except ImportError:
    yaml = None


logger = logging.getLogger(__name__)


class ConfigLoaderBase(ABC):
    """配置加载器抽象基类"""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """加载配置"""
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        pass


class ConfigLoader(ConfigLoaderBase):
    """
    配置加载器

    负责：
    1. 从YAML加载配置
    2. 动态重载配置（热加载）
    3. 配置验证
    4. 配置变更通知
    5. 动态调参

    第一性原理：
    - 配置必须可动态调整
    - 配置变更必须可追踪
    - 无效配置必须被拒绝
    """

    def __init__(self, config_path: str = "./config/dev.yaml") -> None:
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._init_timestamps()
        self._init_reload_state()
        self.load()
        logger.info(f"ConfigLoader initialized: {config_path}")

    def _init_timestamps(self) -> None:
        self.last_load_time = 0.0
        self.last_modified_time = 0.0

    def _init_reload_state(self) -> None:
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._hot_reload_enabled = False
        self._reload_thread: Optional[threading.Thread] = None
        self._reload_interval = 5.0
        self._stop_event = threading.Event()

    def _try_load(self) -> Dict[str, Any]:
        self._load_from_file()
        self._validate_config()
        logger.info(f"Config loaded from {self.config_path}")
        return self.config

    def _handle_load_failure(self, e: Exception) -> Dict[str, Any]:
        """处理加载失败（X2：不再静默回退，抛出异常）"""
        logger.error(f"Failed to load config: {e}")
        raise

    def _load_with_fallback(self) -> Dict[str, Any]:
        """尝试加载配置（X2：失败时抛出异常而非静默回退）"""
        return self._try_load()

    def load(self) -> Dict[str, Any]:
        """
        加载配置文件

        第一性原理：配置是系统行为的边界
        X2：配置文件不存在或校验失败时显式报错，不静默回退
        X3：接入错误码体系
        """
        if not os.path.exists(self.config_path):
            raise ValidationError(
                ErrorCode.CONFIG_NOT_FOUND,
                field="config_path",
                detail=(
                    f"配置文件不存在: {self.config_path}\n"
                    f"  请检查路径是否正确。\n"
                    f"  可用配置: config/dev.yaml, config/prod.yaml, config/test.yaml\n"
                    f"  或设置环境变量 AGENT_CONFIG_PATH 指定配置文件路径。\n"
                    f"  提示: 使用 --env {{dev,prod,test}} 快速选择环境配置。"
                ),
            )
        logger.info(f"正在加载配置文件: {self.config_path}")
        return self._load_with_fallback()

    def _load_from_file(self) -> None:
        if yaml is None:
            raise ImportError("pyyaml is required to load YAML config. Install with: pip install pyyaml")
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.last_load_time = time.time()
        self.last_modified_time = os.path.getmtime(self.config_path)

    def _is_file_changed(self) -> bool:
        """检查文件是否发生变化"""
        if not os.path.exists(self.config_path):
            return False
        current_mtime = os.path.getmtime(self.config_path)
        return current_mtime > self.last_modified_time

    def reload_if_changed(self) -> bool:
        """
        如果配置文件有变化，重新加载

        Returns:
            bool: 是否重新加载
        """
        if self._is_file_changed():
            return self._perform_reload()
        return False

    def _perform_reload(self) -> bool:
        logger.info("Config file changed, reloading...")
        old_config = self.config.copy()
        self.load()
        self._notify_listeners(old_config, self.config)
        return True

    def _call_listener(self, listener: Callable[[Dict[str, Any]], None], new_config: Dict) -> None:
        try:
            listener(new_config)
        except Exception as e:
            logger.error(f"Config listener error: {e}")

    def _notify_listeners(self, old_config: Dict, new_config: Dict) -> None:
        """通知配置变更监听器"""
        changed_keys = self._detect_changes(old_config, new_config)
        if not changed_keys:
            return
        logger.info(f"Config changes detected: {changed_keys}")
        for listener in self._listeners:
            self._call_listener(listener, new_config)

    def _detect_changes(self, old: Dict, new: Dict, prefix: str = "") -> List[str]:
        """检测配置变更的键"""
        changes: List[str] = []
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            changes.extend(self._detect_key_change(old, new, key, prefix))
        return changes

    def _full_key(self, prefix: str, key: str) -> str:
        return f"{prefix}.{key}" if prefix else key

    def _detect_key_change(
        self, old: Dict, new: Dict, key: str, prefix: str
    ) -> List[str]:
        full_key = self._full_key(prefix, key)
        return self._change_for_key(old, new, key, full_key)

    def _change_for_key(self, old: Dict, new: Dict, key: str, full_key: str) -> List[str]:
        if key not in old:
            return [f"+{full_key}"]
        if key not in new:
            return [f"-{full_key}"]
        if isinstance(old[key], dict) and isinstance(new[key], dict):
            return self._detect_changes(old[key], new[key], full_key)
        if old[key] != new[key]:
            return [f"~{full_key}"]
        return []

    def _set_nested(self, key: str, value: Any) -> None:
        """设置嵌套配置项"""
        keys = key.split('.')
        config = self._ensure_path(keys[:-1])
        config[keys[-1]] = value

    def _ensure_path(self, keys: List[str]) -> Dict[str, Any]:
        config = self.config
        for k in keys:
            if k not in config:
                config[k] = {}
            config = config[k]
        return config

    def add_change_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """添加配置变更监听器"""
        self._listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """移除配置变更监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def start_hot_reload(self, interval: float = 5.0) -> None:
        """启动热加载线程"""
        if self._hot_reload_enabled:
            return
        self._enable_reload(interval)
        self._start_reload_thread()
        logger.info(f"Hot reload started (interval={interval}s)")

    def _enable_reload(self, interval: float) -> None:
        self._hot_reload_enabled = True
        self._reload_interval = interval
        self._stop_event.clear()

    def _start_reload_thread(self) -> None:
        self._reload_thread = threading.Thread(target=self._reload_loop, daemon=True)
        self._reload_thread.start()

    def stop_hot_reload(self) -> None:
        """停止热加载线程"""
        if not self._hot_reload_enabled:
            return
        self._hot_reload_enabled = False
        self._stop_event.set()
        if self._reload_thread and self._reload_thread.is_alive():
            self._reload_thread.join(timeout=2.0)
        logger.info("Hot reload stopped")

    def _reload_loop(self) -> None:
        """热加载循环"""
        while not self._stop_event.is_set():
            self.reload_if_changed()
            self._stop_event.wait(self._reload_interval)

    def _try_set_and_validate(self, key: str, value: Any) -> bool:
        """尝试设置并验证参数"""
        self._set_nested(key, value)
        self._validate_config()
        logger.info(f"Dynamic param set: {key}={value}")
        return True

    def set_param(self, key: str, value: Any) -> bool:
        """
        动态设置参数

        Args:
            key: 参数键（支持嵌套，如"guardrail.max_cpu_usage"）
            value: 参数值

        Returns:
            bool: 是否设置成功
        """
        old_config = copy.deepcopy(self.config)
        try:
            return self._try_set_and_validate(key, value)
        except Exception as e:
            self.config = old_config
            logger.error(f"Failed to set param {key}: {e}")
            return False

    def get_param_info(self, key: str) -> Dict[str, Any]:
        """获取参数信息"""
        value = self.get(key)
        return {
            "key": key,
            "value": value,
            "type": type(value).__name__ if value is not None else "None",
            "source": self.config_path if os.path.exists(self.config_path) else "default",
        }

    def list_params(self, prefix: str = "") -> List[str]:
        """列出所有参数键"""
        keys = []
        self._collect_keys(self.config, prefix, keys)
        return keys

    def _collect_keys(self, config: Dict, prefix: str, keys: List[str]) -> None:
        """递归收集所有配置键"""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._collect_keys(value, full_key, keys)
            else:
                keys.append(full_key)

    def _get_nested(self, keys: List[str]) -> Any:
        """获取嵌套配置值"""
        value = self.config
        for k in keys:
            value = self._step_nested(value, k)
            if value is None:
                return None
        return value

    def _step_nested(self, value: Any, key: str) -> Any:
        if isinstance(value, dict) and key in value:
            return value[key]
        return None

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        支持嵌套键，如 "perception.system_poll_interval"
        """
        keys = key.split('.')
        value = self._get_nested(keys)
        return default if value is None else value

    def get_perception_config(self) -> Dict[str, Any]:
        """获取感知模块配置"""
        return self.get('perception', {})

    def get_drive_engine_config(self) -> Dict[str, Any]:
        """获取驱力引擎配置"""
        return self.get('drive_engine', {})

    def get_guardrail_config(self) -> Dict[str, Any]:
        """获取安全护栏配置"""
        return self.get('guardrail', {})

    def get_decision_config(self) -> Dict[str, Any]:
        """获取决策引擎配置"""
        return self.get('decision', {})

    def get_memory_config(self) -> Dict[str, Any]:
        """获取记忆系统配置"""
        return self.get('memory', {})

    def get_snapshot_config(self) -> Dict[str, Any]:
        """获取快照配置"""
        return self.get('snapshot', {})

    def _validate_cpu(self) -> None:
        """验证CPU限制配置（X2：增强错误信息，X3：接入错误码）"""
        max_cpu = self.get('guardrail.max_cpu_usage', 0.2)
        if not (0.01 <= max_cpu <= 1.0):
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field="guardrail.max_cpu_usage",
                detail=(
                    f"配置项 guardrail.max_cpu_usage 无效: {max_cpu}\n"
                    f"  合法取值范围: 0.01 ~ 1.0（表示 1% ~ 100%）\n"
                    f"  修复建议: 将 config 文件中的 guardrail.max_cpu_usage 改为 0.01 到 1.0 之间的值\n"
                    f"  示例: max_cpu_usage: 0.5  # 限制CPU使用率50%"
                ),
            )

    def _validate_memory(self) -> None:
        """验证内存限制配置（X2：增强错误信息，X3：接入错误码）"""
        max_memory = self.get('guardrail.max_memory_usage', 0.2)
        if not (0.01 <= max_memory <= 1.0):
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field="guardrail.max_memory_usage",
                detail=(
                    f"配置项 guardrail.max_memory_usage 无效: {max_memory}\n"
                    f"  合法取值范围: 0.01 ~ 1.0（表示 1% ~ 100%）\n"
                    f"  修复建议: 将 config 文件中的 guardrail.max_memory_usage 改为 0.01 到 1.0 之间的值\n"
                    f"  示例: max_memory_usage: 0.5  # 限制内存使用率50%"
                ),
            )

    def _validate_exploration(self) -> None:
        """验证探索比例配置（X2：增强错误信息，X3：接入错误码）"""
        exploration = self.get('decision.base_exploration_ratio', 0.3)
        if not (0.0 <= exploration <= 1.0):
            raise ValidationError(
                ErrorCode.PARAMETER_RANGE_ERROR,
                field="decision.base_exploration_ratio",
                detail=(
                    f"配置项 decision.base_exploration_ratio 无效: {exploration}\n"
                    f"  合法取值范围: 0.0 ~ 1.0（0=纯利用，1=纯探索）\n"
                    f"  修复建议: 将 config 文件中的 decision.base_exploration_ratio 改为 0.0 到 1.0 之间的值\n"
                    f"  示例: base_exploration_ratio: 0.3  # 30%探索率"
                ),
            )

    def _validate_config(self) -> None:
        """
        验证配置有效性

        第一性原理：无效配置必须被拒绝，防止系统行为异常
        """
        self._validate_cpu()
        self._validate_memory()
        self._validate_exploration()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'perception': self._default_perception(),
            'drive_engine': self._default_drive_engine(),
            'guardrail': self._default_guardrail(),
            'decision': self._default_decision(),
            'memory': self._default_memory(),
            'snapshot': self._default_snapshot(),
        }

    def _default_perception(self) -> Dict[str, Any]:
        return {
            'system_poll_interval': 1.0,
            'max_cpu_usage': 0.02,
        }

    def _default_drive_engine(self) -> Dict[str, Any]:
        return {
            'base_weights': {'safe': 0.4, 'gain': 0.4, 'eff': 0.2},
            'adaptation_rate': 0.3,
        }

    def _default_guardrail(self) -> Dict[str, Any]:
        return {
            'max_cpu_usage': 0.2,
            'max_memory_usage': 0.2,
            'max_disk_usage': 0.85,
        }

    def _default_decision(self) -> Dict[str, Any]:
        return {
            'base_exploration_ratio': 0.3,
            'min_exploration_ratio': 0.1,
            'max_exploration_ratio': 0.5,
        }

    def _default_memory(self) -> Dict[str, Any]:
        return {
            'short_term_capacity': 10000,
            'keep_ratio': 0.3,
        }

    def _default_snapshot(self) -> Dict[str, Any]:
        return {
            'snapshot_dir': './snapshots',
            'max_snapshots': 10,
            'interval': 3600,
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.config.copy()

    def snapshot_config(self) -> Dict[str, Any]:
        """创建配置快照"""
        snapshot = {
            "config": copy.deepcopy(self.config),
            "timestamp": time.time(),
            "path": self.config_path,
        }
        return snapshot

    def restore_config(self, snapshot: Dict[str, Any]) -> bool:
        """
        从快照恢复配置

        Args:
            snapshot: 配置快照

        Returns:
            是否恢复成功
        """
        if "config" not in snapshot:
            return False
        self.config = snapshot["config"].copy()
        self._validate_config()
        logger.info("Config restored from snapshot")
        return True

    def set_params_atomic(self, updates: Dict[str, Any]) -> bool:
        """
        原子性批量更新参数

        全部验证通过才应用，任一失败则回滚

        Args:
            updates: 参数更新字典

        Returns:
            是否全部更新成功
        """
        old_config = copy.deepcopy(self.config)
        try:
            for key, value in updates.items():
                self._set_nested(key, value)
            self._validate_config()
            logger.info(f"Atomic update applied: {list(updates.keys())}")
            return True
        except Exception as e:
            self.config = old_config
            logger.error(f"Atomic update failed: {e}")
            return False

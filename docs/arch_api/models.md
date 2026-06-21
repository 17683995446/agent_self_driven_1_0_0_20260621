# 数据模型设计

## 目录

- [状态模型](#状态模型)
- [任务模型](#任务模型)
- [配置模型](#配置模型)
- [错误码](#错误码)

## 状态模型

### EnvironmentState
系统环境状态，包含系统、日志、文件、自身四个维度。

```python
@dataclass(frozen=True)
class EnvironmentState:
    timestamp: float
    system: SystemState
    log: LogState
    file: FileState
    self: SelfState
```

### DriveRewards
驱力奖励，三个维度：安全、收益、能效。

```python
@dataclass(frozen=True)
class DriveRewards:
    safety: float = 0.0
    gain: float = 0.0
    efficiency: float = 0.0
```

### GapState
缺口状态，表示当前与目标的差距。

```python
@dataclass(frozen=True)
class GapState:
    safety: float = 0.0
    gain: float = 0.0
    efficiency: float = 0.0
```

### DriveWeights
驱力权重，三个维度之和必须为1.0。

```python
@dataclass(frozen=True)
class DriveWeights:
    safe: float = 0.4
    gain: float = 0.4
    eff: float = 0.2
```

## 任务模型

### Task
任务定义，包含执行函数、优先级、目标驱力等。

```python
@dataclass
class Task:
    name: str
    execute_fn: Optional[Callable] = None
    priority: TaskPriority = TaskPriority.LOW
    target_drive: str = "safe"
    is_exploration: bool = False
```

### TaskResult
任务执行结果。

```python
@dataclass(frozen=True)
class TaskResult:
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
```

## 配置模型

### SystemConfig
系统配置根节点。

```python
@dataclass
class SystemConfig:
    perception: PerceptionConfig
    drive_engine: DriveEngineConfig
    guardrail: GuardrailConfig
    decision: DecisionConfig
    memory: MemoryConfig
    snapshot: SnapshotConfig
```

## 错误码

统一错误码枚举，覆盖所有模块。

| 错误码 | 含义 |
|--------|------|
| SUCCESS | 成功 |
| INVALID_PARAMETER | 参数无效 |
| MISSING_PARAMETER | 参数缺失 |
| RESOURCE_EXHAUSTED | 资源耗尽 |
| OPERATION_NOT_ALLOWED | 操作不允许 |

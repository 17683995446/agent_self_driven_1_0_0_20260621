# 数据模型API

## 目录

- [状态模型](#状态模型)
- [任务模型](#任务模型)
- [事件模型](#事件模型)
- [监控模型](#监控模型)

## 状态模型

### EnvironmentState
```python
@dataclass(frozen=True)
class EnvironmentState:
    timestamp: float = field(default_factory=time.time)
    system: SystemState = field(default_factory=SystemState)
    log: LogState = field(default_factory=LogState)
    file: FileState = field(default_factory=FileState)
    self: SelfState = field(default_factory=SelfState)
```

### SystemState
```python
@dataclass(frozen=True)
class SystemState:
    cpu_overall: float = 0.0
    cpu_per_process: float = 0.0
    memory_usage: float = 0.0
    memory_pressure: float = 0.0
    disk_usage: float = 0.0
    io_wait: float = 0.0
    process_count: int = 0
    zombie_processes: int = 0
    load_average: float = 0.0
```

### DriveRewards
```python
@dataclass(frozen=True)
class DriveRewards:
    safety: float = 0.0
    gain: float = 0.0
    efficiency: float = 0.0
```

### GapState
```python
@dataclass(frozen=True)
class GapState:
    safety: float = 0.0
    gain: float = 0.0
    efficiency: float = 0.0
```

### DriveWeights
```python
@dataclass(frozen=True)
class DriveWeights:
    safe: float = 0.4
    gain: float = 0.4
    eff: float = 0.2
```

## 任务模型

### Task
```python
@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    execute_fn: Optional[Callable] = None
    priority: TaskPriority = TaskPriority.LOW
    target_drive: str = "safe"
    is_exploration: bool = False
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    max_cpu_usage: float = 0.1
    max_memory_usage: float = 0.1
```

### TaskResult
```python
@dataclass(frozen=True)
class TaskResult:
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
```

### TaskPool
```python
@dataclass
class TaskPool:
    max_size: int = 1000
    tasks: Dict[str, Task] = field(default_factory=dict)
    execution_history: List[Dict] = field(default_factory=list)
```

## 事件模型

### Event
```python
@dataclass(frozen=True)
class Event:
    type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
```

### EventType
```python
class EventType(Enum):
    STATE_UPDATED = "state_updated"
    GAP_DETECTED = "gap_detected"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    ERROR_OCCURRED = "error_occurred"
```

## 监控模型

### EvolutionMetrics
```python
@dataclass(frozen=True)
class EvolutionMetrics:
    precision_index: float = 0.0
    coverage_index: float = 0.0
    efficiency_index: float = 0.0
    timestamp: float = field(default_factory=time.time)
```

### AnomalyEvent
```python
@dataclass(frozen=True)
class AnomalyEvent:
    type: str
    severity: str
    message: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
```

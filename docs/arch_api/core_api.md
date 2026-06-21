# 核心模块API

## 目录

- [DecisionEngine](#decisionengine)
- [DriveEngineModule](#driveenginemodule)
- [EnvironmentPerceptionModule](#environmentperceptionmodule)
- [HierarchicalPredictionModel](#hierarchicalpredictionmodel)
- [SleepManager](#sleepmanager)
- [EvolutionMonitor](#evolutionmonitor)
- [SnapshotManager](#snapshotmanager)
- [SafetyGuardrail](#safetyguardrail)
- [MemorySystem](#memorysystem)
- [TaskExecutor](#taskexecutor)
- [EventBus](#eventbus)
- [AnomalyDetector](#anomalydetector)
- [AlertManager](#alertmanager)
- [AdaptiveExplorationBalancer](#adaptiveexplorationbalancer)
- [SelfDiagnostics](#selfdiagnostics)

## DecisionEngine

### 初始化
```python
engine = DecisionEngine(base_exploration_ratio: float = 0.3)
```

### 方法
- `generate_tasks(gaps: GapState, state: EnvironmentState) -> List[Task]`
- `select_next_task(pool: TaskPool, gaps: GapState, weights: DriveWeights) -> Optional[Task]`
- `execute_task(task: Task) -> TaskResult`
- `update_exploration_ratio(error_trend: float, stagnation_detected: bool = False)`

## DriveEngineModule

### 初始化
```python
engine = DriveEngineModule()
```

### 方法
- `compute_drive_rewards(state: EnvironmentState) -> DriveRewards`
- `compute_gaps(rewards: Optional[DriveRewards] = None) -> GapState`
- `compute_weights(state: EnvironmentState, gaps: Optional[GapState] = None) -> DriveWeights`

## EnvironmentPerceptionModule

### 初始化
```python
module = EnvironmentPerceptionModule()
```

### 方法
- `get_current_state() -> EnvironmentState`
- `start()`
- `stop()`
- `register_sensor(sensor: Sensor)`

## HierarchicalPredictionModel

### 初始化
```python
model = HierarchicalPredictionModel()
```

### 方法
- `predict() -> EnvironmentState`
- `update(actual: EnvironmentState)`
- `get_average_error() -> float`

## SleepManager

### 初始化
```python
manager = SleepManager(memory_system: MemorySystem, prediction_model: HierarchicalPredictionModel, idle_threshold: float = 0.9)
```

### 方法
- `should_sleep(state: EnvironmentState) -> bool`
- `enter_sleep() -> SleepReport`
- `wake_up()`

## EvolutionMonitor

### 初始化
```python
monitor = EvolutionMonitor(window_size: int = 30)
```

### 方法
- `update(state: EnvironmentState, rewards: DriveRewards, gaps: GapState, task_executed: bool = False, task_success: bool = False, prediction_error: float = 0.0)`
- `detect_trend() -> EvolutionTrend`
- `get_current_metrics() -> Optional[EvolutionMetrics]`

## SnapshotManager

### 初始化
```python
manager = SnapshotManager(snapshot_dir: str = "./snapshots", max_snapshots: int = 10, auto_snapshot_interval: int = 3600)
```

### 方法
- `create_snapshot(model_state: Dict, config_state: Dict, metrics: Dict, metadata: Optional[Dict] = None) -> Snapshot`
- `rollback(snapshot_id: Optional[str] = None) -> RollbackResult`
- `compare_snapshots(id1: str, id2: str) -> Dict`

## SafetyGuardrail

### 初始化
```python
guardrail = SafetyGuardrail(max_cpu: float = 0.2, max_memory: float = 0.2, max_disk: float = 0.85)
```

### 方法
- `check_operation(operation: str) -> GuardrailResult`
- `check_resource_usage(usage: ResourceUsage) -> GuardrailResult`
- `enforce_resource_limits(usage: ResourceUsage) -> EnforcementAction`

## MemorySystem

### 初始化
```python
memory = MemorySystem(short_term_capacity: int = 10000, long_term_path: str = "./memory/long_term.json")
```

### 方法
- `store_experience(state: Any, action: str, result: Any, reward: float, importance: float = 0.5)`
- `retrieve_recent(count: int = 10) -> List[Experience]`
- `retrieve_important(count: int = 10) -> List[Experience]`
- `sync_to_long_term()`

## TaskExecutor

### 初始化
```python
executor = TaskExecutor(max_workers: int = 4, default_timeout: float = 30.0)
```

### 方法
- `submit(task: Task, timeout: Optional[float] = None) -> ExecutionRecord`
- `cancel_task(task_id: str) -> bool`
- `shutdown(wait: bool = True)`

## EventBus

### 初始化
```python
bus = EventBus()
```

### 方法
- `publish(event: Event, async_mode: bool = False)`
- `subscribe(listener: EventListener, event_types: Optional[List[EventType]] = None)`
- `unsubscribe(listener: EventListener)`

## AnomalyDetector

### 初始化
```python
detector = AnomalyDetector()
```

### 方法
- `detect(state: EnvironmentState) -> List[AnomalyEvent]`
- `update_baseline(state: EnvironmentState)`

## AlertManager

### 初始化
```python
manager = AlertManager()
```

### 方法
- `send_alert(anomaly: AnomalyEvent)`
- `get_alert_history() -> List[AnomalyEvent]`

## AdaptiveExplorationBalancer

### 初始化
```python
balancer = AdaptiveExplorationBalancer(base_ratio: float = 0.3, min_ratio: float = 0.1, max_ratio: float = 0.5, adaptation_rate: float = 0.3, stagnation_threshold: int = 5, window_size: int = 20)
```

### 方法
- `should_explore() -> bool`
- `adjust(force: bool = False) -> float`
- `record_exploration_result(success: bool, reward: float = 0.0)`

## SelfDiagnostics

### 初始化
```python
diagnostics = SelfDiagnostics(check_interval: float = 60.0)
```

### 方法
- `register_check(check: HealthCheck)`
- `run_all_checks() -> Dict[str, ComponentHealth]`
- `get_overall_status() -> HealthStatus`

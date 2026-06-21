# 核心模块设计

## 目录

- [环境感知 (Perception)](#环境感知)
- [驱力引擎 (Drive Engine)](#驱力引擎)
- [决策引擎 (Decision)](#决策引擎)
- [任务执行器 (Executor)](#任务执行器)
- [记忆系统 (Memory)](#记忆系统)
- [预测模型 (Prediction)](#预测模型)
- [睡眠进化 (Sleep)](#睡眠进化)
- [监控告警 (Monitor/Alert)](#监控告警)
- [快照回滚 (Snapshot)](#快照回滚)
- [安全护栏 (Guardrail)](#安全护栏)
- [探索平衡 (Exploration)](#探索平衡)
- [事件总线 (Event Bus)](#事件总线)
- [健康检查 (Health)](#健康检查)

## 环境感知

### 职责
采集系统环境状态，包括CPU、内存、磁盘、进程等。

### 接口
- `get_current_state()` → `EnvironmentState`
- `start()` / `stop()`

## 驱力引擎

### 职责
计算内生驱力奖励、评估缺口、调整权重。

### 接口
- `compute_drive_rewards(state)` → `DriveRewards`
- `compute_gaps(rewards)` → `GapState`
- `compute_weights(state, gaps)` → `DriveWeights`

## 决策引擎

### 职责
基于缺口和权重生成任务，选择最优任务执行。

### 接口
- `generate_tasks(gaps, state)` → `List[Task]`
- `select_next_task(pool, gaps, weights)` → `Optional[Task]`
- `execute_task(task)` → `TaskResult`

## 任务执行器

### 职责
并发执行任务，管理超时和取消。

### 接口
- `submit(task, timeout)` → `ExecutionRecord`
- `cancel_task(task_id)` → `bool`

## 记忆系统

### 职责
存储经验，短期/长期记忆分层，自动同步。

### 接口
- `store_experience(state, action, result, reward, importance)`
- `retrieve_recent(count)` → `List[Experience]`
- `retrieve_important(count)` → `List[Experience]`

## 预测模型

### 职责
分层预测（低/中/高层），在线学习更新。

### 接口
- `predict()` → `EnvironmentState`
- `update(actual)`

## 睡眠进化

### 职责
检测睡眠条件，离线复盘，模型优化。

### 接口
- `should_sleep(state)` → `bool`
- `enter_sleep()` → `SleepReport`

## 监控告警

### 职责
计算进化指标，检测趋势，记录异常。

### 接口
- `update(state, rewards, gaps)`
- `detect_trend()` → `EvolutionTrend`
- `get_current_metrics()` → `Optional[EvolutionMetrics]`

## 快照回滚

### 职责
创建快照，回滚状态，比较差异。

### 接口
- `create_snapshot(model_state, config_state, metrics)` → `Snapshot`
- `rollback(snapshot_id)` → `RollbackResult`

## 安全护栏

### 职责
检查操作合法性，强制执行资源限制。

### 接口
- `check_operation(operation)` → `GuardrailResult`
- `check_resource_usage(usage)` → `GuardrailResult`
- `enforce_resource_limits(usage)` → `EnforcementAction`

## 探索平衡

### 职责
动态调整探索/利用比例，记录成功率。

### 接口
- `should_explore()` → `bool`
- `adjust(force)` → `float`
- `record_exploration_result(success, reward)`

## 事件总线

### 职责
模块间解耦通信，支持同步/异步发布。

### 接口
- `publish(event, async_mode)`
- `subscribe(listener, event_types)`

## 健康检查

### 职责
定期检查各组件健康状态，自动修复。

### 接口
- `run_all_checks()` → `Dict[str, ComponentHealth]`
- `get_overall_status()` → `HealthStatus`

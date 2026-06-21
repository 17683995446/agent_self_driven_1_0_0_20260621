# 配置说明文档

本文档详细说明 Self-Driven Agent 的所有配置项、取值范围和环境差异。

## 配置文件位置

| 环境 | 文件路径 | 用途 |
|------|----------|------|
| 开发 | `config/dev.yaml` | 本地开发、调试（默认） |
| 生产 | `config/prod.yaml` | 生产部署、长期运行 |
| 测试 | `config/test.yaml` | 单元测试、集成测试、CI/CD |

## 配置加载优先级

配置文件按以下优先级加载（高 → 低）：

1. **CLI参数**：`--config PATH` 或 `--env {dev,prod,test}`
2. **环境变量**：`AGENT_CONFIG_PATH`
3. **默认值**：`./config/dev.yaml`

示例：

```bash
# 方式1：CLI参数指定配置文件
python -m src.main --config config/prod.yaml

# 方式2：CLI参数选择环境
python -m src.main --env prod

# 方式3：环境变量
export AGENT_CONFIG_PATH=config/prod.yaml
python -m src.main
```

## 配置项详解

### 基础信息

#### `environment`
- **类型**：字符串
- **取值**：`dev` | `prod` | `test`
- **说明**：运行环境标识，用于日志和监控区分

#### `log_level`
- **类型**：字符串
- **取值**：`DEBUG` | `INFO` | `WARNING` | `ERROR`
- **说明**：日志级别，影响输出到 `logs/agent.log` 的详细程度
- **建议**：开发用 `DEBUG`，生产用 `WARNING`，测试用 `INFO`

### 系统循环配置

#### `cycle_interval`
- **类型**：浮点数
- **单位**：秒
- **取值范围**：> 0
- **推荐值**：0.1 ~ 10.0
- **说明**：主循环间隔，决定系统决策频率。值越小响应越快但 CPU 占用越高

#### `cycle_timeout`
- **类型**：浮点数
- **单位**：秒
- **取值范围**：> `cycle_interval`
- **推荐值**：5.0 ~ 60.0
- **说明**：单次循环超时阈值，超过则触发告警

### 任务池配置

#### `task_pool_max_size`
- **类型**：整数
- **取值范围**：> 0
- **推荐值**：50 ~ 1000
- **说明**：任务池最大容量，超过则拒绝新任务

#### `task_default_timeout`
- **类型**：浮点数
- **单位**：秒
- **取值范围**：> 0
- **推荐值**：10.0 ~ 600.0
- **说明**：任务默认超时时间，超时则中断任务

### 安全护栏 (`guardrail`)

资源使用上限保护，超过则触发保护机制。

#### `guardrail.max_cpu_usage`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0（1.0 = 100%）
- **说明**：CPU 使用率上限
- **建议**：dev=0.5，prod=0.2

#### `guardrail.max_memory_usage`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：内存使用率上限

#### `guardrail.max_disk_usage`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：磁盘使用率上限

#### `guardrail.forbidden_operations`
- **类型**：字符串列表（正则表达式）
- **说明**：禁止执行的危险命令模式列表，匹配到任一模式则拒绝执行
- **默认模式**：
  - `rm\s+-rf\s+/`：禁止 `rm -rf /`
  - `mkfs`：禁止格式化文件系统
  - `dd\s+if=.*of=/dev/`：禁止写入设备文件

### 决策引擎 (`decision`)

探索-利用平衡参数。

#### `decision.base_exploration_ratio`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：基础探索比例。0=纯利用（选择最优），1=纯探索（随机尝试）
- **推荐值**：0.2 ~ 0.4

#### `decision.min_exploration_ratio`
- **类型**：浮点数
- **取值范围**：0.0 ~ `base_exploration_ratio`
- **说明**：最小探索比例（下限保护），防止探索率过低导致陷入局部最优

#### `decision.max_exploration_ratio`
- **类型**：浮点数
- **取值范围**：`base_exploration_ratio` ~ 1.0
- **说明**：最大探索比例（上限保护），防止探索率过高导致不稳定

### 感知模块 (`perception`)

系统状态感知参数。

#### `perception.system_poll_interval`
- **类型**：浮点数
- **单位**：秒
- **取值范围**：> 0
- **推荐值**：0.1 ~ 5.0
- **说明**：系统状态采样间隔

#### `perception.max_cpu_usage`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：感知模块自身 CPU 占用上限，应远小于 `guardrail.max_cpu_usage`

### 驱力引擎 (`drive_engine`)

驱动力权重配置。

**约束**：`safe + gain + eff = 1.0`

#### `drive_engine.base_weights.safe`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：安全驱力权重，驱动系统避免危险操作

#### `drive_engine.base_weights.gain`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：收益驱力权重，驱动系统追求收益

#### `drive_engine.base_weights.eff`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：效率驱力权重，驱动系统提高资源效率

#### `drive_engine.adaptation_rate`
- **类型**：浮点数
- **取值范围**：0.0 ~ 1.0
- **说明**：驱力权重自适应速率。0=不自适应，1=快速自适应

### 事件总线 (`event_bus`)

#### `event_bus.max_event_history`
- **类型**：整数
- **取值范围**：> 0
- **推荐值**：100 ~ 10000
- **说明**：事件历史最大保留数，超过则丢弃最旧事件

#### `event_bus.async_workers`
- **类型**：整数
- **取值范围**：>= 1
- **推荐值**：1 ~ 8
- **说明**：异步事件处理工作线程数

### 审计日志

#### `audit_dir`
- **类型**：字符串（路径）
- **说明**：审计日志存储目录，相对路径基于项目根目录。目录不存在时自动创建

### 快照配置 (`snapshot`)

#### `snapshot.snapshot_dir`
- **类型**：字符串（路径）
- **说明**：快照存储目录

#### `snapshot.max_snapshots`
- **类型**：整数
- **取值范围**：> 0
- **说明**：最大快照保留数，超过则删除最旧快照

#### `snapshot.interval`
- **类型**：整数
- **单位**：秒
- **取值范围**：> 0
- **推荐值**：600 ~ 7200
- **说明**：快照生成间隔

### API网关 (`api_gateway`)

#### `api_gateway.rate_limit_requests_per_second`
- **类型**：整数
- **取值范围**：> 0
- **说明**：每秒最大请求数

#### `api_gateway.rate_limit_burst_size`
- **类型**：整数
- **取值范围**：>= `rate_limit_requests_per_second`
- **说明**：突发请求上限，允许短时间内的请求突发

## 环境差异对比

| 配置项 | dev | prod | test |
|--------|-----|------|------|
| `log_level` | DEBUG | WARNING | INFO |
| `cycle_interval` | 1.0 | 1.0 | 0.1 |
| `cycle_timeout` | 30.0 | 60.0 | 5.0 |
| `task_pool_max_size` | 100 | 1000 | 50 |
| `task_default_timeout` | 60.0 | 300.0 | 10.0 |
| `guardrail.max_cpu_usage` | 0.5 | 0.2 | 0.2 |
| `guardrail.max_memory_usage` | 0.5 | 0.2 | 0.2 |
| `event_bus.max_event_history` | 1000 | 10000 | 100 |
| `event_bus.async_workers` | 1 | 4 | 1 |
| `snapshot.max_snapshots` | 10 | 50 | 5 |
| `api_gateway.rate_limit_requests_per_second` | 100 | 50 | 1000 |

## 自定义配置

如需创建自定义配置：

1. 复制现有配置文件作为模板：
   ```bash
   cp config/dev.yaml config/custom.yaml
   ```

2. 修改配置项值

3. 通过以下方式加载：
   ```bash
   # CLI参数
   python -m src.main --config config/custom.yaml

   # 环境变量
   export AGENT_CONFIG_PATH=config/custom.yaml
   python -m src.main
   ```

## 配置验证

使用 `--dry-run` 验证配置而不启动主循环：

```bash
python -m src.main --config config/prod.yaml --dry-run
```

该命令会加载配置、验证完整性、打印配置摘要，然后退出。

## 常见问题

> 更多问答见 [FAQ.md](FAQ.md)。

### Q: 配置文件不存在会怎样？

A: 系统会抛出 `ValidationError(CONFIG_NOT_FOUND)`（错误码 200003）并退出，**不会**静默使用默认配置。请用 `--config` 指定路径或 `--env` 选择环境。

### Q: 配置项缺失会怎样？

A: 缺失的配置项使用代码内置默认值，不会导致崩溃。但建议显式配置所有关键项。

### Q: 如何查看当前加载的配置？

A: 启动时系统会打印配置摘要，包含配置文件路径、环境、日志级别和关键参数。也可用 `--dry-run` 验证配置并查看摘要。

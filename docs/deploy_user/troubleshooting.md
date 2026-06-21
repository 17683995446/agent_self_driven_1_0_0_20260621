# 故障排查

- [错误码对照表](#错误码对照表)
- [常见问题](#常见问题)
  - [Agent无法启动](#agent无法启动)
  - [任务执行失败率高](#任务执行失败率高)
  - [预测精度下降](#预测精度下降)
  - [内存泄漏](#内存泄漏)
  - [优雅停机超时](#优雅停机超时)
- [日志分析](#日志分析)
- [诊断命令](#诊断命令)

## 错误码对照表

系统使用统一的错误码体系（见 `src/platform/support/models/base/error_code.py`）。错误码按类别分段，便于快速定位问题。配置项的允许范围见 [配置说明](configuration.md)。

### 参数类（1xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 100001 | invalid_parameter | 参数无效 | 传入参数格式/值不合法 | 检查参数类型与取值 |
| 100002 | missing_parameter | 参数缺失 | 必填参数未提供 | 补全必填参数 |
| 100003 | parameter_type_error | 参数类型错误 | 传入类型与期望不符 | 检查参数类型（str/int/float/list/dict） |
| 100004 | parameter_range_error | 参数范围错误 | 数值越界或长度超限 | 调整到允许范围内（见配置说明） |
| 100005 | parameter_format_error | 参数格式错误 | 枚举值不合法 | 使用允许的枚举值 |

### 系统/配置类（2xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 200001 | system_internal_error | 系统内部错误 | 未捕获异常 | 查看堆栈日志，提交 issue |
| 200002 | config_load_error | 配置加载失败 | YAML 语法错误 | 用 `python -c "import yaml; yaml.safe_load(open('config/prod.yaml'))"` 验证 |
| 200003 | config_not_found | 配置文件不存在 | 路径错误或文件缺失 | 检查 `--config` 路径或使用 `--env` 选择环境 |
| 200004 | config_validate_error | 配置校验失败 | 必填项缺失或值非法 | 对照配置说明补全/修正 |

### 资源类（3xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 300001 | resource_cpu_exceeded | CPU 超限 | 周期负载超过配置上限 | 调高 `cpu_threshold` 或降低任务并发 |
| 300002 | resource_memory_exceeded | 内存超限 | 内存占用超过配置上限 | 调高 `memory_threshold` 或清理记忆/快照 |
| 300003 | resource_disk_exceeded | 磁盘超限 | 磁盘占用超过配置上限 | 清理日志/快照，或调高 `disk_threshold` |
| 300004 | resource_limit_violation | 资源限制违反 | 安全护栏触发 | 检查资源监控日志，调整任务负载 |

### 安全类（4xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 400001 | safety_violation | 安全违规 | 任务触发安全护栏 | 检查任务函数是否在白名单内 |
| 400002 | forbidden_operation | 禁止操作 | 尝试执行受限操作 | 查看安全策略配置 |
| 400003 | exploration_stopped | 探索被停止 | 探索率超限或手动停止 | 检查探索配置与运行状态 |

### 任务类（5xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 500001 | task_execute_failed | 任务执行失败 | 任务函数抛出异常 | 查看任务日志堆栈 |
| 500002 | task_timeout | 任务超时 | 执行时间超过 `task_timeout` | 调高超时或优化任务函数 |
| 500003 | task_cancelled | 任务被取消 | 优雅停机或主动取消 | 正常现象，无需处理 |
| 500004 | task_no_function | 任务无函数 | 任务未绑定可执行函数 | 检查任务注册逻辑 |

### 快照/模型/记忆/健康类（6xxxxx-9xxxxx）

| 错误码 | 名称 | 含义 | 常见原因 | 解决方案 |
|--------|------|------|----------|----------|
| 600001 | snapshot_create_failed | 快照创建失败 | 磁盘满或权限不足 | 检查磁盘空间与目录权限 |
| 600002 | snapshot_rollback_failed | 快照回滚失败 | 快照损坏或状态不一致 | 尝试更早的快照 |
| 600003 | snapshot_not_found | 快照不存在 | 快照 ID 错误或已被清理 | 列出可用快照后重试 |
| 700001 | prediction_error | 预测错误 | 模型输入异常 | 检查输入数据格式 |
| 700002 | model_update_failed | 模型更新失败 | 训练数据不足或梯度异常 | 检查记忆系统数据量 |
| 800001 | memory_store_failed | 记忆存储失败 | 容量满或序列化失败 | 清理旧记忆或扩容 |
| 800002 | memory_retrieve_failed | 记忆检索失败 | 索引损坏 | 重建记忆索引 |
| 900001 | health_check_failed | 健康检查失败 | 关键组件异常 | 查看健康检查详情 |
| 900002 | healing_failed | 自愈失败 | 自愈策略未覆盖该故障 | 手动介入处理 |

## 常见问题

### Agent无法启动

**现象**：执行 `./scripts/start.sh` 后报错或无响应

**排查步骤**：
1. 检查 Python 版本 `python --version`（需要 3.8+）
2. 检查依赖安装 `pip list | grep -E "pyyaml|psutil|numpy"`
3. 检查配置文件 `cat config/dev.yaml`（确认存在且语法正确）
4. 验证安装 `python scripts/verify_installation.py`
5. 验证配置 `self-driven-agent --dry-run`
6. 查看启动日志 `tail -f logs/agent.out`

**常见错误码**：
- `200003 config_not_found`：配置文件路径错误 → 使用 `--env` 或 `--config` 指定
- `200002 config_load_error`：YAML 语法错误 → 用 `yaml.safe_load` 验证
- `100004 parameter_range_error`：配置值越界 → 对照配置说明修正

### 任务执行失败率高

**现象**：监控显示任务成功率低于 50%

**排查步骤**：
1. 查看运行状态 `self-driven-agent --status`
2. 检查资源使用 `python -c "import psutil; print(psutil.cpu_percent(), psutil.virtual_memory().percent)"`
3. 检查安全护栏触发日志 `grep "safety_violation\|resource_" logs/agent.log`
4. 检查任务超时设置

**常见错误码**：
- `500001 task_execute_failed`：任务函数异常 → 查看堆栈
- `500002 task_timeout`：超时 → 调高 `task_timeout` 或优化任务
- `300001/300002 resource_*_exceeded`：资源超限 → 调高阈值或降负载

### 预测精度下降

**现象**：预测误差持续增大

**排查步骤**：
1. 检查记忆系统数据量 `self-driven-agent --status`（查看 memory 条目数）
2. 检查睡眠进化是否正常触发 `grep "sleep_evolution" logs/agent.log`
3. 检查是否有异常状态输入 `grep "prediction_error" logs/agent.log`

### 内存泄漏

**现象**：内存使用持续增长

**排查步骤**：
1. 查看运行状态 `self-driven-agent --status`（查看 memory/snapshot 统计）
2. 检查记忆系统容量
3. 检查快照数量
4. 检查事件总线历史长度

**解决方案**：
- 调低 `memory.max_entries` 限制记忆容量
- 调低 `snapshot.max_snapshots` 限制快照数量
- 定期重启 Agent 释放资源

### 优雅停机超时

**现象**：执行 `./scripts/stop.sh` 后等待超过 30 秒才停止

**排查步骤**：
1. 查看停机日志 `grep "shutdown" logs/agent.log`
2. 检查是否有长周期任务正在执行（停机会等待当前周期完成）
3. 检查快照保存是否成功

**说明**：系统采用两阶段停机——第一次 `SIGTERM` 触发优雅停机（等待当前周期完成、保存快照），若 30 秒未退出则 `SIGKILL` 强制终止。强制终止可能丢失未保存的状态。

## 日志分析

### 日志位置

| 日志文件 | 说明 |
|----------|------|
| `logs/agent.log` | 主日志（轮转，10MB/份，保留 5 份） |
| `logs/agent.out` | 启动脚本重定向的标准输出/错误 |
| `logs/runtime_status.json` | 运行时状态快照（JSON，机器可读） |
| `logs/runtime_monitor.log` | 监控脚本运行日志 |
| `logs/runtime_monitor_report.log` | 监控脚本最终报告 |

### 日志格式

- **text**（默认）：人类可读，带颜色（终端）/ 纯文本（文件）
- **json**：结构化，机器可解析，适合日志聚合系统

切换格式：`self-driven-agent --log-format json`

### 关键日志标志

| 标志 | 含义 |
|------|------|
| `Entering main loop` / `System ready` | Agent 启动就绪（启动脚本探测此标志） |
| `Shutdown step` | 优雅停机进度（共 6 步） |
| `Shutdown snapshot saved` | 停机快照已保存 |
| `error_code=200003` | 错误码（可用于过滤定位） |

## 诊断命令

```bash
# 验证安装
python scripts/verify_installation.py

# 验证配置不启动
self-driven-agent --dry-run

# 查询运行状态
self-driven-agent --status

# 查看最近错误
grep "ERROR\|error_code" logs/agent.log | tail -20

# 查看停机过程
grep -i "shutdown" logs/agent.log

# 查看资源告警
grep "resource_\|exceeded" logs/agent.log

# 实时监控
./scripts/monitor_5h.sh $(cat data/agent.pid) 3600  # 监控1小时
```

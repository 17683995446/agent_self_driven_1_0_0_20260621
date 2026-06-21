# 常见问答（FAQ）

汇总用户高频问题。按类别组织，便于快速查找。

- [安装类](#安装类)
- [配置类](#配置类)
- [运行类](#运行类)
- [性能类](#性能类)
- [日志与监控类](#日志与监控类)

## 安装类

### Q: 需要 Python 哪个版本？

A: Python 3.8+。推荐 3.10+。用 `python --version` 检查。

### Q: 哪些依赖是必需的，哪些是可选的？

A:
- **必需**：`pyyaml`（配置解析）
- **可选**：`numpy`（数值计算）、`psutil`（资源监控）。缺失时系统降级运行，不影响核心功能。

安装全部依赖：`pip install -e .[optional]`

### Q: 如何验证安装是否成功？

A: 运行 `python scripts/verify_installation.py`，会检查 Python 版本、依赖、包导入、配置文件、console_scripts 入口。

### Q: `self-driven-agent` 命令找不到怎么办？

A: 未安装 console_scripts 入口。运行 `pip install -e .` 重新安装（开发模式）。

## 配置类

### Q: 配置文件不存在会怎样？

A: 系统会抛出 `ValidationError(CONFIG_NOT_FOUND)`（错误码 200003）并退出，**不会**静默使用默认配置。这是为了避免"配置承诺与行为不一致"。请用 `--config` 指定路径或 `--env` 选择环境。

### Q: 配置项缺失会怎样？

A: 缺失的配置项使用代码内置默认值，不会崩溃。但建议显式配置所有关键项，避免行为与预期不符。

### Q: 如何查看当前加载的配置？

A: 启动时系统会打印配置摘要。也可用 `self-driven-agent --dry-run` 验证配置并查看摘要，不启动主循环。

### Q: dev/prod/test 配置有什么区别？

A:
- **dev**：低资源限制、高日志级别（DEBUG）、短周期，适合开发调试
- **prod**：生产配置，高资源限制、INFO 日志、长周期
- **test**：测试配置，最小资源、快速周期

用 `--env dev`/`--env prod`/`--env test` 选择。

### Q: 配置值范围错误怎么办？

A: 系统会抛出 `ValidationError(PARAMETER_RANGE_ERROR)`（错误码 100004）。对照 [配置说明](configuration.md) 检查数值范围，如 CPU/内存阈值、周期时长等。

## 运行类

### Q: 如何启动 Agent？

A:
```bash
# 使用启动脚本（推荐，含就绪探测和 PID 管理）
./scripts/start.sh                    # 默认 prod
./scripts/start.sh --env dev          # dev 环境

# 直接运行
self-driven-agent --env prod
python -m src.main --config config/prod.yaml
```

### Q: 如何停止 Agent？

A:
```bash
./scripts/stop.sh                     # 优雅停机（等待当前周期完成）
```

第一次 `Ctrl+C` 或 `SIGTERM` 触发优雅停机（保存快照），30 秒内未退出则强制终止。**不要**直接 `kill -9`，会丢失未保存的状态。

### Q: 如何查看运行状态？

A:
```bash
self-driven-agent --status            # 读取 data/runtime_status.json
```

显示周期数、运行时长、任务统计、资源使用、最近错误等。

### Q: Agent 启动后立即退出怎么办？

A:
1. 用 `--dry-run` 验证配置
2. 查看 `logs/agent.out` 的错误信息
3. 常见原因：配置文件不存在（200003）、配置值越界（100004）、依赖缺失

### Q: 可以同时运行多个 Agent 实例吗？

A: 不建议。默认 PID 文件和日志路径是共享的，多实例会冲突。如需多实例，需为每个实例配置独立的 `log_dir` 和 `data_dir`。

## 性能类

### Q: CPU/内存占用过高怎么办？

A:
1. 查看 `self-driven-agent --status` 的资源统计
2. 调低 `cycle_interval`（降低周期频率）
3. 调低 `memory.max_entries`（减少记忆容量）
4. 调低 `snapshot.max_snapshots`（减少快照数量）

### Q: 任务执行慢怎么办？

A:
1. 检查是否有任务超时（错误码 500002）
2. 调高 `task_timeout`
3. 优化任务函数本身
4. 检查资源是否被安全护栏限制（错误码 3xxxxx）

### Q: 内存持续增长怎么办？

A: 见 [故障排查 - 内存泄漏](troubleshooting.md#内存泄漏)。主要原因是记忆/快照/事件历史未清理。调低对应的容量上限即可。

## 日志与监控类

### Q: 日志在哪里？

A:
- `logs/agent.log`：主日志（轮转，10MB/份，保留 5 份）
- `logs/agent.out`：启动脚本重定向的输出
- `logs/runtime_status.json`：运行时状态（JSON）

详见 [故障排查 - 日志分析](troubleshooting.md#日志分析)。

### Q: 如何切换 JSON 日志格式？

A: `self-driven-agent --log-format json`。适合日志聚合系统（ELK、Loki 等）。

### Q: 如何关闭彩色日志？

A: 设置环境变量 `AGENT_NO_COLOR=1`。文件日志始终是纯文本，颜色仅用于终端。

### Q: 如何长时间监控 Agent？

A:
```bash
# 监控1小时（默认5小时）
./scripts/monitor_5h.sh $(cat data/agent.pid) 3600
```

监控脚本会每 30 分钟记录 CPU/内存/日志行数，结束时生成报告。

### Q: 启动脚本卡在"等待 Agent 就绪"怎么办？

A: Agent 30 秒内未输出就绪标志。查看 `logs/agent.out` 排查启动失败原因（通常是配置错误或依赖缺失）。

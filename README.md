# 自驱永续进化Agent系统

一个自驱、永续进化的智能Agent系统。系统通过感知环境、内生驱力、自主决策、执行任务、反馈学习的闭环实现持续进化。

## 快速开始

### 1. 安装

```bash
git clone <repository>
cd self_driven_agent
pip install -e .          # 核心安装
pip install -e .[optional] # 含可选依赖（numpy/psutil，推荐）
pip install -e .[dev]      # 含开发工具（pytest）
pip install -e .[all]      # 全部安装
```

### 2. 验证安装

```bash
self-driven-agent --version
self-driven-agent --dry-run
```

### 3. 启动

```bash
# 默认dev环境
self-driven-agent

# 指定环境
self-driven-agent --env prod

# 指定配置文件
self-driven-agent --config config/prod.yaml

# 设置日志级别
self-driven-agent --log-level DEBUG
```

或使用Python模块方式：

```bash
python -m src.main --env dev
```

### 4. 停止

按 `Ctrl+C` 发送SIGINT信号优雅停止。

## 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--config, -c` | 配置文件路径 | `--config config/prod.yaml` |
| `--env` | 环境选择（dev/prod/test） | `--env prod` |
| `--log-level` | 日志级别（DEBUG/INFO/WARNING/ERROR） | `--log-level DEBUG` |
| `--log-dir` | 日志输出目录 | `--log-dir /var/log/agent` |
| `--dry-run` | 验证配置不启动 | `--dry-run` |
| `--version, -v` | 显示版本 | `--version` |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AGENT_CONFIG_PATH` | 配置文件路径 | `./config/dev.yaml` |
| `AGENT_LOG_DIR` | 日志输出目录 | `logs` |

优先级：CLI参数 > 环境变量 > 默认值

## 配置

配置文件位于 `config/` 目录：

- `config/dev.yaml` - 开发环境（默认）
- `config/prod.yaml` - 生产环境
- `config/test.yaml` - 测试环境

详见 [配置说明](docs/deploy_user/configuration.md)。

## Python API

```python
from src.main import AgentSystem

# 创建并启动
agent = AgentSystem(config_path="config/dev.yaml", log_level="INFO")
agent.start()
```

## 项目结构

```
self_driven_agent/
├── src/                         # 源码
│   ├── left/                    # 左脑（认知+行动）
│   │   ├── cognition/           # 认知层（感知+预测）
│   │   │   ├── perception/      # 感知模块
│   │   │   └── prediction/      # 预测模块
│   │   └── action/              # 行动层（决策+执行）
│   │       ├── decision/        # 决策模块
│   │       └── execution/       # 执行模块
│   ├── platform/                # 平台层（生命周期+支撑）
│   │   ├── lifecycle/           # 生命周期（记忆+监控）
│   │   │   ├── memory/          # 记忆（配置+护栏+插件）
│   │   │   └── monitor/         # 监控（快照）
│   │   └── support/             # 支撑（模型+基础设施）
│   │       ├── models/          # 数据模型
│   │       └── infra/           # 基础设施（事件+配置）
│   └── main.py                  # 主入口
├── tests/                       # 测试
├── config/                      # 配置文件
├── docs/                        # 文档
├── scripts/                     # 运维脚本
├── pyproject.toml               # 项目配置
└── requirements.txt             # 核心依赖
```

## 依赖

### 核心依赖（必需）
- pyyaml - 配置管理

### 可选依赖（推荐安装）
- numpy - 数值计算（缺失时降级为纯Python实现）
- psutil - 系统监控（缺失时感知层返回默认值）

### 开发依赖
- pytest - 测试框架
- pytest-cov - 覆盖率工具

## 测试

```bash
# 全部测试
python -m pytest tests/ -v

# 易用性测试
python -m pytest tests/test_u1_config_path_consistency.py tests/test_u2_cli_args.py tests/test_u3_packaging.py tests/test_u4_dependency_management.py -v
```

## 文档

- [快速开始](docs/deploy_user/quick_start.md)
- [环境搭建](docs/deploy_user/setup.md)
- [核心概念](docs/deploy_user/concepts.md)
- [监控运维](docs/deploy_user/monitoring.md)
- [测试规范](docs/deploy_user/testing.md)
- [故障排查](docs/deploy_user/troubleshooting.md)
- [架构概览](docs/arch_api/overview.md)

## License

MIT

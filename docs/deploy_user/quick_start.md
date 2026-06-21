# 快速开始

- [安装](#安装)
- [启动](#启动)
- [基本使用](#基本使用)
- [配置](#配置)

## 安装

```bash
git clone <repository>
cd self_driven_agent
pip install -e .[optional]  # 推荐安装（含numpy/psutil）
```

或使用requirements文件：

```bash
pip install -r requirements.txt -r requirements-optional.txt
```

## 启动

```bash
# 使用console_scripts入口（推荐）
self-driven-agent

# 指定环境
self-driven-agent --env prod

# 使用Python模块
python -m src.main

# 验证配置不启动
self-driven-agent --dry-run
```

## 基本使用

```python
from src.main import AgentSystem

# 创建系统（可选指定配置路径和日志级别）
system = AgentSystem(config_path="config/dev.yaml", log_level="INFO")

# 启动（阻塞运行）
system.start()

# 停止
system.stop()
```

## 配置

编辑 `config/dev.yaml`（开发环境）或 `config/prod.yaml`（生产环境）：

```yaml
perception:
  system_poll_interval: 1.0

drive_engine:
  base_weights:
    safe: 0.4
    gain: 0.4
    eff: 0.2

guardrail:
  max_cpu_usage: 0.5
  max_memory_usage: 0.5
```

通过环境变量指定配置文件：

```bash
export AGENT_CONFIG_PATH=config/prod.yaml
self-driven-agent
```

或通过CLI参数：

```bash
self-driven-agent --config config/prod.yaml
```

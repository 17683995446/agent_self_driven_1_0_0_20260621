# 环境搭建

- [系统要求](#系统要求)
- [安装依赖](#安装依赖)
- [目录结构](#目录结构)
- [开发规范](#开发规范)

## 系统要求

- Python 3.8+
- pip 21.0+
- git

## 安装依赖

```bash
# 核心安装
pip install -e .

# 推荐安装（含可选依赖）
pip install -e .[optional]

# 开发安装（含测试工具）
pip install -e .[dev]

# 全部安装
pip install -e .[all]
```

或使用requirements文件：

```bash
pip install -r requirements.txt                      # 核心
pip install -r requirements.txt -r requirements-optional.txt  # 含可选
pip install -r requirements-dev.txt                   # 开发工具
```

## 目录结构

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

## 开发规范

1. 所有业务类必须继承 `abc.ABC`
2. 函数有效代码不超过7行
3. 全量类型注解
4. 统一错误码
5. 参数强校验

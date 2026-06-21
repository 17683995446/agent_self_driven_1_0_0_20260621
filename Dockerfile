# 自驱永续进化预测修正Agent系统
# 第一性原理：容器是系统的"细胞"，提供隔离与可复现环境

FROM python:3.11-slim

LABEL maintainer="agent-system"
LABEL description="Self-Driven Perpetual Evolution Agent System"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/healthcheck.py ./scripts/healthcheck.py

# 创建数据目录
RUN mkdir -p /app/data /app/logs /app/snapshots /app/memory

# 设置环境变量
ENV PYTHONPATH=/app
ENV AGENT_CONFIG_PATH=/app/config/prod.yaml
ENV AGENT_LOG_DIR=/app/logs
ENV AGENT_DATA_DIR=/app/data

# 健康检查（轻量级，不实例化完整AgentSystem）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python scripts/healthcheck.py || exit 1

# 暴露端口（用于未来扩展HTTP接口）
EXPOSE 8080

# 启动命令
CMD ["python", "-m", "src.main"]

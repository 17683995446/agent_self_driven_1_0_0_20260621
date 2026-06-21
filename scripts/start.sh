#!/bin/bash
# 启动脚本（X8：参数透传 + 就绪探测 + 公共库）
# 第一性原理：启动是系统的"出生"，必须确保环境正确
#
# 用法：
#   ./start.sh                    # 默认 prod 环境
#   ./start.sh --env dev          # 启动 dev 配置
#   ./start.sh --env test         # 启动 test 配置
#   ./start.sh --log-level DEBUG  # 透传其他参数

set -euo pipefail

# 加载公共库（X8：统一颜色/路径/日志函数，M15）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# 解析环境参数（X8：支持 --env，M5）
CONFIG_FILE=$(parse_env "$@")
log_info "使用配置文件: $CONFIG_FILE"

# 检查Python环境
check_python() {
    if ! command -v python &> /dev/null; then
        log_error "Python not found"
        exit 1
    fi

    local version
    version=$(python --version 2>&1 | awk '{print $2}')
    log_info "Python version: $version"
}

# 检查依赖
check_dependencies() {
    # 核心依赖（必需）
    local core_deps=("yaml")
    for dep in "${core_deps[@]}"; do
        if ! python -c "import $dep" 2>/dev/null; then
            log_error "核心依赖缺失: $dep"
            log_error "请安装: pip install pyyaml"
            exit 1
        fi
    done

    # 可选依赖（缺失时降级运行）
    local optional_deps=("psutil" "numpy")
    for dep in "${optional_deps[@]}"; do
        if ! python -c "import $dep" 2>/dev/null; then
            log_warn "可选依赖缺失: $dep（系统将降级运行）"
            log_warn "安装: pip install $dep"
        fi
    done

    log_info "依赖检查完成"
}

# 检查配置文件
check_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "配置文件不存在: $CONFIG_FILE"
        log_error "可用配置: config/dev.yaml, config/prod.yaml, config/test.yaml"
        exit 1
    fi
}

# 检查是否已在运行
check_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            # X8：校验 PID 对应进程确实是 agent（M6）
            if verify_pid_is_agent "$pid"; then
                log_warn "Agent already running (PID: $pid)"
                exit 1
            else
                log_warn "PID $pid 不是 Agent 进程，清理过期 PID 文件"
                rm -f "$PID_FILE"
            fi
        else
            rm -f "$PID_FILE"
        fi
    fi
}

# 启动Agent（X8：参数透传 + 就绪探测，M4）
start_agent() {
    log_info "Starting Self-Driven Agent..."

    export AGENT_CONFIG_PATH="$CONFIG_FILE"

    # 透传所有参数到 python -m src.main
    local pid
    pid=$(run_agent --config "$CONFIG_FILE" "$@")
    echo "$pid" > "$PID_FILE"

    # X8：就绪探测替代固定 sleep 2（M4）
    log_step "等待 Agent 就绪..."
    if wait_for_ready "$pid" 30; then
        log_success "Agent started successfully (PID: $pid)"
    else
        log_error "Agent failed to start within 30s"
        log_error "查看日志: tail -f $LOG_DIR/agent.out"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# 主流程
main() {
    check_python
    check_dependencies
    check_config
    setup_directories
    check_running
    start_agent
}

main "$@"

#!/bin/bash
# 停止脚本（X8：PID 校验 + 公共库）
# 第一性原理：停止是系统的"休眠"，必须优雅释放资源，且不误杀无关进程

set -euo pipefail

# 加载公共库（X8：统一颜色/路径/日志函数，M15）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

TIMEOUT=30

# 检查PID文件
check_pid_file() {
    if [[ ! -f "$PID_FILE" ]]; then
        log_warn "PID file not found: $PID_FILE"
        exit 0
    fi
}

# 获取PID
get_pid() {
    cat "$PID_FILE"
}

# 检查进程是否存在
check_process() {
    local pid=$1
    kill -0 "$pid" 2>/dev/null
}

# X8：校验 PID 对应进程确实是 agent（M6，防止误杀）
verify_pid() {
    local pid=$1
    if verify_pid_is_agent "$pid"; then
        return 0
    else
        log_error "PID $pid 对应的进程不是 Agent，拒绝停止"
        log_error "进程命令行: $(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null || echo '未知')"
        log_error "如需强制停止，请手动: kill -TERM $pid"
        exit 1
    fi
}

# 优雅停止
graceful_stop() {
    local pid=$1
    log_info "Sending graceful stop signal to PID: $pid"
    kill -TERM "$pid" 2>/dev/null || true
}

# 强制停止
force_stop() {
    local pid=$1
    log_warn "Force killing PID: $pid"
    kill -KILL "$pid" 2>/dev/null || true
}

# 等待进程退出
wait_for_exit() {
    local pid=$1
    local count=0

    while check_process "$pid"; do
        if [[ $count -ge $TIMEOUT ]]; then
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done

    return 0
}

# 清理
cleanup() {
    rm -f "$PID_FILE"
    log_info "Cleanup completed"
}

# 主流程
main() {
    check_pid_file

    local pid
    pid=$(get_pid)

    if ! check_process "$pid"; then
        log_warn "Process not running (PID: $pid)"
        cleanup
        exit 0
    fi

    # X8：校验 PID 确实是 agent 进程（M6）
    verify_pid "$pid"

    graceful_stop "$pid"

    if wait_for_exit "$pid"; then
        log_success "Agent stopped gracefully"
    else
        log_warn "Graceful stop timeout, forcing..."
        force_stop "$pid"
    fi

    cleanup
}

main "$@"

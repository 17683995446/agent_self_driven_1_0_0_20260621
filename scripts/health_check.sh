#!/bin/bash
# 健康检查脚本
# 第一性原理：健康检查是系统的"体检"，定期确认各器官正常运作

set -uo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/agent.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# 检查进程存活
check_process() {
    if [[ ! -f "$PID_FILE" ]]; then
        log_error "PID file not found"
        return 1
    fi

    local pid
    pid=$(cat "$PID_FILE")

    if kill -0 "$pid" 2>/dev/null; then
        log_info "Process running (PID: $pid)"
        return 0
    else
        log_error "Process not running (PID: $pid)"
        return 1
    fi
}

# 检查资源使用
check_resources() {
    if [[ ! -f "$PID_FILE" ]]; then
        return 1
    fi

    local pid
    pid=$(cat "$PID_FILE")

    # CPU使用率
    local cpu
    cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
    if [[ -n "$cpu" ]]; then
        if (( $(echo "$cpu > 80" | bc -l) )); then
            log_warn "CPU usage high: ${cpu}%"
        else
            log_info "CPU usage: ${cpu}%"
        fi
    fi

    # 内存使用率
    local mem
    mem=$(ps -p "$pid" -o %mem= 2>/dev/null | tr -d ' ')
    if [[ -n "$mem" ]]; then
        if (( $(echo "$mem > 80" | bc -l) )); then
            log_warn "Memory usage high: ${mem}%"
        else
            log_info "Memory usage: ${mem}%"
        fi
    fi
}

# 检查日志
check_logs() {
    local log_dir="$PROJECT_DIR/logs"
    if [[ ! -d "$log_dir" ]]; then
        log_warn "Log directory not found"
        return
    fi

    local error_count
    error_count=$(grep -r "ERROR" "$log_dir" 2>/dev/null | wc -l)
    if [[ "$error_count" -gt 10 ]]; then
        log_warn "High error count in logs: $error_count"
    else
        log_info "Log errors: $error_count"
    fi
}

# 检查磁盘空间
check_disk() {
    local usage
    usage=$(df "$PROJECT_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
    if [[ "$usage" -gt 90 ]]; then
        log_warn "Disk usage high: ${usage}%"
    else
        log_info "Disk usage: ${usage}%"
    fi
}

# 主流程
main() {
    echo "=== Self-Driven Agent Health Check ==="
    echo ""

    local healthy=0

    if check_process; then
        healthy=1
        check_resources
    fi

    check_logs
    check_disk

    echo ""
    if [[ "$healthy" -eq 1 ]]; then
        echo -e "${GREEN}Overall: HEALTHY${NC}"
        exit 0
    else
        echo -e "${RED}Overall: UNHEALTHY${NC}"
        exit 1
    fi
}

main "$@"

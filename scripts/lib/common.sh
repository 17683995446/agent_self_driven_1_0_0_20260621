#!/bin/bash
# 公共脚本函数库（X8：统一脚本体验，消除重复定义）
#
# 第一性原理：公共逻辑应集中维护，避免脚本间重复定义导致不一致
# 使用：source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# 颜色定义（X8：统一颜色定义，M15）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 路径解析（X8：统一路径解析，所有脚本共用）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/agent.pid"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"
SNAPSHOT_DIR="$PROJECT_DIR/snapshots"
MEMORY_DIR="$PROJECT_DIR/memory"

# 日志函数（X8：统一日志函数，M15）
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 创建必要目录（X8：统一目录初始化）
setup_directories() {
    mkdir -p "$LOG_DIR" "$DATA_DIR" "$SNAPSHOT_DIR" "$MEMORY_DIR"
}

# 解析环境参数（X8：统一 --env 参数解析，M5）
# 用法：parse_env "$@" 返回 CONFIG_FILE
parse_env() {
    local env="prod"  # 默认 prod
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --env)
                env="$2"
                shift 2
                ;;
            --env=*)
                env="${1#*=}"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    case "$env" in
        dev|prod|test)
            echo "$PROJECT_DIR/config/${env}.yaml"
            ;;
        *)
            log_error "无效环境: $env（可选: dev, prod, test）"
            exit 1
            ;;
    esac
}

# 透传参数到 python -m src.main（X8：统一参数透传，M4）
# 用法：run_agent "$@" 会把所有参数透传给 src.main
run_agent() {
    export PYTHONPATH="$PROJECT_DIR"
    export AGENT_LOG_DIR="$LOG_DIR"
    nohup python -m src.main "$@" > "$LOG_DIR/agent.out" 2>&1 &
    echo $!
}

# 就绪探测（X8：检查日志标志而非固定 sleep，M4）
# 用法：wait_for_ready $pid $timeout
wait_for_ready() {
    local pid=$1
    local timeout=${2:-30}
    local count=0
    local ready_marker="$LOG_DIR/agent.out"

    while [[ $count -lt $timeout ]]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            return 1
        fi
        # 检查日志中是否出现就绪标志
        if [[ -f "$ready_marker" ]]; then
            if grep -q "Entering main loop\|Agent system started\|System ready" "$ready_marker" 2>/dev/null; then
                return 0
            fi
        fi
        sleep 1
        count=$((count + 1))
    done
    return 1
}

# 校验 PID 对应进程命令行（X8：防止误杀，M6）
# 用法：verify_pid_is_agent $pid
verify_pid_is_agent() {
    local pid=$1
    if [[ ! -f "/proc/$pid/cmdline" ]]; then
        return 1
    fi
    local cmdline
    cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)
    if echo "$cmdline" | grep -q "src.main\|self-driven-agent"; then
        return 0
    fi
    return 1
}

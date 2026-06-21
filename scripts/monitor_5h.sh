#!/usr/bin/env bash
# 运行监控脚本（X8：参数化时长，L2）
# 第一性原理：监控时长应可配置，而非硬编码5小时
#
# 用法：
#   ./monitor_5h.sh <pid> [duration_seconds]
#   ./monitor_5h.sh 12345           # 默认监控5小时（18000秒）
#   ./monitor_5h.sh 12345 3600      # 监控1小时
#   ./monitor_5h.sh 12345 7200      # 监控2小时

set -euo pipefail

# 加载公共库（X8：统一路径，L2）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# 参数解析（X8：参数化时长，L2）
PID=${1:?用法: $0 <pid> [duration_seconds]}
DURATION=${2:-18000}  # 默认5小时

# 路径使用公共库定义（X8：消除硬编码，L2）
LOG="$LOG_DIR/runtime_monitor.log"
REPORT="$LOG_DIR/runtime_monitor_report.log"
START=$(date +%s)
END=$((START + DURATION))

# 时长可读化
format_duration() {
    local secs=$1
    local hours=$((secs / 3600))
    local mins=$(((secs % 3600) / 60))
    echo "${hours}小时${mins}分钟"
}

echo "=== 运行监控开始 ===" > "$REPORT"
echo "PID: $PID" >> "$REPORT"
echo "监控时长: $(format_duration $DURATION) ($DURATION 秒)" >> "$REPORT"
echo "开始时间: $(date -d @$START '+%Y-%m-%d %H:%M:%S')" >> "$REPORT"
echo "预计结束: $(date -d @$END '+%Y-%m-%d %H:%M:%S')" >> "$REPORT"
echo "" >> "$REPORT"

while true; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START))
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 进程已退出! 运行时长: ${ELAPSED}秒" >> "$REPORT"
        break
    fi
    if [ "$ELAPSED" -ge "$DURATION" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已满 $(format_duration $DURATION)，停止进程" >> "$REPORT"
        kill "$PID"
        break
    fi
    # 每30分钟输出一次状态
    if [ $((ELAPSED % 1800)) -lt 60 ]; then
        CPU=$(ps -p "$PID" -o %cpu= 2>/dev/null || echo "N/A")
        MEM=$(ps -p "$PID" -o %mem= 2>/dev/null || echo "N/A")
        LINES=$(wc -l < "$LOG" 2>/dev/null || echo "0")
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 运行中 | 已运行: ${ELAPSED}s | CPU: ${CPU}% | MEM: ${MEM}% | 日志行数: $LINES" >> "$REPORT"
    fi
    sleep 60
done

# 生成最终报告
echo "" >> "$REPORT"
echo "=== 最终报告 ===" >> "$REPORT"
echo "总运行时长: ${ELAPSED}秒 ($(format_duration $ELAPSED))" >> "$REPORT"
if [[ -f "$LOG" ]]; then
    echo "日志总行数: $(wc -l < "$LOG")" >> "$REPORT"
    echo "日志最后10行:" >> "$REPORT"
    tail -n 10 "$LOG" >> "$REPORT"
else
    echo "日志文件不存在: $LOG" >> "$REPORT"
fi

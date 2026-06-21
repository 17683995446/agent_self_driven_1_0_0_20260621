#!/usr/bin/env python3
"""
轻量健康检查脚本（X10：增强指标，L7）

检查Agent系统是否健康运行，不实例化完整AgentSystem（避免副作用）。

检查项：
1. 进程存活（通过PID文件）
2. 日志文件最近更新
3. 日志中无致命错误
4. 运行时状态（周期数/运行时长/最近错误，来自 runtime_status.json）

使用：python scripts/healthcheck.py
退出码：0=健康，1=不健康
"""

import os
import sys
import time
import json
from pathlib import Path


def check_pid_file(pid_file):
    """检查PID文件"""
    if not os.path.exists(pid_file):
        return False, f"PID文件不存在: {pid_file}"
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
    except (ValueError, IOError):
        return False, f"PID文件无效: {pid_file}"
    # 检查进程是否存活
    try:
        os.kill(pid, 0)
        return True, f"进程运行中 (PID={pid})"
    except OSError:
        return False, f"进程不存在 (PID={pid})"


def check_log_freshness(log_file, max_age_seconds=120):
    """检查日志文件最近更新"""
    if not os.path.exists(log_file):
        return False, f"日志文件不存在: {log_file}"
    mtime = os.path.getmtime(log_file)
    age = time.time() - mtime
    if age > max_age_seconds:
        return False, f"日志已过期 ({age:.0f}秒未更新)"
    return True, f"日志正常更新 ({age:.0f}秒前)"


def check_log_errors(log_file, max_errors=10):
    """检查日志中致命错误数量"""
    if not os.path.exists(log_file):
        return False, f"日志文件不存在: {log_file}"
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        error_count = content.count('ERROR') + content.count('CRITICAL')
        if error_count > max_errors:
            return False, f"错误过多 ({error_count}条)"
        return True, f"错误数正常 ({error_count}条)"
    except IOError:
        return False, f"无法读取日志: {log_file}"


def check_runtime_status(status_file):
    """检查运行时状态（X10：从 runtime_status.json 读取指标，L7）"""
    if not os.path.exists(status_file):
        return False, "状态文件不存在（Agent 未运行或未写入状态）"
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return False, f"状态文件解析失败: {e}"

    cycle_count = status.get("cycle_count", 0)
    start_time = status.get("start_time")
    last_cycle_time = status.get("last_cycle_time")
    recent_errors = status.get("recent_errors", [])

    # 运行时长
    if start_time:
        uptime = time.time() - start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        uptime_str = f"{hours}h{minutes}m"
    else:
        uptime_str = "未知"

    # 最近周期时间
    if last_cycle_time:
        age = time.time() - last_cycle_time
        cycle_age = f"{age:.0f}秒前"
    else:
        cycle_age = "未知"

    msg = (
        f"周期数: {cycle_count} | "
        f"运行时长: {uptime_str} | "
        f"最近周期: {cycle_age} | "
        f"最近错误: {len(recent_errors)}条"
    )
    return True, msg


def main():
    """主函数"""
    project_dir = Path(__file__).parent.parent
    pid_file = project_dir / "data" / "agent.pid"
    log_file = project_dir / "logs" / "agent.log"
    status_file = project_dir / "data" / "runtime_status.json"

    checks = []

    # 检查PID文件
    ok, msg = check_pid_file(str(pid_file))
    checks.append(("进程检查", ok, msg))

    # 检查日志新鲜度
    ok, msg = check_log_freshness(str(log_file))
    checks.append(("日志新鲜度", ok, msg))

    # 检查日志错误
    ok, msg = check_log_errors(str(log_file))
    checks.append(("日志错误", ok, msg))

    # 检查运行时状态（X10：L7）
    ok, msg = check_runtime_status(str(status_file))
    checks.append(("运行时状态", ok, msg))

    # 输出结果
    all_ok = True
    for name, ok, msg in checks:
        status = "✓" if ok else "✗"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False

    if all_ok:
        print("healthy")
        return 0
    else:
        print("unhealthy")
        return 1


if __name__ == "__main__":
    sys.exit(main())

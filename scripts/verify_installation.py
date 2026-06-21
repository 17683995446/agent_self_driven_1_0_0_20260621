#!/usr/bin/env python3
"""
安装验证脚本

验证系统安装是否完整：
1. Python版本
2. 核心依赖（pyyaml）
3. 可选依赖（numpy/psutil）
4. 包导入
5. 配置文件
6. console_scripts入口

使用：python scripts/verify_installation.py
"""

import sys
import os


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"[1/6] Python版本: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"  ✗ 需要 Python 3.8+，当前 {version.major}.{version.minor}")
        return False
    print("  ✓ Python版本符合要求")
    return True


def check_core_dependencies():
    """检查核心依赖"""
    print("[2/6] 核心依赖:")
    all_ok = True
    try:
        import yaml
        print(f"  ✓ pyyaml {yaml.__version__}")
    except ImportError:
        print("  ✗ pyyaml 未安装（必需）")
        print("    安装: pip install pyyaml")
        all_ok = False
    return all_ok


def check_optional_dependencies():
    """检查可选依赖"""
    print("[3/6] 可选依赖:")
    all_ok = True
    try:
        import numpy
        print(f"  ✓ numpy {numpy.__version__}")
    except ImportError:
        print("  ✗ numpy 未安装（可选，缺失时降级运行）")
        print("    安装: pip install numpy")
        all_ok = False
    try:
        import psutil
        print(f"  ✓ psutil {psutil.__version__}")
    except ImportError:
        print("  ✗ psutil 未安装（可选，缺失时降级运行）")
        print("    安装: pip install psutil")
        all_ok = False
    return all_ok


def check_package_import():
    """检查包导入"""
    print("[4/6] 包导入:")
    all_ok = True
    try:
        from src.main import AgentSystem, main, __version__
        print(f"  ✓ src.main 导入成功（版本 {__version__}）")
    except ImportError as e:
        print(f"  ✗ src.main 导入失败: {e}")
        all_ok = False
    try:
        from src.platform.lifecycle.memory.config_loader import ConfigLoader
        print("  ✓ ConfigLoader 导入成功")
    except ImportError as e:
        print(f"  ✗ ConfigLoader 导入失败: {e}")
        all_ok = False
    return all_ok


def check_config_files():
    """检查配置文件（X8：使用相对路径，L8）"""
    print("[5/6] 配置文件:")
    all_ok = True
    # X8：基于脚本位置解析项目根目录，不硬编码绝对路径（L8）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    for config_file in ["config/dev.yaml", "config/prod.yaml", "config/test.yaml"]:
        if os.path.isfile(config_file):
            print(f"  ✓ {config_file} 存在")
        else:
            print(f"  ✗ {config_file} 不存在")
            all_ok = False
    return all_ok


def check_console_script():
    """检查console_scripts入口"""
    print("[6/6] console_scripts入口:")
    import subprocess
    try:
        result = subprocess.run(
            ["self-driven-agent", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"  ✓ self-driven-agent 可执行: {result.stdout.strip()}")
            return True
        else:
            print(f"  ✗ self-driven-agent 执行失败: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ✗ self-driven-agent 未找到")
        print("    安装: pip install -e .")
        return False
    except subprocess.TimeoutExpired:
        print("  ✗ self-driven-agent 执行超时")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("自驱永续进化Agent系统 - 安装验证")
    print("=" * 60)
    print()

    # 必需检查（失败则整体失败）
    required_checks = [
        ("Python版本", check_python_version()),
        ("核心依赖", check_core_dependencies()),
        ("包导入", check_package_import()),
        ("配置文件", check_config_files()),
        ("console_scripts入口", check_console_script()),
    ]

    # 可选检查（失败仅警告）
    optional_checks = [
        ("可选依赖", check_optional_dependencies()),
    ]

    print()
    print("=" * 60)
    required_passed = sum(1 for _, v in required_checks if v)
    required_total = len(required_checks)
    optional_passed = sum(1 for _, v in optional_checks if v)
    optional_total = len(optional_checks)

    if required_passed == required_total:
        if optional_passed == optional_total:
            print(f"✓ 安装验证通过 ({required_passed}/{required_total} 必需, {optional_passed}/{optional_total} 可选)")
        else:
            print(f"✓ 安装验证通过 ({required_passed}/{required_total} 必需)")
            print(f"  ⚠ 可选依赖部分缺失 ({optional_passed}/{optional_total})，系统将降级运行")
        print("系统已就绪，可以使用 self-driven-agent 启动")
        return 0
    else:
        print(f"✗ 安装验证失败 ({required_passed}/{required_total} 必需)")
        print("请根据上述提示修复问题")
        return 1


if __name__ == "__main__":
    sys.exit(main())

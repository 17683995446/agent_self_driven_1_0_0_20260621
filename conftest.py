"""
pytest全局配置

确保测试从项目根目录运行，src包可被导入
"""
import sys
import os

# 确保项目根目录在sys.path中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 切换到项目根目录，确保相对路径配置文件可被找到
os.chdir(PROJECT_ROOT)

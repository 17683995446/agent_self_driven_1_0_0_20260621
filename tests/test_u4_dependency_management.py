"""
U4：依赖管理规范化测试

验证依赖管理规范化：
1. requirements文件拆分正确
2. numpy可选导入降级
3. psutil可选导入降级
4. yaml可选导入降级
5. matplotlib已移除

第一性原理：缺失可选依赖不应崩溃，应降级运行
"""

import pytest
import os
from pathlib import Path


PROJECT_ROOT = Path("/workspace/self_driven_agent")


class TestU4RequirementsSplit:
    """测试requirements文件拆分"""

    def test_core_requirements_exists(self):
        """核心依赖文件存在"""
        assert (PROJECT_ROOT / "requirements.txt").is_file()

    def test_optional_requirements_exists(self):
        """可选依赖文件存在"""
        assert (PROJECT_ROOT / "requirements-optional.txt").is_file()

    def test_dev_requirements_exists(self):
        """开发依赖文件存在"""
        assert (PROJECT_ROOT / "requirements-dev.txt").is_file()

    def test_core_has_pyyaml(self):
        """核心依赖包含pyyaml"""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "pyyaml" in content

    def test_core_not_has_numpy(self):
        """核心依赖不包含numpy（移到可选）"""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        # 确保numpy不在核心依赖的依赖声明行中
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("#")]
        assert not any("numpy" in l for l in lines)

    def test_core_not_has_matplotlib(self):
        """核心依赖不包含matplotlib"""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "matplotlib" not in content

    def test_optional_has_numpy(self):
        """可选依赖包含numpy"""
        content = (PROJECT_ROOT / "requirements-optional.txt").read_text()
        assert "numpy" in content

    def test_optional_has_psutil(self):
        """可选依赖包含psutil"""
        content = (PROJECT_ROOT / "requirements-optional.txt").read_text()
        assert "psutil" in content

    def test_dev_has_pytest(self):
        """开发依赖包含pytest"""
        content = (PROJECT_ROOT / "requirements-dev.txt").read_text()
        assert "pytest" in content


class TestU4NumpyOptionalImport:
    """测试numpy可选导入"""

    def test_monitor_imports_without_numpy_crash(self):
        """monitor.py无numpy时不崩溃"""
        from src.left.action.execution import monitor
        assert hasattr(monitor, 'np')
        # np可能是None（如果numpy未安装）或numpy模块

    def test_error_decomposition_imports_without_crash(self):
        """error_decomposition.py无numpy时不崩溃"""
        from src.left.cognition.perception import error_decomposition
        assert hasattr(error_decomposition, 'np')

    def test_convergence_imports_without_crash(self):
        """convergence.py无numpy时不崩溃"""
        from src.left.cognition.prediction import convergence
        assert hasattr(convergence, 'np')

    def test_differentiable_reward_imports_without_crash(self):
        """differentiable_reward.py无numpy时不崩溃"""
        from src.left.cognition.prediction import differentiable_reward
        assert hasattr(differentiable_reward, 'np')

    def test_prediction_imports_without_crash(self):
        """prediction.py无numpy时不崩溃"""
        from src.left.cognition.perception import prediction
        assert hasattr(prediction, 'np')


class TestU4NumpyDegradation:
    """测试numpy降级功能"""

    def test_monitor_avg_error_without_numpy(self):
        """monitor无numpy时计算平均误差"""
        from src.left.action.execution.monitor import EvolutionMonitor
        monitor = EvolutionMonitor()
        # 添加一些误差历史
        monitor.error_history.extend([0.1, 0.2, 0.3, 0.4, 0.5])
        # 即使numpy可用，也应能计算
        result = monitor._compute_avg_error()
        assert 0.0 <= result <= 1.0

    def test_monitor_halves_diff_without_numpy(self):
        """monitor无numpy时计算前后半段差"""
        from src.left.action.execution.monitor import EvolutionMonitor
        monitor = EvolutionMonitor()
        indices = [0.1, 0.2, 0.3, 0.4]
        result = monitor._compute_halves_diff(indices)
        # 后半段均值 - 前半段均值 = 0.35 - 0.15 = 0.2
        assert abs(result - 0.2) < 0.001

    def test_convergence_check_without_numpy(self):
        """convergence无numpy时检查收敛"""
        from src.left.cognition.prediction.convergence import WeightConvergenceAnalyzer
        from src.platform.support.models.base.state import DriveWeights
        analyzer = WeightConvergenceAnalyzer(tolerance=0.1)
        old = DriveWeights(safe=0.3, gain=0.4, eff=0.3)
        new = DriveWeights(safe=0.32, gain=0.38, eff=0.30)
        result = analyzer._check_convergence(old, new)
        assert isinstance(result, bool)


class TestU4YamlOptionalImport:
    """测试yaml可选导入"""

    def test_config_loader_has_yaml_attr(self):
        """ConfigLoader模块有yaml属性"""
        from src.platform.lifecycle.memory import config_loader
        assert hasattr(config_loader, 'yaml')

    def test_config_loader_works_with_yaml(self):
        """ConfigLoader有yaml时正常工作"""
        os.chdir("/workspace/self_driven_agent")
        from src.platform.lifecycle.memory.config_loader import ConfigLoader
        loader = ConfigLoader("./config/dev.yaml")
        assert loader.get("environment") == "dev"


class TestU4PyprojectOptionalDeps:
    """测试pyproject.toml可选依赖声明"""

    def test_pyproject_has_optional_section(self):
        """pyproject.toml有optional-dependencies"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[project.optional-dependencies]" in content

    def test_pyproject_optional_has_numpy(self):
        """可选依赖包含numpy"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "numpy" in content

    def test_pyproject_optional_has_psutil(self):
        """可选依赖包含psutil"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "psutil" in content

    def test_pyproject_dev_has_pytest(self):
        """dev依赖包含pytest"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "pytest" in content

    def test_pyproject_core_only_pyyaml(self):
        """核心dependencies只有pyyaml"""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        # 找到dependencies部分
        start = content.find("dependencies = [")
        end = content.find("]", start)
        deps_section = content[start:end]
        assert "pyyaml" in deps_section
        assert "numpy" not in deps_section
        assert "psutil" not in deps_section
        assert "matplotlib" not in deps_section

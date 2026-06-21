"""
权重收敛性分析器测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.prediction.convergence import WeightConvergenceAnalyzer
from src.platform.support.models.base.state import DriveWeights, GapState


class TestConvergenceNormal:
    """正常值测试"""

    def test_converges_with_constant_gaps(self):
        analyzer = WeightConvergenceAnalyzer(max_iterations=100)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)] * 50
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.3)
        assert result.converged is True
        assert result.iterations < 50

    def test_final_weights_sum_to_one(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)] * 10
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.3)
        total = result.final_weights.safe + result.final_weights.gain + result.final_weights.eff
        assert abs(total - 1.0) < 1e-6

    def test_history_recorded(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)] * 5
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.3)
        assert len(result.weight_history) == 6
        assert len(result.gap_history) == 5


class TestConvergenceBoundary:
    """边界极值测试"""

    def test_single_gap(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)]
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.3)
        assert result.converged is False
        assert result.iterations == 1

    def test_zero_adaptation_rate(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)] * 10
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.0)
        assert result.final_weights.safe == pytest.approx(0.5, abs=1e-6)

    def test_full_adaptation_rate(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [GapState(safety=0.5, gain=0.3, efficiency=0.2)] * 10
        result = analyzer.analyze(weights, gaps, adaptation_rate=1.0)
        assert result.converged is True


class TestConvergenceEmpty:
    """空入参测试"""

    def test_empty_gap_sequence(self):
        analyzer = WeightConvergenceAnalyzer()
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        result = analyzer.analyze(weights, [], adaptation_rate=0.3)
        assert result.converged is False
        assert result.iterations == 0
        assert result.final_weights == weights


class TestConvergenceInvalid:
    """非法格式测试"""

    def test_oscillating_gaps(self):
        analyzer = WeightConvergenceAnalyzer(max_iterations=100)
        weights = DriveWeights(safe=0.4, gain=0.4, eff=0.2)
        gaps = [
            GapState(safety=0.9, gain=0.05, efficiency=0.05),
            GapState(safety=0.05, gain=0.9, efficiency=0.05),
        ] * 50
        result = analyzer.analyze(weights, gaps, adaptation_rate=0.3)
        assert result.converged is False

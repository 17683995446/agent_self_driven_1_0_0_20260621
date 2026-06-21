"""
缺口计算公理化测试

四类用例：正常值、空入参、边界极值、非法格式
"""

import pytest
from src.left.cognition.prediction.gap_axiom import SmoothGapCalculator


class TestGapAxiomNormal:
    """正常值测试"""

    def test_compute_normal(self):
        calc = SmoothGapCalculator()
        assert calc.compute(0.5) == pytest.approx(0.5, abs=1e-6)

    def test_compute_quarter(self):
        calc = SmoothGapCalculator()
        assert calc.compute(0.25) == pytest.approx(0.75, abs=1e-6)

    def test_verify_passes(self):
        calc = SmoothGapCalculator()
        result = calc.verify_axioms()
        assert result.valid is True
        assert result.violations == []


class TestGapAxiomBoundary:
    """边界极值测试"""

    def test_compute_zero_reward(self):
        calc = SmoothGapCalculator()
        val = calc.compute(0.0)
        assert val == pytest.approx(1.0, abs=1e-6)

    def test_compute_one_reward(self):
        calc = SmoothGapCalculator()
        val = calc.compute(1.0)
        assert val == pytest.approx(1e-7, abs=1e-8)

    def test_compute_exactly_half(self):
        calc = SmoothGapCalculator()
        val = calc.compute(0.5)
        assert val == pytest.approx(0.5, abs=1e-6)


class TestGapAxiomInvalid:
    """非法格式测试"""

    def test_compute_negative_reward(self):
        calc = SmoothGapCalculator()
        val = calc.compute(-0.5)
        assert val == pytest.approx(1.0, abs=1e-6)

    def test_compute_over_one_reward(self):
        calc = SmoothGapCalculator()
        val = calc.compute(1.5)
        assert val == pytest.approx(1e-7, abs=1e-8)

    def test_monotonicity_holds(self):
        calc = SmoothGapCalculator()
        g1 = calc.compute(0.1)
        g2 = calc.compute(0.9)
        assert g1 > g2


class TestGapAxiomEpsilon:
    """Epsilon边界测试"""

    def test_custom_epsilon(self):
        calc = SmoothGapCalculator(epsilon=0.01)
        val = calc.compute(1.0)
        assert val == pytest.approx(0.01, abs=1e-6)

    def test_ideal_state_with_epsilon(self):
        calc = SmoothGapCalculator(epsilon=0.01)
        result = calc.verify_axioms()
        assert result.valid is True

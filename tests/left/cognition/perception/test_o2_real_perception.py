"""
O2 秩序化测试：感知层真实化

第一性原理：感知必须真实，否则决策基于错误数据
验证 LogState/FileState/SelfState 真实采集
"""

import os
import tempfile
import pytest

from src.left.cognition.perception.perception import EnvironmentPerceptionModule


class TestLogStateRealCollection:
    """测试日志状态真实采集"""

    def test_no_log_dir_returns_empty(self, monkeypatch) -> None:
        """无日志目录返回空状态"""
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_log_dir", lambda: "/nonexistent/path/xyz")
        state = module._build_log_state()
        assert state.error_rate == 0.0
        assert state.warning_rate == 0.0

    def test_real_log_collection(self, tmp_path, monkeypatch) -> None:
        """真实日志采集"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "app.log"
        log_file.write_text(
            "INFO start\n"
            "ERROR crash\n"
            "ERROR fail\n"
            "WARNING slow\n"
            "INFO done\n"
        )
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_log_dir", lambda: str(log_dir))
        state = module._build_log_state()
        assert state.error_rate > 0.0
        assert state.warning_rate > 0.0
        # 2 errors / 5 total = 0.4
        assert abs(state.error_rate - 0.4) < 0.01

    def test_empty_log_dir(self, tmp_path, monkeypatch) -> None:
        """空日志目录"""
        log_dir = tmp_path / "empty_logs"
        log_dir.mkdir()
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_log_dir", lambda: str(log_dir))
        state = module._build_log_state()
        assert state.error_rate == 0.0

    def test_only_info_logs(self, tmp_path, monkeypatch) -> None:
        """只有INFO日志"""
        log_dir = tmp_path / "info_logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("INFO msg1\nINFO msg2\n")
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_log_dir", lambda: str(log_dir))
        state = module._build_log_state()
        assert state.error_rate == 0.0
        assert state.warning_rate == 0.0


class TestFileStateRealCollection:
    """测试文件状态真实采集"""

    def test_no_target_dir_returns_empty(self, monkeypatch) -> None:
        """无目标目录返回空状态"""
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_target_dir", lambda: "/nonexistent/path/xyz")
        state = module._build_file_state()
        assert state.total_files == 0

    def test_real_file_collection(self, tmp_path, monkeypatch) -> None:
        """真实文件采集"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("print('a')")
        (src_dir / "b.py").write_text("print('b')")
        sub = src_dir / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("print('c')")
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_target_dir", lambda: str(src_dir))
        state = module._build_file_state()
        assert state.total_files == 3

    def test_skip_pycache(self, tmp_path, monkeypatch) -> None:
        """跳过__pycache__"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("a")
        cache = src_dir / "__pycache__"
        cache.mkdir()
        (cache / "a.pyc").write_text("cached")
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_target_dir", lambda: str(src_dir))
        state = module._build_file_state()
        assert state.total_files == 1  # 不含.pyc


class TestSelfStateRealCollection:
    """测试自身状态真实采集"""

    def test_self_state_has_values(self) -> None:
        """自身状态有值"""
        module = EnvironmentPerceptionModule()
        state = module._build_self_state()
        # cpu和memory应为有效值（可能为0如果psutil不可用）
        assert 0.0 <= state.agent_cpu <= 1.0
        assert 0.0 <= state.agent_memory <= 1.0

    def test_prediction_error_default_zero(self) -> None:
        """预测误差默认为0"""
        module = EnvironmentPerceptionModule()
        state = module._build_self_state()
        assert state.prediction_error == 0.0

    def test_inject_prediction_error(self) -> None:
        """注入预测误差"""
        module = EnvironmentPerceptionModule()
        module.set_prediction_error(0.5)
        state = module._build_self_state()
        assert state.prediction_error == 0.5

    def test_inject_prediction_error_clamped(self) -> None:
        """注入预测误差被钳制到[0,1]"""
        module = EnvironmentPerceptionModule()
        module.set_prediction_error(1.5)
        state = module._build_self_state()
        assert state.prediction_error == 1.0
        module.set_prediction_error(-0.5)
        state = module._build_self_state()
        assert state.prediction_error == 0.0


class TestFullStateIntegration:
    """完整状态集成测试"""

    def test_get_current_state_includes_real_logs(self, tmp_path, monkeypatch) -> None:
        """get_current_state包含真实日志状态"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("ERROR crash\nINFO ok\n")
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_log_dir", lambda: str(log_dir))
        state = module.get_current_state()
        assert state.logs.error_rate > 0.0

    def test_get_current_state_includes_real_files(self, tmp_path, monkeypatch) -> None:
        """get_current_state包含真实文件状态"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("a")
        module = EnvironmentPerceptionModule()
        monkeypatch.setattr(module, "_find_target_dir", lambda: str(src_dir))
        state = module.get_current_state()
        assert state.files.total_files >= 1

    def test_get_current_state_includes_self_metrics(self) -> None:
        """get_current_state包含自身指标"""
        module = EnvironmentPerceptionModule()
        state = module.get_current_state()
        assert 0.0 <= state.self.agent_cpu <= 1.0
        assert 0.0 <= state.self.agent_memory <= 1.0

"""
环境感知扩展测试

补充覆盖传感器、历史记录等路径
"""

import pytest

from src.left.cognition.perception.perception import (
    EnvironmentPerceptionModule, PerceptionModuleBase,
    CPUSensor, MemorySensor, DiskSensor, ProcessSensor, Sensor,
    NetworkSensor, IOSensor,
    SensorReading, SensorHealth, SensorManager,
)
from src.platform.support.models.base.state import EnvironmentState


class TestSensorBase:
    """测试传感器基类"""

    def test_sensor_abstract(self):
        with pytest.raises(TypeError):
            Sensor()


class TestCPUSensor:
    """测试CPU传感器"""

    def test_read(self):
        sensor = CPUSensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert 0.0 <= reading.confidence <= 1.0
        assert reading.unit == "ratio"

    def test_properties(self):
        sensor = CPUSensor()
        assert sensor.sensor_type == "cpu"
        assert sensor.sampling_rate == 1.0

    def test_health_check(self):
        sensor = CPUSensor()
        health = sensor.health_check()
        assert health.healthy is True


class TestMemorySensor:
    """测试内存传感器"""

    def test_read(self):
        sensor = MemorySensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert 0.0 <= reading.confidence <= 1.0
        assert reading.unit == "ratio"

    def test_properties(self):
        sensor = MemorySensor()
        assert sensor.sensor_type == "memory"


class TestDiskSensor:
    """测试磁盘传感器"""

    def test_read(self):
        sensor = DiskSensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert 0.0 <= reading.confidence <= 1.0
        assert reading.unit == "ratio"

    def test_properties(self):
        sensor = DiskSensor()
        assert sensor.sensor_type == "disk"


class TestProcessSensor:
    """测试进程传感器"""

    def test_read(self):
        sensor = ProcessSensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert 0.0 <= reading.confidence <= 1.0
        assert reading.unit == "ratio"

    def test_compute_ratios(self):
        sensor = ProcessSensor()
        import psutil
        processes = list(psutil.process_iter())
        ratio, zombie = sensor._compute_ratios(processes)
        assert 0.0 <= ratio <= 1.0
        assert 0.0 <= zombie <= 1.0


class TestEnvironmentPerceptionModuleExtended:
    """测试环境感知模块扩展路径"""

    def test_register_sensor(self):
        module = EnvironmentPerceptionModule()
        custom = CPUSensor()
        module.register_sensor(custom)
        assert "cpu" in module.sensors

    def test_get_recent_history(self):
        module = EnvironmentPerceptionModule()
        module.get_current_state()
        module.get_current_state()
        history = module.get_recent_history(2)
        assert len(history) == 2

    def test_start_stop(self):
        module = EnvironmentPerceptionModule()
        module.start()
        assert module.running is True
        assert module.is_running is True
        module.stop()
        assert module.running is False

    def test_multiple_states(self):
        module = EnvironmentPerceptionModule()
        for _ in range(5):
            state = module.get_current_state()
            assert isinstance(state, EnvironmentState)

    def test_read_sensor_error(self):
        module = EnvironmentPerceptionModule()
        class BadSensor(Sensor):
            @property
            def sensor_type(self):
                return "bad"
            @property
            def sampling_rate(self):
                return 1.0
            def calibrate(self):
                return True
            def read(self):
                raise RuntimeError("sensor error")
        bad = BadSensor()
        module.register_sensor(bad)
        state = module.get_current_state()
        assert isinstance(state, EnvironmentState)

    def test_read_sensor_exception_path(self):
        module = EnvironmentPerceptionModule()
        class FailSensor(Sensor):
            @property
            def sensor_type(self):
                return "fail"
            @property
            def sampling_rate(self):
                return 1.0
            def calibrate(self):
                return True
            def read(self):
                raise ValueError("fail")
        fs = FailSensor()
        result = module._read_sensor("fail", fs)
        assert result.value == 0.0
        assert result.confidence == 0.0

    def test_read_all_sensors(self):
        module = EnvironmentPerceptionModule()
        readings = module._read_all_sensors()
        assert "cpu" in readings
        assert "memory" in readings
        assert "disk" in readings
        assert "process" in readings

    def test_build_system_state(self):
        module = EnvironmentPerceptionModule()
        readings = {
            "cpu": SensorReading(0, 0.5, "ratio", 0.9),
            "memory": SensorReading(0, 0.3, "ratio", 0.9),
            "disk": SensorReading(0, 0.2, "ratio", 0.9),
            "process": SensorReading(0, 0.1, "ratio", 0.9),
        }
        system = module._build_system_state(readings)
        assert system.cpu_overall == 0.5
        assert system.memory_usage == 0.3

    def test_build_log_state(self):
        module = EnvironmentPerceptionModule()
        log = module._build_log_state()
        assert log.error_rate == 0.0

    def test_build_file_state(self):
        module = EnvironmentPerceptionModule()
        file_state = module._build_file_state()
        assert file_state is not None

    def test_build_self_state(self):
        module = EnvironmentPerceptionModule()
        self_state = module._build_self_state()
        assert self_state.agent_cpu == 0.0


class TestNetworkSensor:
    """测试网络传感器"""

    def test_read(self):
        sensor = NetworkSensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert reading.unit == "ratio"

    def test_properties(self):
        sensor = NetworkSensor()
        assert sensor.sensor_type == "network"
        assert sensor.sampling_rate == 0.5

    def test_calibrate(self):
        sensor = NetworkSensor()
        assert sensor.calibrate() is True


class TestIOSensor:
    """测试IO传感器"""

    def test_read(self):
        sensor = IOSensor()
        reading = sensor.read()
        assert 0.0 <= reading.value <= 1.0
        assert reading.unit == "ratio"

    def test_properties(self):
        sensor = IOSensor()
        assert sensor.sensor_type == "io"
        assert sensor.sampling_rate == 0.5

    def test_calibrate(self):
        sensor = IOSensor()
        assert sensor.calibrate() is True


class TestSensorManager:
    """测试传感器管理器"""

    def test_register_and_list(self):
        manager = SensorManager()
        manager.register_sensor(CPUSensor())
        assert "cpu" in manager.list_sensors()

    def test_unregister(self):
        manager = SensorManager()
        manager.register_sensor(CPUSensor())
        manager.unregister_sensor("cpu")
        assert "cpu" not in manager.list_sensors()

    def test_get_sensor(self):
        manager = SensorManager()
        manager.register_sensor(MemorySensor())
        sensor = manager.get_sensor("memory")
        assert sensor is not None
        assert sensor.sensor_type == "memory"

    def test_calibrate_all(self):
        manager = SensorManager()
        manager.register_sensor(CPUSensor())
        results = manager.calibrate_all()
        assert results["cpu"] is True

    def test_health_check_all(self):
        manager = SensorManager()
        manager.register_sensor(CPUSensor())
        health = manager.health_check_all()
        assert health["cpu"].healthy is True

    def test_read_all(self):
        manager = SensorManager()
        manager.register_sensor(DiskSensor())
        readings = manager.read_all()
        assert "disk" in readings
        assert 0.0 <= readings["disk"].value <= 1.0

    def test_start_stop_sampling(self):
        manager = SensorManager()
        manager.start_sampling()
        assert manager.running is True
        manager.stop_sampling()
        assert manager.running is False

"""
环境感知传感器异常路径测试

覆盖各传感器异常处理分支
"""

import pytest
from unittest.mock import patch

from src.left.cognition.perception.perception import (
    CPUSensor, MemorySensor, DiskSensor, ProcessSensor, SensorReading,
)


class TestCPUSensorError:
    """测试CPU传感器异常路径"""

    def test_read_exception(self):
        sensor = CPUSensor()
        with patch("psutil.cpu_percent", side_effect=OSError("cpu error")):
            reading = sensor.read()
            assert reading.value == 0.0
            assert reading.confidence == 0.0


class TestMemorySensorError:
    """测试内存传感器异常路径"""

    def test_read_exception(self):
        sensor = MemorySensor()
        with patch("psutil.virtual_memory", side_effect=OSError("mem error")):
            reading = sensor.read()
            assert reading.value == 0.0
            assert reading.confidence == 0.0


class TestDiskSensorError:
    """测试磁盘传感器异常路径"""

    def test_read_exception(self):
        sensor = DiskSensor()
        with patch("psutil.disk_usage", side_effect=OSError("disk error")):
            reading = sensor.read()
            assert reading.value == 0.0
            assert reading.confidence == 0.0


class TestProcessSensorError:
    """测试进程传感器异常路径"""

    def test_read_exception(self):
        sensor = ProcessSensor()
        with patch("psutil.process_iter", side_effect=OSError("proc error")):
            reading = sensor.read()
            assert reading.value == 0.0
            assert reading.confidence == 0.0

    def test_count_zombies_exception(self):
        sensor = ProcessSensor()
        class FakeProc:
            def status(self):
                raise psutil.NoSuchProcess(1)
        with patch("psutil.process_iter", return_value=[FakeProc()]):
            reading = sensor.read()
            assert 0.0 <= reading.value <= 1.0

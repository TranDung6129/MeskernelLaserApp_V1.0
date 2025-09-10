"""
Data Processor - Xử lý và lưu trữ dữ liệu đo từ sensor
"""
import time
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal
from .state_detector import StateDetector, StateDetectorConfig

@dataclass
class MeasurementData:
    """Dữ liệu đo một lần"""
    timestamp: float
    distance_mm: float
    signal_quality: int
    voltage: Optional[float] = None
    temperature: Optional[float] = None
    velocity_ms: Optional[float] = None
    state: Optional[str] = None
    
    @property
    def distance_m(self) -> float:
        """Khoảng cách tính bằng mét"""
        return self.distance_mm / 1000.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển thành dictionary"""
        return {
            'timestamp': self.timestamp,
            'distance_mm': self.distance_mm,
            'distance_m': self.distance_m,
            'signal_quality': self.signal_quality,
            'voltage': self.voltage,
            'temperature': self.temperature
        }

class DataProcessor(QObject):
    """Xử lý và lưu trữ dữ liệu đo"""
    
    # Signals để update UI
    new_data_processed = pyqtSignal(dict)  # Dữ liệu mới đã xử lý
    statistics_updated = pyqtSignal(dict)  # Thống kê cập nhật
    
    def __init__(self, max_samples: int = 1000, velocity_threshold: float = 0.005):
        super().__init__()
        self.max_samples = max_samples
        self.measurements: deque = deque(maxlen=max_samples)
        self.recent_velocities: deque = deque(maxlen=max_samples)
        self.state_detector = StateDetector(StateDetectorConfig(velocity_threshold=velocity_threshold))
        
        # Statistics
        self.stats = {
            'total_samples': 0,
            'min_distance': float('inf'),
            'max_distance': 0.0,
            'avg_distance': 0.0,
            'current_distance': 0.0,
            'current_velocity': 0.0,
            'avg_velocity': 0.0,
            'min_velocity': 0.0,
            'max_velocity': 0.0,
            'current_quality': 0,
            'current_voltage': 0.0,
            'measurement_rate': 0.0,
            'last_update': time.time(),
            # Depth in meters for convenience
            'current_depth_m': 0.0,
            'max_depth_m': 0.0,
            # State & productivity
            'state': 'Dừng',
            'time_drilling_s': 0.0,
            'time_stopped_s': 0.0,
            'efficiency_percent': 0.0,
            'velocity_threshold': velocity_threshold,
        }
        
        # Device info
        self.device_info = {
            'hardware_version': 'Unknown',
            'software_version': 'Unknown',
            'serial_number': 'Unknown',
            'input_voltage': 0.0,
            'device_status': 'Unknown'
        }
        
    def add_measurement(self, distance_mm: float, signal_quality: int, *, velocity_ms: Optional[float] = None, state: Optional[str] = None, timestamp: Optional[float] = None) -> MeasurementData:
        """Thêm phép đo mới với tuỳ chọn truyền kèm vận tốc/state/timestamp."""
        ts = timestamp if timestamp is not None else time.time()
        measurement = MeasurementData(
            timestamp=ts,
            distance_mm=distance_mm,
            signal_quality=signal_quality,
            velocity_ms=velocity_ms,
            state=state,
        )
        
        self.measurements.append(measurement)
        self._update_statistics(measurement)
        
        # Emit signal với dữ liệu đã xử lý
        processed_data = measurement.to_dict()
        processed_data.update({
            'velocity_ms': self.stats['current_velocity'],
            'measurement_rate': self.stats['measurement_rate'],
            'state': self.stats['state'],
            'efficiency_percent': self.stats['efficiency_percent'],
            'velocity_threshold': self.stats['velocity_threshold'],
        })
        
        self.new_data_processed.emit(processed_data)
        self.statistics_updated.emit(self.get_current_stats())
        
        return measurement
    
    def _update_statistics(self, new_measurement: MeasurementData):
        """Cập nhật thống kê"""
        self.stats['total_samples'] += 1
        self.stats['current_distance'] = new_measurement.distance_mm
        self.stats['current_depth_m'] = new_measurement.distance_m
        self.stats['current_quality'] = new_measurement.signal_quality
        
        # Min/Max distance
        if new_measurement.distance_mm < self.stats['min_distance']:
            self.stats['min_distance'] = new_measurement.distance_mm
        if new_measurement.distance_mm > self.stats['max_distance']:
            self.stats['max_distance'] = new_measurement.distance_mm
            self.stats['max_depth_m'] = new_measurement.distance_m
            
        # Average distance (rolling average của 100 samples gần nhất)
        recent_measurements = list(self.measurements)[-100:]
        if recent_measurements:
            avg_dist = sum(m.distance_mm for m in recent_measurements) / len(recent_measurements)
            self.stats['avg_distance'] = avg_dist
            
        # Measurement rate (samples per second)
        current_time = time.time()
        time_diff = current_time - self.stats['last_update']
        if time_diff > 0:
            self.stats['measurement_rate'] = 1.0 / time_diff
        self.stats['last_update'] = current_time

        # Velocity tracking and statistics
        if new_measurement.velocity_ms is not None:
            self.recent_velocities.append(new_measurement.velocity_ms)
            self.stats['current_velocity'] = float(new_measurement.velocity_ms)
            if self.recent_velocities:
                v_array = list(self.recent_velocities)
                self.stats['avg_velocity'] = float(sum(v_array) / len(v_array))
                self.stats['min_velocity'] = float(min(v_array))
                self.stats['max_velocity'] = float(max(v_array))
            # State detection with hysteresis
            state_now = self.state_detector.update(new_measurement.velocity_ms, new_measurement.timestamp)
            self.stats['state'] = state_now
            self.stats['time_drilling_s'] = self.state_detector.total_time_drilling_s
            self.stats['time_stopped_s'] = self.state_detector.total_time_stopped_s
            self.stats['efficiency_percent'] = self.state_detector.get_efficiency_percent()
            # Propagate detected state back into the measurement for CSV export
            if new_measurement.state is None:
                new_measurement.state = state_now
        else:
            # If no velocity provided, do not change velocity stats
            pass
        
    def update_device_info(self, info_type: str, value: Any):
        """Cập nhật thông tin thiết bị"""
        if info_type in self.device_info:
            self.device_info[info_type] = value
            self.statistics_updated.emit(self.get_current_stats())
            
    def get_current_stats(self) -> Dict[str, Any]:
        """Lấy thống kê hiện tại"""
        return {
            **self.stats,
            **self.device_info
        }
        
    def get_recent_data(self, count: int = 100) -> List[MeasurementData]:
        """Lấy dữ liệu gần đây"""
        return list(self.measurements)[-count:]
    
    def get_distance_array(self, count: int = 100) -> np.ndarray:
        """Lấy array khoảng cách gần đây"""
        recent = self.get_recent_data(count)
        return np.array([m.distance_mm for m in recent])
    
    def get_timestamp_array(self, count: int = 100) -> np.ndarray:
        """Lấy array timestamp gần đây"""
        recent = self.get_recent_data(count)
        if not recent:
            return np.array([])
        # Convert to relative time (seconds from first measurement)
        first_time = recent[0].timestamp
        return np.array([m.timestamp - first_time for m in recent])
    
    def get_quality_array(self, count: int = 100) -> np.ndarray:
        """Lấy array signal quality gần đây"""
        recent = self.get_recent_data(count)
        return np.array([m.signal_quality for m in recent])
        
    def clear_data(self):
        """Xóa tất cả dữ liệu"""
        self.measurements.clear()
        self.recent_velocities.clear()
        self.state_detector.reset()
        self.stats = {
            'total_samples': 0,
            'min_distance': float('inf'),
            'max_distance': 0.0,
            'avg_distance': 0.0,
            'current_distance': 0.0,
            'current_velocity': 0.0,
            'avg_velocity': 0.0,
            'min_velocity': 0.0,
            'max_velocity': 0.0,
            'current_quality': 0,
            'current_voltage': 0.0,
            'measurement_rate': 0.0,
            'last_update': time.time(),
            'current_depth_m': 0.0,
            'max_depth_m': 0.0,
            'state': 'Dừng',
            'time_drilling_s': 0.0,
            'time_stopped_s': 0.0,
            'efficiency_percent': 0.0,
            'velocity_threshold': self.stats.get('velocity_threshold', 0.005),
        }
        
    def export_data_csv(self, filename: str) -> bool:
        """Export dữ liệu ra file CSV"""
        try:
            import csv
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'depth_m', 'distance_mm', 'velocity_ms', 'state', 'signal_quality', 'voltage', 'temperature']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for measurement in self.measurements:
                    writer.writerow({
                        'timestamp': measurement.timestamp,
                        'depth_m': f"{measurement.distance_m:.6f}",
                        'distance_mm': measurement.distance_mm,
                        'velocity_ms': f"{measurement.velocity_ms:.6f}" if measurement.velocity_ms is not None else '',
                        'state': measurement.state or '',
                        'signal_quality': measurement.signal_quality,
                        'voltage': measurement.voltage or '',
                        'temperature': measurement.temperature or ''
                    })
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False